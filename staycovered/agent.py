"""The StayCovered agent: one case, end to end, as a chain of visible steps.

notice -> plain-language explanation -> documents -> rules as of the date -> smallest proven fix -> 12-month
forecast -> nearby programs -> key rule checked against official text -> client message -> packet.

Each step reports which model (or plain code) did the work, its tokens, cost and time. A step whose inputs are
unchanged is served from the recorded run (marked cached, with the original metrics); a case a visitor has
changed runs live. Numbers in the client message are checked against the worksheet before it is shown.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict
from datetime import date

from pydantic import BaseModel, Field

from . import config, extract, llm, store
from .engine.compute import worksheet
from .engine.forecast import forecast
from .engine.paths import month_paths

CACHE = config.ROOT / "data" / "cache" / "agent_runs.json"   # committed, recorded runs for the demo cases
RUNTIME = config.RUNTIME_DIR / "agent_runs.json"

NANO, SUPER = "Nemotron Nano", "Nemotron Super"
STEPS = [
    ("read_notice", "Read the state's notice", [NANO]),
    ("explain", "Explain it in the client's language", [NANO]),
    ("read_documents", "Read the client's documents", [NANO]),
    ("apply_rules", "Apply the rules in force on the date", ["Rules engine (code)"]),
    ("find_fixes", "Search for the smallest proven fix", ["Rules engine (code)"]),
    ("forecast", "Forecast the next 12 months", ["Rules engine (code)"]),
    ("nearby", "Find places nearby to earn hours", ["Tavily Search", SUPER]),
    ("verify_rule", "Check the key rule against official text", [SUPER, NANO]),
    ("draft_message", "Draft a message for the client", [SUPER]),
    ("package", "Assemble the packet, form and reminders", ["Code"]),
]
FRONTIER = ("a frontier API model", 4.0, 20.0)      # $/M in, $/M out (same price list as WorkReqBench)
ULTRA = config.ULTRA


def plan() -> list[dict]:
    return [{"n": i, "id": sid, "title": t, "actors": a} for i, (sid, t, a) in enumerate(STEPS)]


def _load(p) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _key(rec: store.CaseRecord, step: str) -> str:
    d = json.loads(rec.model_dump_json(exclude={"updated", "flags"}))
    for doc in d.get("documents", []):
        doc.pop("extracted", None)  # cached explanations etc. are outputs, not inputs
    return hashlib.sha256(json.dumps([d, step, config.DEMO_AS_OF.isoformat()], sort_keys=True).encode()).hexdigest()[:24]


def _metrics(calls: list, wall: float) -> dict:
    llm_calls = [c for c in calls if not str(c.get("model", "")).startswith("tavily/")]
    tav = [c for c in calls if str(c.get("model", "")).startswith("tavily/")]
    pin = sum(c.get("prompt_tokens") or 0 for c in llm_calls)
    pout = sum(c.get("completion_tokens") or 0 for c in llm_calls)
    models = sorted({c["model"].split("/")[-1] for c in llm_calls})
    return {"models": models, "llm_calls": len(llm_calls), "tavily_calls": len(tav), "prompt_tokens": pin, "completion_tokens": pout,
            "usd": round(sum(c.get("usd") or 0 for c in llm_calls), 6), "seconds": round(wall, 2),
            "ultra_usd": round((pin * ULTRA.usd_per_m_in + pout * ULTRA.usd_per_m_out) / 1e6, 6),
            "frontier_usd": round((pin * FRONTIER[1] + pout * FRONTIER[2]) / 1e6, 6)}


# ---------------------------------------------------------------- steps

def _notice_doc(rec):
    return next((d for d in rec.documents if d.kind == "notice"), None)


def _s_read_notice(rec, on):
    d = _notice_doc(rec)
    if not d:
        return {"skipped": "No state notice on file for this case."}
    n = extract.notice(d.text)
    spans = list(n.spans.values())
    ok = sum(1 for s in spans if s and s.lower() in d.text.lower())
    return {"headline": f"{n.notice_type.replace('_', ' ').capitalize()} notice about {', '.join(n.months_in_question) or 'no month named'}",
            "details": [f"Respond by: {n.respond_by or 'not stated'}", f"Asks for: {'; '.join(n.requested_items[:2])}",
                        f"{ok} of {len(spans)} supporting phrases found word for word in the letter"]}


def _s_explain(rec, on):
    d = _notice_doc(rec)
    if not d:
        return {"skipped": "No notice to explain."}
    lang = "es" if rec.language == "es" else "en"
    ex, missing = extract.explain_notice(d.text, lang)
    return {"headline": ex.summary, "details": ex.what_to_do[:3] + [f"{len(ex.spans)} phrases tied to the letter, {len(missing)} dropped"],
            "language": lang}


def _s_read_documents(rec, on):
    docs = [d for d in rec.documents if d.kind in ("income", "activity")]
    if not docs:
        return {"skipped": "No income or activity documents yet."}
    details, total, matched = [], 0, 0
    for d in docs:
        _doc, entries, problems = extract.income_doc(d.text, d.id, d.member_id or rec.case.client_id)
        reviewed = [e for e in rec.case.ledger if e.source and e.source.doc_id == d.id]
        hit = sum(1 for e in entries if any(r.kind == e.kind and r.period_start == e.period_start and r.period_end == e.period_end
                                              and abs(r.amount - e.amount) <= max(0.01, 0.01 * abs(r.amount)) for r in reviewed))
        total += len(reviewed)
        matched += min(hit, len(reviewed))
        details.append(f"{d.name}: {len(entries)} numbers read, each with its exact line" + (f"; {len(problems)} flagged" if problems else ""))
    head = (f"{matched} of {total} numbers match the reviewed ledger" + (f"; {total - matched} need a human look" if matched < total else "")
            if total else f"Read {len(docs)} document{'s' if len(docs) != 1 else ''}")
    return {"headline": head,
            "details": details}


def _ws(rec, on):
    return worksheet(rec.case, on)


def _s_apply_rules(rec, on):
    ws = _ws(rec, on)
    words = {"meets": "meets the requirement", "conditional": "meets it only if a condition holds", "does_not_meet": "falls short",
             "insufficient_evidence": "has no evidence yet"}
    r = ws.results[-1]
    det = [f"Review: {ws.review}", f"{r.month}: {r.activity_hours:g} of {ws.params['monthly_hours']['value']} hours, "
           f"${r.own_income + r.own_gross_self_employment:,.2f} of ${r.income_threshold:,.0f} income"]
    det += [f"Condition: {c}" for c in r.conditions[:1]]
    det += [f"Possible exemption: {e.label}" for e in ws.exemptions[:1]]
    return {"headline": f"{rec.client_name.split()[0]} {words[ws.overall]}", "details": det, "status": ws.overall}


def _s_find_fixes(rec, on):
    ws = _ws(rec, on)
    paths = [p for r in ws.results for p in month_paths(rec.case, r, on)]
    if not paths:
        return {"headline": "Nothing to fix: the documented month already qualifies.", "details": []}
    proven = [p for p in paths if p.proven]
    return {"headline": proven[0].title if proven else paths[0].title,
            "details": [p.title for p in (proven[1:3] if proven else paths[1:3])] + [f"{len(proven)} fixes proven by re-running the rules"]}


def _s_forecast(rec, on):
    f = forecast(rec.case, on)
    return {"headline": f.headline, "details": [f"First month at risk: {f.first_risk or 'none'}"],
            "months": [{"month": m.month, "status": m.status} for m in f.months]}


def _s_nearby(rec, on):
    from . import nearby

    ws = _ws(rec, on)
    needs_hours = any(p.kind == "hours" for r in ws.results for p in month_paths(rec.case, r, on))
    if not needs_hours or not rec.case.location:
        return {"skipped": "No extra hours needed, so no search." if not needs_hours else "No city on file."}
    reused = nearby.cached(rec.case.location, "work_program") is not None
    r = nearby.find(rec.case.location, "work_program")
    return {"headline": f"{len(r['options'])} job-training programs near {rec.case.location}", "details": [o["name"] for o in r["options"][:3]]
            + [f"Sent to search: {r['sent_to_search']}"], "reused": f"Search results reused from {r['as_of']} for this city" if reused else None}


KEY_QUESTION = {
    ("NE", True): "How long does my client have to respond to a noncompliance notice?",
    ("NE", False): "Does my client's spouse's income count toward the $580?",
    ("MT", True): "How many qualifying months does my client need at redetermination?",
    ("MT", False): "How many qualifying months does my client need at redetermination?",
}


def _s_verify_rule(rec, on):
    from .api import ask_cached

    q = KEY_QUESTION[(rec.case.jurisdiction, rec.case.event == "noncompliance_notice")]
    out = ask_cached(q, rec.case.jurisdiction, on)
    g = out["grounded"]
    n = len(g["citations"])
    return {"headline": g["answer"], "question": q,
            "reused": "Answer reused: the same official rules were in force when it was first checked" if out.get("cached") else None,
            "details": [f"Evidence check: {n + g['dropped_citations']} quotes proposed, {n} verified word for word, {g['dropped_citations']} dropped"]
            + [f"Source: {c['title']} ({c['as_of']})" for c in g["citations"][:2]]}


class ClientMessage(BaseModel):
    sms: str = Field(description="A short text message to the client, 320 characters or less")
    next_steps: list[str] = Field(description="2-3 very short steps")


MSG_SYS = """You write a short, warm text message from a Medicaid navigator to a client, in {lang}.
Use ONLY the facts provided. Copy every number, amount and date exactly as given. Do not add rules or promises.
Plain words, about a 6th-grade reading level. 320 characters or less for the message."""
_NUM = re.compile(r"\$?\d[\d,]*(?:\.\d+)?")


def _s_draft_message(rec, on):
    ws = _ws(rec, on)
    paths = [p for r in ws.results for p in month_paths(rec.case, r, on) if p.proven]
    lang = "Spanish" if rec.language == "es" else "English"
    status_text = {"meets": "meets the work requirement for the month in question",
                   "conditional": "can meet the requirement if one thing is shown",
                   "does_not_meet": "is a little short of the requirement right now",
                   "insufficient_evidence": "needs to send proof or ask about an exemption"}[ws.overall]
    facts = {"first_name": rec.client_name.split()[0], "situation": status_text,
             "respond_by": f"{ws.cure_deadline:%B} {ws.cure_deadline.day}, {ws.cure_deadline.year}" if ws.cure_deadline else None,
             "smallest_fix": paths[0].title if paths else None,
             "documents_to_send": [p.detail for p in paths[:1]], "agency_phone": "1-855-632-7633" if rec.case.jurisdiction == "NE" else "1-888-706-1535"}
    m = llm.structured("answer", MSG_SYS.format(lang=lang), json.dumps(facts), ClientMessage, tag="agent_message", max_tokens=1500)
    clean = lambda xs: [x.rstrip(",").lstrip("$") for x in xs]  # noqa: E731
    allowed = set(clean(_NUM.findall(json.dumps(facts))))
    used = clean(_NUM.findall(m.sms + " " + " ".join(m.next_steps)))
    bad = [u for u in used if u not in allowed]
    return {"headline": m.sms, "details": m.next_steps + [f"Numbers checked against the worksheet: {len(used) - len(bad)} of {len(used)} match"
                                                          + (f" ({', '.join(bad)} need review)" if bad else "")], "language": lang}


def _s_package(rec, on):
    cid = rec.case.id
    links = [{"label": "Evidence packet (PDF)", "href": f"/api/cases/{cid}/packet.pdf"},
             {"label": "Calendar reminders (.ics)", "href": f"/api/cases/{cid}/reminders.ics"}]
    if rec.case.jurisdiction == "NE":
        links.insert(1, {"label": "Nebraska MLTC-118, pre-filled (PDF)", "href": f"/api/cases/{cid}/mltc118.pdf"})
    return {"headline": "Packet, state form and reminders are ready", "details": [], "links": links}


RUN = {"read_notice": _s_read_notice, "explain": _s_explain, "read_documents": _s_read_documents, "apply_rules": _s_apply_rules,
       "find_fixes": _s_find_fixes, "forecast": _s_forecast, "nearby": _s_nearby, "verify_rule": _s_verify_rule,
       "draft_message": _s_draft_message, "package": _s_package}


def run_step(case_id: str, n: int, live: bool = False, write_cache: bool = False) -> dict:
    sid, title, actors = STEPS[n]
    rec = store.load(case_id)
    on = config.DEMO_AS_OF
    key = _key(rec, sid)
    if not live:
        hit = _load(RUNTIME).get(key) or _load(CACHE).get(key)
        if hit:
            return hit | {"cached": True}
    t0 = time.time()
    with llm.collect() as calls:
        out = RUN[sid](rec, on)
    res = {"n": n, "id": sid, "title": title, "actors": actors, "output": out, "metrics": _metrics(calls, time.time() - t0),
           "ran_at": date.today().isoformat()}
    target = CACHE if write_cache else RUNTIME
    d = _load(target)
    d[key] = res
    target.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return res | {"cached": False}


def receipt(steps: list[dict]) -> dict:
    tot = {k: round(sum(s["metrics"][k] for s in steps), 6) for k in ("usd", "ultra_usd", "frontier_usd", "prompt_tokens", "completion_tokens", "seconds")}
    tot["llm_calls"] = sum(s["metrics"]["llm_calls"] for s in steps)
    tot["tavily_calls"] = sum(s["metrics"]["tavily_calls"] for s in steps)
    tot["frontier_name"] = FRONTIER[0]
    return tot


__all__ = ["plan", "run_step", "receipt", "asdict"]
