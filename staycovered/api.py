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
def list_cases(as_of: str | None = None, jurisdiction: str | None = None) -> list[dict]:
    on = _d(as_of)
    out = []
    for rec in store.all_cases():
        if jurisdiction and rec.case.jurisdiction != jurisdiction:
            continue
        ws = worksheet(rec.case, on)
        status = {"meets": "meets", "conditional": "conditional", "does_not_meet": "at_risk",
                  "insufficient_evidence": "insufficient_evidence"}[ws.overall]
        out.append({
            "id": rec.case.id, "client_name": rec.client_name, "event": rec.case.event, "jurisdiction": rec.case.jurisdiction,
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
    # historical changes (archived snapshots) + changes found by the scheduled live check; all summaries are committed,
    # so visitors never trigger model calls here
    hist = watch.replay_all(jurisdiction, summarise=True, allow_llm=False)
    live = [e | {"live": True} for e in watch.live_events() if e["jurisdiction"] in (jurisdiction, "US")]
    return sorted(hist + live, key=lambda e: e["new_as_of"])


@app.get("/api/drift/status")
def drift_status() -> dict:
    return watch.live_status()


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


# ---------- paths to stay covered + coverage forecast ----------

@app.get("/api/cases/{case_id}/plan")
def case_plan(case_id: str, as_of: str | None = None) -> dict:
    from .engine.forecast import forecast
    from .engine.paths import month_paths

    rec = store.load(case_id)
    on = _d(as_of)
    ws = worksheet(rec.case, on)
    return {"paths": [{"month": r.month, "status": r.status, "paths": [asdict(x) for x in month_paths(rec.case, r, on)]}
                      for r in ws.results if r.status != "meets"],
            "forecast": asdict(forecast(rec.case, on)), "location": rec.case.location}


from .selfcheck import SelfCheckIn  # noqa: E402


@app.post("/api/selfcheck")
def selfcheck(x: SelfCheckIn) -> dict:
    """Anonymous, deterministic, nothing stored: the person's usual month against the published rules."""
    from . import selfcheck as sc
    return sc.run(x)


@app.get("/api/nearby")
def nearby_city(location: str, kind: str, req: Request) -> dict:
    from . import nearby

    if kind not in nearby.QUERIES:
        raise HTTPException(400, "kind must be volunteer or work_program")
    try:
        if (hit := nearby.cached(location, kind)) is not None:
            return hit
        _rate_limit(req)
        if not config.TAVILY_API_KEY:
            raise HTTPException(503, "Search is not configured on this deployment.")
        return _llm_guard(lambda: nearby.find(location, kind))  # type: ignore[arg-type]
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/sandbox")
def policy_sandbox(jurisdiction: str = "NE", income_to_hours: bool | None = None, household_income: bool | None = None,
                   required_months: int | None = None, ex_parte: bool | None = None, as_of: str | None = None) -> dict:
    """What if the state chose differently? Deterministic; no AI call."""
    from . import sandbox

    if jurisdiction not in ("NE", "MT"):
        raise HTTPException(400, "jurisdiction must be NE or MT")
    if required_months is not None and required_months not in (1, 2, 3):
        raise HTTPException(400, "required_months must be 1, 2 or 3")
    lv = {k: v for k, v in {"income_to_hours": income_to_hours, "household_income": household_income,
                            "required_months": required_months, "ex_parte": ex_parte}.items() if v is not None}
    return sandbox.run(jurisdiction, lv, _d(as_of))


@app.get("/api/forecast")
def caseload_forecast(jurisdiction: str = "NE", as_of: str | None = None) -> dict:
    from .engine.forecast import forecast

    on = _d(as_of)
    rows, changes = [], {}
    for rec in store.all_cases():
        if rec.case.jurisdiction != jurisdiction:
            continue
        f = forecast(rec.case, on)
        rows.append({"id": rec.case.id, "client_name": rec.client_name, "headline": f.headline, "first_risk": f.first_risk,
                     "months": [{"month": m.month, "status": m.status} for m in f.months]})
        for m in f.months:
            for c in m.changes:
                changes.setdefault((m.month, c.label), {"month": m.month, "label": c.label, "before": c.before, "after": c.after,
                                                         "fact_id": c.fact_id, "clients": []})["clients"].append(rec.client_name)
    rows.sort(key=lambda r: (r["first_risk"] is None, r["first_risk"] or "", r["client_name"]))
    months = rows[0]["months"] if rows else []
    return {"months": [m["month"] for m in months], "rows": rows, "changes": list(changes.values())}


@app.get("/api/cases/{case_id}/nearby")
def case_nearby(case_id: str, kind: str, req: Request) -> dict:
    from . import nearby

    if kind not in nearby.QUERIES:
        raise HTTPException(400, "kind must be volunteer or work_program")
    rec = store.load(case_id)
    if not rec.case.location:
        raise HTTPException(400, "This case has no city on file.")
    if (hit := nearby.cached(rec.case.location, kind)) is not None:
        return hit
    _rate_limit(req)
    if not config.TAVILY_API_KEY:
        raise HTTPException(503, "Search is not configured on this deployment.")
    return _llm_guard(lambda: nearby.find(rec.case.location, kind))  # type: ignore[arg-type]


def _ics_event(uid: str, day: date, title: str, desc: str, alarm_days: int | None = None) -> list[str]:
    esc = lambda t: t.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")  # noqa: E731
    ev = ["BEGIN:VEVENT", f"UID:{uid}@staycovered", f"DTSTAMP:{date.today():%Y%m%d}T000000Z",
          f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"SUMMARY:{esc(title)}", f"DESCRIPTION:{esc(desc)}"]
    if alarm_days:
        ev += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(title)}", f"TRIGGER:-P{alarm_days}D", "END:VALARM"]
    return ev + ["END:VEVENT"]


@app.get("/api/cases/{case_id}/reminders.ics")
def reminders(case_id: str, as_of: str | None = None) -> Response:
    """Calendar reminders for the client: the response deadline, renewal, monthly proof-keeping, and rule changes."""
    from .engine.compute import month_bounds
    from .engine.forecast import forecast

    rec = store.load(case_id)
    on = _d(as_of)
    ws = worksheet(rec.case, on)
    f = forecast(rec.case, on)
    first = rec.client_name.split()[0]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//StayCovered//Reminders//EN", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:Medicaid reminders ({first})"]
    if ws.cure_deadline and ws.cure_deadline >= on:
        lines += _ics_event(f"{case_id}-deadline", ws.cure_deadline, "Medicaid: answer the work-requirement notice TODAY",
                            "Send proof of hours or income, or ask about an exemption. Ask your navigator for help.", 7)
    if rec.case.event == "renewal" and rec.case.event_date >= on:
        lines += _ics_event(f"{case_id}-renewal", rec.case.event_date, "Medicaid renewal",
                            "Have pay stubs, volunteer letters or school letters ready.", 14)
    for last, m in zip(f.months[0:6], f.months[1:7]):
        ms = month_bounds(m.month)[0]
        prev = month_bounds(last.month)[0]
        note = "" if last.status == "meets" else (f" If {prev:%B} looked like your usual month, it falls short. Smallest fix: "
                                                  + (last.paths[0].title if last.paths else "talk to your navigator") + ".")
        lines += _ics_event(f"{case_id}-proof-{m.month}", ms, f"Medicaid: keep proof of {prev:%B} hours and income",
                            "Save pay stubs, gig statements and volunteer or school letters for last month." + note)
        for c in m.changes:
            lines += _ics_event(f"{case_id}-rule-{m.month}-{c.param}", ms, f"Medicaid rule change: {c.label}",
                                f"{c.before} -> {c.after}. Ask your navigator what this means for you.", 7)
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines) + "\r\n", media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="medicaid-reminders-{first.lower()}.ics"'})


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
