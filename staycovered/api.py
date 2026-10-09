"""FastAPI backend for the StayCovered web app."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from . import answer as answer_mod
from . import config, extract, rules, sources, store
from .drift import watch
from .engine.compute import worksheet

app = FastAPI(title="StayCovered API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _d(s: str | None) -> date:
    return date.fromisoformat(s) if s else date.today()


def _ws(rec: store.CaseRecord, on: date) -> dict:
    return asdict(worksheet(rec.case, on))


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "nebius": bool(config.NEBIUS_API_KEY), "tavily": bool(config.TAVILY_API_KEY),
            "sources": len(sources.all_sources()), "facts": len(rules.all_facts())}


# ---------- cases ----------

@app.get("/api/cases")
def list_cases(as_of: str | None = None) -> list[dict]:
    on = _d(as_of)
    out = []
    for rec in store.all_cases():
        ws = worksheet(rec.case, on)
        statuses = [r.status for r in ws.results]
        out.append({
            "id": rec.case.id, "client_name": rec.client_name, "event": rec.case.event,
            "event_date": rec.case.event_date.isoformat(),
            "cure_deadline": ws.cure_deadline.isoformat() if ws.cure_deadline else None,
            "days_left": (ws.cure_deadline - on).days if ws.cure_deadline else None,
            "status": "meets" if statuses and all(s == "meets" for s in statuses) else
                      ("insufficient_evidence" if "insufficient_evidence" in statuses else
                       "depends_on_expenses" if "does_not_meet" not in statuses else "at_risk"),
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
def add_document(case_id: str, doc: DocIn) -> dict:
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


# ---------- grounded answers ----------

class AskIn(BaseModel):
    question: str
    jurisdiction: str = "NE"
    as_of: str | None = None
    compare_closed_book: bool = False


@app.post("/api/ask")
def ask(q: AskIn) -> dict:
    on = _d(q.as_of)
    res = answer_mod.answer(q.question, q.jurisdiction, on)
    out = {"grounded": json.loads(res.model_dump_json())}
    if q.compare_closed_book:
        out["closed_book"] = answer_mod.closed_book(q.question, q.jurisdiction)
    return out


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
def drift_check() -> list[dict]:
    if not config.TAVILY_API_KEY:
        raise HTTPException(400, "TAVILY_API_KEY not set")
    out = []
    for e in watch.check_live():
        out.append(asdict(e) | {"affected_cases": watch.flag_cases(e)})
    return out


@app.get("/api/drift/replay")
def drift_replay(jurisdiction: str = "NE", summarise: bool = True) -> list[dict]:
    return watch.replay_all(jurisdiction, summarise=summarise)


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


@app.get("/api/log/tavily")
def log_tavily(n: int = 200) -> list[dict]:
    return _tail(watch.TAVILY_LOG, n)


@app.get("/api/bench/results")
def bench_results() -> dict:
    p = config.BENCH_DIR / "results" / "latest.json"
    return json.loads(p.read_text()) if p.exists() else {}


@app.get("/api/cases/{case_id}/packet.pdf")
def packet(case_id: str, as_of: str | None = None) -> Response:
    from .packet import build_packet

    rec = store.load(case_id)
    pdf = build_packet(rec, worksheet(rec.case, _d(as_of)))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="staycovered-{case_id}.pdf"'})
