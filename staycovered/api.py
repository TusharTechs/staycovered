"""FastAPI backend for the StayCovered web app."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import date

import hashlib
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from . import answer as answer_mod
from . import config, extract, rules, sources, store
from .drift import watch
from .engine.compute import worksheet

app = FastAPI(title="StayCovered API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------- public-demo protection: answer cache + per-visitor rate limit ----------
ANSWER_CACHE = config.ROOT / "data" / "cache" / "answers.json"      # committed, pre-warmed
RUNTIME_ANSWERS = config.RUNTIME_DIR / "answers.json"              # grows at runtime
_hits: dict[str, deque] = defaultdict(deque)
RATE = int(__import__("os").getenv("SC_RATE_PER_HOUR", "20"))


def _visitor(req: Request) -> str:
    fwd = req.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (req.client.host if req.client else "?"))


def _rate_limit(req: Request) -> None:
    now, q = time.time(), _hits[_visitor(req)]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= RATE:
        raise HTTPException(429, "You've asked a lot of new questions in the last hour; please try again later. Cached answers still work.")
    q.append(now)


def _cache_key(*parts: object) -> str:
    return hashlib.sha256(json.dumps([str(p).strip().lower() for p in parts]).encode()).hexdigest()[:24]


def _cache_get(key: str) -> dict | None:
    for p in (ANSWER_CACHE, RUNTIME_ANSWERS):
        if p.exists():
            v = json.loads(p.read_text()).get(key)
            if v:
                return v
    return None


def _cache_put(key: str, value: dict) -> None:
    d = json.loads(RUNTIME_ANSWERS.read_text()) if RUNTIME_ANSWERS.exists() else {}
    d[key] = value
    RUNTIME_ANSWERS.write_text(json.dumps(d))


def _llm_guard(fn):
    """Turn budget exhaustion into a friendly 503 instead of a crash."""
    from .llm import BudgetExceeded

    try:
        return fn()
    except BudgetExceeded as e:
        raise HTTPException(503, str(e))


def _d(s: str | None) -> date:
    return date.fromisoformat(s) if s else date.today()


def _ws(rec: store.CaseRecord, on: date) -> dict:
    return asdict(worksheet(rec.case, on))


@app.get("/api/health")
def health() -> dict:
    from .llm import spent_today
    return {"ok": True, "nebius": bool(config.NEBIUS_API_KEY), "tavily": bool(config.TAVILY_API_KEY),
            "sources": len(sources.all_sources()), "facts": len(rules.all_facts()),
            "budget_left_today": round(max(0.0, config.DAILY_USD_CAP - spent_today()), 3)}


# ---------- cases ----------

@app.get("/api/cases")
def list_cases(as_of: str | None = None) -> list[dict]:
    on = _d(as_of)
    out = []
    for rec in store.all_cases():
        ws = worksheet(rec.case, on)
        status = {"meets": "meets", "conditional": "conditional", "does_not_meet": "at_risk",
                  "insufficient_evidence": "insufficient_evidence"}[ws.overall]
        out.append({
            "id": rec.case.id, "client_name": rec.client_name, "event": rec.case.event,
            "event_date": rec.case.event_date.isoformat(),
            "cure_deadline": ws.cure_deadline.isoformat() if ws.cure_deadline else None,
            "days_left": (ws.cure_deadline - on).days if ws.cure_deadline else None,
            "status": status,
            "possible_exemptions": len(ws.exemptions), "flags": rec.flags, "synthetic": rec.synthetic,
        })
    return sorted(out, key=lambda c: (c["days_left"] is None, c["days_left"] or 0))


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, as_of: str | None = None) -> dict:
    try:
        rec = store.load(case_id)
    except FileNotFoundError:
        raise HTTPException(404, "case not found")
    return {"record": json.loads(rec.model_dump_json()), "worksheet": _ws(rec, _d(as_of))}


class DocIn(BaseModel):
    name: str
    kind: str  # notice | income
    member_id: str | None = None
    text: str


@app.post("/api/cases/{case_id}/documents")
def add_document(case_id: str, doc: DocIn, req: Request) -> dict:
    _rate_limit(req)
    if len(doc.text) > 20000:
        raise HTTPException(413, "Document too long for the demo (20,000 characters max).")
    return _llm_guard(lambda: _add_document(case_id, doc))


def _add_document(case_id: str, doc: DocIn) -> dict:
    rec = store.load(case_id)
    did = f"doc-{uuid.uuid4().hex[:6]}"
    d = store.Document(id=did, name=doc.name, kind=doc.kind, member_id=doc.member_id, text=doc.text)
    if doc.kind == "notice":
        n = extract.notice(doc.text)
        d.extracted = json.loads(n.model_dump_json())
        rec.notice = d.extracted
        if n.notice_date:
            rec.case.notice_date = n.notice_date
    else:
        mid = doc.member_id or rec.case.client_id
        parsed, entries, problems = extract.income_doc(doc.text, did, mid)
        d.extracted = json.loads(parsed.model_dump_json())
        d.problems = problems
        rec.case.ledger = [e for e in rec.case.ledger if not (e.source and e.source.doc_id == did)] + entries
    rec.documents.append(d)
    store.save(rec)
    return {"document": json.loads(d.model_dump_json()), "worksheet": _ws(rec, date.today())}


@app.post("/api/cases/{case_id}/explain")
def explain(case_id: str, lang: str = "en") -> dict:
    return _llm_guard(lambda: _explain(case_id, lang))


def _explain(case_id: str, lang: str = "en") -> dict:
    rec = store.load(case_id)
    notice_doc = next((d for d in rec.documents if d.kind == "notice"), None)
    if not notice_doc:
        raise HTTPException(404, "no notice on this case")
    cache = (notice_doc.extracted or {}).get("explanations", {})
    if lang not in cache:
        ex, missing = extract.explain_notice(notice_doc.text, lang)
        cache[lang] = json.loads(ex.model_dump_json()) | {"unverified_spans": len(missing)}
        notice_doc.extracted = (notice_doc.extracted or {}) | {"explanations": cache}
        store.save(rec)
    return cache[lang]


# ---------- grounded answers ----------

class AskIn(BaseModel):
    question: str
    jurisdiction: str = "NE"
    as_of: str | None = None
    compare_closed_book: bool = False


@app.post("/api/ask")
def ask(q: AskIn, req: Request) -> dict:
    on = _d(q.as_of)
    if len(q.question) > 600:
        raise HTTPException(413, "Question too long (600 characters max).")
    key = _cache_key("ask", q.question, q.jurisdiction, on.isoformat(), q.compare_closed_book)
    hit = _cache_get(key)
    if hit:
        return hit | {"cached": True}
    _rate_limit(req)

    def run() -> dict:
        res = answer_mod.answer(q.question, q.jurisdiction, on)
        out = {"grounded": json.loads(res.model_dump_json())}
        if q.compare_closed_book:
            # the frozen answer does not depend on the date: share it across dates
            fk = _cache_key("frozen", q.question, q.jurisdiction)
            frozen = _cache_get(fk)
            if not frozen:
                frozen = {"text": answer_mod.closed_book(q.question, q.jurisdiction)}
                _cache_put(fk, frozen)
            out["closed_book"] = frozen["text"]
        _cache_put(key, out)
        return out

    return _llm_guard(run)


# ---------- rules, sources, time machine ----------

@app.get("/api/facts")
def facts(as_of: str | None = None, jurisdiction: str = "NE") -> list[dict]:
    on = _d(as_of)
    return [
        {**{k: (v.isoformat() if isinstance(v, date) else v) for k, v in asdict(f).items() if k != "citations"},
         "citations": [asdict(c) for c in f.citations]}
        for f in rules.facts_known(on, {"US", jurisdiction})
    ]


@app.get("/api/sources")
def list_sources(as_of: str | None = None, jurisdiction: str | None = None) -> list[dict]:
    on = _d(as_of)
    js = {"US", jurisdiction} if jurisdiction else None
    return [{"id": s.id, "jurisdiction": s.jurisdiction, "title": s.title, "url": s.url, "wayback_url": s.wayback_url,
             "as_of": s.as_of.isoformat()} for s in sources.sources_as_of(on, js)]


@app.get("/api/sources/{source_id}/locate")
def locate(source_id: str, quote: str) -> dict:
    ctx = sources.locate(source_id, quote)
    if ctx is None:
        raise HTTPException(404, "quote not found in source")
    s = sources.get(source_id)
    return {"context": ctx, "title": s.title, "url": s.wayback_url or s.url, "as_of": s.as_of.isoformat()}


@app.get("/api/timeline")
def timeline(jurisdiction: str = "NE") -> dict:
    """Dates where the rule picture changes: facts taking effect or first being published, and snapshot diffs."""
    events: dict[str, dict] = {}
    for f in rules.all_facts():
        if f.jurisdiction not in ("US", jurisdiction):
            continue
        for kind, d in (("effective", f.effective_from), ("published", f.known_from), ("ended", f.effective_to)):
            if d:
                e = events.setdefault(d.isoformat(), {"date": d.isoformat(), "facts": []})
                e["facts"].append({"id": f.id, "kind": kind, "statement": f.statement})
    diffs = []
    for p in watch.allowlist():
        if p["jurisdiction"] in ("US", jurisdiction):
            for ev in watch.replay(p["url"]):
                diffs.append({k: v for k, v in asdict(ev).items() if k not in ("added", "removed")} |
                             {"added": ev.added[:20], "removed": ev.removed[:20]})
    return {"dates": sorted(events.values(), key=lambda e: e["date"]), "snapshot_changes": diffs}


@app.get("/api/drift/events")
def drift_events() -> list[dict]:
    if not watch.EVENTS.exists():
        return []
    return [json.loads(line) for line in watch.EVENTS.read_text().splitlines() if line.strip()]


@app.post("/api/drift/check")
def drift_check(req: Request) -> list[dict]:
    if not config.ADMIN_TOKEN or req.headers.get("x-admin-token") != config.ADMIN_TOKEN:
        raise HTTPException(403, "Live checks are run by the maintainer (they use Tavily credits).")
    if not config.TAVILY_API_KEY:
        raise HTTPException(400, "TAVILY_API_KEY not set")
    if config.ON_VERCEL:
        raise HTTPException(501, "Live snapshots are written to the repository; run drift-watch from the maintainer's machine or CI.")
    out = []
    for e in watch.check_live():
        out.append(asdict(e) | {"affected_cases": watch.flag_cases(e)})
    return out


@app.get("/api/drift/replay")
def drift_replay(jurisdiction: str = "NE") -> list[dict]:
    # summaries come from the committed cache; visitors never trigger new summary calls
    return watch.replay_all(jurisdiction, summarise=True, allow_llm=False)


# ---------- under the hood ----------

def _tail(p, n: int) -> list[dict]:
    if not p.exists():
        return []
    lines = p.read_text().splitlines()[-n:]
    return [json.loads(x) for x in lines if x.strip()]


@app.get("/api/log/calls")
def log_calls(n: int = 200) -> list[dict]:
    from .llm import CALL_LOG
    return _tail(CALL_LOG, n)


@app.get("/api/log/summary")
def log_summary() -> dict:
    p = config.ROOT / "data" / "cache" / "usage_summary.json"
    return json.loads(p.read_text()) if p.exists() else {}


@app.get("/api/log/tavily")
def log_tavily(n: int = 200) -> list[dict]:
    return _tail(watch.TAVILY_LOG, n)


@app.get("/api/bench/results")
def bench_results() -> dict:
    p = config.BENCH_DIR / "results" / "latest.json"
    return json.loads(p.read_text()) if p.exists() else {}


@app.get("/api/cases/{case_id}/mltc118")
def mltc118_plan(case_id: str, as_of: str | None = None) -> dict:
    from dataclasses import asdict as _a

    from .forms import FORM_ID, plan
    rec = store.load(case_id)
    return {"form": FORM_ID, "fields": [_a(f) for f in plan(rec, worksheet(rec.case, _d(as_of)))]}


@app.get("/api/cases/{case_id}/mltc118.pdf")
def mltc118_pdf(case_id: str, as_of: str | None = None) -> Response:
    from .forms import fill
    rec = store.load(case_id)
    pdf, _ = fill(rec, worksheet(rec.case, _d(as_of)))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="MLTC-118-draft-{case_id}.pdf"'})


@app.get("/api/cases/{case_id}/packet.pdf")
def packet(case_id: str, as_of: str | None = None) -> Response:
    from .packet import build_packet

    rec = store.load(case_id)
    pdf = build_packet(rec, worksheet(rec.case, _d(as_of)))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="staycovered-{case_id}.pdf"'})


@app.get("/api/extraction/results")
def extraction_results() -> dict:
    out = {}
    for name in ("results.json", "results_heldout.json"):
        p = config.BENCH_DIR / "extraction" / name
        if p.exists():
            out[name.replace(".json", "")] = {k: v for k, v in json.loads(p.read_text()).items() if k != "rows"}
    return out


# ---------- human grading of the benchmark judge (blind) ----------
_GRADE = config.BENCH_DIR / "results" / "grade_me.csv"


@app.get("/api/grade/items")
def grade_items() -> list[dict]:
    import csv
    if config.ON_VERCEL or not _GRADE.exists():  # local-only tool
        return []
    return [{k: v for k, v in r.items()} for r in csv.DictReader(_GRADE.open())]


class GradeIn(BaseModel):
    human_pass: str  # "y" | "n" | ""


@app.post("/api/grade/{row}")
def grade_row(row: str, g: GradeIn) -> dict:
    import csv
    if config.ON_VERCEL:
        raise HTTPException(403, "Grading is a local-only tool.")
    rows = list(csv.DictReader(_GRADE.open()))
    if g.human_pass not in ("y", "n", ""):
        raise HTTPException(400, "y or n")
    for r in rows:
        if r["row"] == row:
            r["human_pass"] = g.human_pass
    with _GRADE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return {"done": sum(1 for r in rows if r["human_pass"]), "total": len(rows)}


# ---------- serve the built web app (single-service deploy) ----------
_DIST = config.ROOT / "web" / "dist"
if _DIST.exists():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        f = _DIST / path
        return FileResponse(f if path and f.is_file() else _DIST / "index.html")
