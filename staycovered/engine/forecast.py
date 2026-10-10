"""Coverage forecast: same life, changing rules.

Holds the client's most recent documented month constant and evaluates it under the rules in force in each of the
next twelve months. Any change in the outcome is caused by the rules alone, and each change names the rule fact
behind it. The Time Machine looks back; the forecast looks forward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .compute import _member_month, month_bounds, prev_months, worksheet
from .model import INCOME_KINDS, Case, Kind, LedgerEntry
from .params import resolve
from .paths import Path, _hourly_wage, month_paths

IGNORE_PARAMS = {"receipt_days", "cure_days"}


@dataclass
class RuleChange:
    param: str
    label: str
    before: object
    after: object
    fact_id: str | None


@dataclass
class ForecastMonth:
    month: str
    status: str
    path: str | None
    conditions: list[str]
    changes: list[RuleChange]
    paths: list[Path] = field(default_factory=list)


@dataclass
class Forecast:
    case_id: str
    jurisdiction: str
    from_month: str
    pattern_month: str | None
    pattern: list[dict]
    assumptions: list[str]
    months: list[ForecastMonth]
    headline: str
    first_risk: str | None


def _next_months(today: date, n: int) -> list[str]:
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _fmt(v: object) -> str:
    return {"own": "client's own", "household": "whole household", "own_plus_maybe_household": "own (household may count)",
            True: "yes", False: "no"}.get(v, str(v)) if isinstance(v, (str, bool)) else str(v)


def _relevant(name: str, before: object, after: object, student: bool, household: bool) -> bool:
    if name in IGNORE_PARAMS or before == after:
        return False
    if name in ("income_basis", "partial_credit_own_income") and not household:
        return False
    if name in ("credit_hour_hours", "half_time_credits") and not student:
        return False
    if isinstance(before, (int, float)) and isinstance(after, (int, float)) and not isinstance(before, bool):
        return abs(after - before) > 0.01 * max(abs(before), 1)  # rounding differences between sources are not changes
    return True


def _long(key: str) -> str:
    return date.fromisoformat(key + "-01").strftime("%B %Y")


def _label(key: str) -> str:
    return date.fromisoformat(key + "-01").strftime("%b %Y")


def forecast(case: Case, today: date | None = None, n: int = 12) -> Forecast:
    today = today or date.today()
    client = next(m for m in case.household if m.id == case.client_id)
    ws = worksheet(case, today)
    with_evidence = [r for r in ws.results if r.contributions]
    months = _next_months(today, n)
    if not with_evidence:
        return Forecast(case.id, case.jurisdiction, months[0], None, [], [], [], "No documented month to project yet. "
                        "Start with the paths below: proof for the month in question, or an exemption.", None)

    pm = with_evidence[-1].month
    assumptions = [f"{client.name.split()[0]}'s life stays exactly as documented for {_label(pm)}: same hours, same income."]
    # One entry per (member, kind) holding what counted in the pattern month.
    agg: dict[tuple[str, Kind], float] = {}
    for c in with_evidence[-1].contributions:
        k = (c.member_id, Kind(c.kind))
        agg[k] = agg.get(k, 0.0) + c.amount
    if client.seasonal_worker:
        p0 = resolve(case.jurisdiction, today)
        window = prev_months(today, int(p0["seasonal_months"]))
        tot = sum(_member_month(case, client, k, p0).own_income for k in window)
        agg = {key: v for key, v in agg.items() if key[1] not in INCOME_KINDS}
        agg[(client.id, Kind.EARNED_INCOME)] = round(tot / len(window), 2)
        assumptions.append(f"Seasonal worker: income projected at the {len(window)}-month average (${tot / len(window):,.2f}/month).")
    if any(k == Kind.EDUCATION_CREDIT_HOURS for _m, k in agg):
        assumptions.append("Still enrolled in the same number of credit hours.")
        # credit entries were already converted to hours in the pattern month; project the credits themselves
        for e in case.ledger:
            if e.kind == Kind.EDUCATION_CREDIT_HOURS and e.member_id == client.id:
                agg[(e.member_id, e.kind)] = e.amount
    pattern = [{"member_id": m, "kind": k.value, "amount": round(v, 2)} for (m, k), v in agg.items()]

    wage = _hourly_wage(with_evidence[-1])
    student = any(k == Kind.EDUCATION_CREDIT_HOURS for _m, k in agg)
    out: list[ForecastMonth] = []
    prev = resolve(case.jurisdiction, month_bounds(months[0])[0])
    for key in months:
        ms, me = month_bounds(key)
        p = resolve(case.jurisdiction, ms)
        ledger = [LedgerEntry(id=f"proj-{key}-{i}", member_id=m, kind=k, period_start=ms, period_end=me, amount=v)
                  for i, ((m, k), v) in enumerate(agg.items())]
        proj = case.model_copy(update={"ledger": ledger, "months_in_question": [key]})
        r = _member_month(proj, client, key, p)
        changes = [RuleChange(name, p.values[name].label, _fmt(prev[name]), _fmt(p[name]), p.values[name].fact_id)
                   for name in p.values if _relevant(name, prev[name], p[name], student, len(case.household) > 1)]
        fm = ForecastMonth(key, r.status, r.path, r.conditions, changes)
        if r.status != "meets":
            fm.paths = [x for x in month_paths(proj, r, today, wage) if x.kind != "ask_exemption"]
        out.append(fm)
        prev = p

    risky = [m for m in out if m.status != "meets"]
    first_risk = risky[0].month if risky else None
    flips = [m for i, m in enumerate(out) if i and m.status != out[i - 1].status]
    name = client.name.split()[0]
    if not risky:
        headline = f"If nothing changes, {name} stays covered through {_label(out[-1].month)}."
    elif len(risky) == len(out) and all(m.status == "conditional" for m in out):
        headline = (f"If nothing changes, every month for {name} depends on the same thing: "
                    f"{out[0].conditions[0].split(' (')[0].lower() if out[0].conditions else 'an agency decision'}. "
                    "Settling it once settles the pattern.")
    elif len(risky) == len(out):
        opts = [x.title for x in out[0].paths if x.kind in ("income", "hours")]
        opts.sort(key=lambda t: "paid hours" not in t)  # a few more paid hours beats many unpaid ones
        fix = " or ".join(o[0].lower() + o[1:].replace(f" in {_long(out[0].month)}", "") for o in opts[:2])
        headline = f"If nothing changes, {name} falls short every month. Smallest fix, each month: {fix or 'see the paths'}."
    else:
        f = flips[0]
        why = f.changes[0].label.lower() if f.changes else "the rules change"
        verb = "starts to qualify clearly" if f.status == "meets" else "stops qualifying clearly"
        headline = f"Same life, different rules: {name} {verb} in {_label(f.month)}, because {why} changes."
    return Forecast(case.id, case.jurisdiction, months[0], pm, pattern, assumptions, out, headline, first_risk)
