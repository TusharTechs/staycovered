"""Policy sandbox: flip a state option the federal rule allows and watch the caseload change.

Each lever is a state policy choice cited to the federal rule (three are state options; ex parte exemption checks
are required from 2027 and can start sooner), applied over the state's published rules with
the same deterministic engine, worksheet and forecast. Outcomes separate people who fall short from people who
are at risk only for paperwork, the distinction that drove coverage losses in earlier work-requirement programs.
Illustrative: the demo caseload is a handful of synthetic clients, not a population estimate.
"""

from __future__ import annotations

from datetime import date

from . import rules, store
from .engine.compute import _member_month, _review, screen_exemptions
from .engine.forecast import forecast
from .engine.params import Param, overrides, resolve

LEVERS = [
    {"key": "income_to_hours", "label": "Count earnings toward the 80 hours",
     "help": "Earnings divided by the federal minimum wage ($7.25) count as hours, combined with volunteering, school or training. "
             "Paid work counts once: its documented hours or its converted earnings, whichever is larger.",
     "kind": "bool", "fact_id": "US.income_alternative.income_to_hours_option"},
    {"key": "household_income", "label": "Count the whole household's income now",
     "help": "Federal rules count household income from January 2027. A state can choose to start sooner.",
     "kind": "bool", "fact_id": "US.income_alternative.magi_household_income"},
    {"key": "required_months", "label": "Qualifying months needed at renewal",
     "help": "The federal rule lets each state require one or more months, consecutive or not, since the last renewal.",
     "kind": "choice", "options": [1, 2, 3], "fact_id": "US.lookback.renewal"},
    {"key": "ex_parte", "label": "Check exemptions from data the state already has",
     "help": "Use claims and other records to confirm an exemption before asking the person for paperwork. The federal "
             "rule requires this from January 2027; a state can start sooner. "
             "Assumes the state's data shows what the case file shows.",
     "kind": "bool", "fact_id": "US.verification.ex_parte_first"},
]

OUTCOMES = ["covered", "protected", "depends", "short", "paperwork"]


def defaults(jurisdiction: str, on: date) -> dict:
    p = resolve(jurisdiction, on)
    return {"income_to_hours": bool(p["income_to_hours"]), "household_income": p["income_basis"] == "household",
            "required_months": int(p["renewal_required_months"]), "ex_parte": False}


def _overrides(jurisdiction: str, on: date, lv: dict) -> dict[str, Param]:
    p = resolve(jurisdiction, on)
    out: dict[str, Param] = {}
    if lv["income_to_hours"] != bool(p["income_to_hours"]):
        out["income_to_hours"] = Param(lv["income_to_hours"], "US.income_alternative.income_to_hours_option", True, "sandbox")
    if lv["household_income"] and p["income_basis"] != "household":
        out["income_basis"] = Param("household", "US.income_alternative.magi_household_income", True, "sandbox")
    if int(lv["required_months"]) != int(p["renewal_required_months"]):
        out["renewal_required_months"] = Param(int(lv["required_months"]), "US.lookback.renewal", True, "sandbox")
    return out


def _classify(case, on: date, ex_parte: bool) -> tuple[str, str]:
    p = resolve(case.jurisdiction, on)
    months, required, _desc = _review(case, p)
    client = next(m for m in case.household if m.id == case.client_id)
    res = [_member_month(case, client, k, p) for k in months]
    n = {s: sum(r.status == s for r in res) for s in ("meets", "conditional", "does_not_meet", "insufficient_evidence")}
    req = required or len(months)
    exempt = screen_exemptions(case, on)
    if n["meets"] >= req:
        return "covered", _why_meets([r for r in res if r.status == "meets"][-1], n["meets"], req)
    if ex_parte and exempt:
        return "protected", f"exemption confirmed from state data: {exempt[0].label.lower()}"
    if n["meets"] + n["conditional"] >= req:
        return "depends", "qualifies only if the agency decides in the client's favour"
    if n["does_not_meet"] and not (n["meets"] + n["conditional"]):
        return "short", "documented months fall short of 80 hours and $580"
    missing = req - n["meets"] - n["conditional"]
    why = f"needs proof for {missing} more month(s)" if n["meets"] + n["conditional"] else "no proof on file yet"
    if exempt:
        why += f"; possible exemption ({exempt[0].label.lower()}) needs paperwork"
    return "paperwork", why


def _why_meets(r, have: int, req: int) -> str:
    how = {"hours": f"{r.activity_hours:g} activity hours",
           "income": f"${r.own_income + r.household_other_income:,.2f} income (${r.income_threshold:,.0f} needed)",
           "combined": f"{r.combined_hours:g} hours counting earnings as hours at $7.25 (80 needed)",
           "seasonal_average": f"seasonal average income ${r.seasonal_average_income or 0:,.2f}",
           "school_half_time": "half-time school"}.get(r.path or "", r.path or "")
    when = date.fromisoformat(r.month + "-01").strftime("%b %Y")
    return f"{when}: {how}" + (f"; {have} qualifying months, {req} needed" if req > 1 else "")


def _evaluate(jurisdiction: str, on: date, lv: dict) -> list[dict]:
    out = []
    with overrides(_overrides(jurisdiction, on, lv)):
        for rec in store.all_cases():
            if rec.case.jurisdiction != jurisdiction:
                continue
            outcome, why = _classify(rec.case, on, lv["ex_parte"])
            f = forecast(rec.case, on)
            covered = 12 if outcome == "protected" else sum(m.status == "meets" for m in f.months)
            out.append({"id": rec.case.id, "client_name": rec.client_name, "outcome": outcome, "why": why,
                        "covered_months": covered, "months": [{"month": m.month, "status": m.status} for m in f.months]})
    return sorted(out, key=lambda c: c["client_name"])


def _totals(clients: list[dict]) -> dict:
    t = {o: sum(c["outcome"] == o for c in clients) for o in OUTCOMES}
    t["covered_months"] = sum(c["covered_months"] for c in clients)
    t["clients"] = len(clients)
    return t


def run(jurisdiction: str, levers: dict | None = None, on: date | None = None) -> dict:
    on = on or date.today()
    base_lv = defaults(jurisdiction, on)
    lv = base_lv | {k: v for k, v in (levers or {}).items() if k in base_lv}
    base, scen = _evaluate(jurisdiction, on, base_lv), _evaluate(jurisdiction, on, lv)
    b_by = {c["id"]: c for c in base}
    flips = [{"id": c["id"], "client_name": c["client_name"], "before": b_by[c["id"]]["outcome"], "after": c["outcome"],
              "why": c["why"], "months_delta": c["covered_months"] - b_by[c["id"]]["covered_months"]}
             for c in scen if c["outcome"] != b_by[c["id"]]["outcome"] or c["covered_months"] != b_by[c["id"]]["covered_months"]]
    facts = {f.id: f for f in rules.all_facts()}
    return {
        "jurisdiction": jurisdiction, "as_of": on.isoformat(),
        "levers": [lev | {"default": base_lv[lev["key"]], "value": lv[lev["key"]],
                          "quote": facts[lev["fact_id"]].citations[0].quote if lev["fact_id"] in facts else "",
                          "source_id": facts[lev["fact_id"]].citations[0].source_id if lev["fact_id"] in facts else ""}
                   for lev in LEVERS],
        "baseline": {"clients": base, "totals": _totals(base)},
        "scenario": {"clients": scen, "totals": _totals(scen)},
        "flips": flips,
    }
