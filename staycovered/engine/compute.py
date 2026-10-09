"""Deterministic compliance worksheet.

The LLM never does arithmetic. This module turns ledger rows into a month-by-month worksheet where
every number carries the ledger rows (and so the client-document spans) and the rule facts it used.
Outcomes are "meets" / "does_not_meet" / "insufficient_evidence" per month; exemptions are only ever
"possible — confirm with the agency".
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from .model import HOURS_KINDS, INCOME_KINDS, Case, Kind, LedgerEntry, Member
from .params import Params, resolve


@dataclass
class Contribution:
    entry_id: str
    member_id: str
    kind: str
    amount: float  # prorated amount counted in this month
    share: float  # fraction of the entry's period that falls in this month
    doc_id: str | None
    span: str


@dataclass
class MonthResult:
    month: str  # YYYY-MM
    member_id: str
    status: Literal["meets", "does_not_meet", "insufficient_evidence"]
    path: str | None  # hours | household_income | combined | seasonal_average
    activity_hours: float
    household_income: float
    income_threshold: float
    income_hours_equivalent: float
    combined_hours: float
    seasonal_average_income: float | None
    contributions: list[Contribution]
    ambiguities: list[str]
    facts_used: list[str]


@dataclass
class ExemptionFlag:
    member_id: str
    key: str
    label: str
    fact_ids: list[str]
    action: str


@dataclass
class Worksheet:
    case_id: str
    jurisdiction: str
    as_of: date
    months: list[str]
    results: list[MonthResult]
    exemptions: list[ExemptionFlag]
    cure_deadline: date | None
    params: dict[str, dict]
    warnings: list[str] = field(default_factory=list)


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_bounds(key: str) -> tuple[date, date]:
    y, m = map(int, key.split("-"))
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def prev_months(d: date, n: int) -> list[str]:
    """The n full calendar months before the month containing d, oldest first."""
    out = []
    y, m = d.year, d.month
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append(f"{y:04d}-{m:02d}")
    return list(reversed(out))


def prorate(e: LedgerEntry, key: str) -> tuple[float, float]:
    """Amount of an entry attributable to a month, by overlapping days. Returns (amount, share)."""
    ms, me = month_bounds(key)
    s, t = max(e.period_start, ms), min(e.period_end, me)
    if s > t:
        return 0.0, 0.0
    total_days = (e.period_end - e.period_start).days + 1
    share = ((t - s).days + 1) / total_days
    return e.amount * share, share


def _income_value(kind: Kind) -> bool:
    return kind in INCOME_KINDS


def months_to_check(case: Case, p: Params) -> list[str]:
    if case.event == "application":
        return prev_months(case.event_date, int(p["lookback_months_application"]))
    # renewal / noncompliance: default to the month before the event (states vary; flagged in warnings)
    return prev_months(case.event_date, 1)


def _member_month(case: Case, member: Member, key: str, p: Params) -> MonthResult:
    threshold = float(p["income_multiplier_hours"]) * float(p["min_wage"])
    contributions: list[Contribution] = []
    ambiguities: list[str] = []
    facts_used = [p.get(k).fact_id for k in ("monthly_hours", "min_wage", "income_multiplier_hours") if p.get(k).fact_id]

    activity_hours = 0.0
    household_income = 0.0
    member_income = 0.0
    applicable = [m for m in case.household if m.applicable_adult]

    for e in case.ledger:
        amt, share = prorate(e, key)
        if share == 0:
            continue
        if share < 1 and (e.period_end - e.period_start).days > 0:
            span = f"{e.period_start}..{e.period_end}"
            if not any(span in a for a in ambiguities):
                ambiguities.append(
                    f"Entry {e.id} covers {span}; {share:.0%} was attributed to {key} by days. "
                    "Confirm how the agency counts periods that cross months."
                )
        c = Contribution(e.id, e.member_id, e.kind.value, round(amt, 2), round(share, 4),
                         e.source.doc_id if e.source else None, e.source.span if e.source else "")
        if e.kind in HOURS_KINDS and e.member_id == member.id:
            activity_hours += amt
            contributions.append(c)
        elif _income_value(e.kind):
            counts_household = bool(p["income_basis_household"])
            if counts_household or e.member_id == member.id:
                household_income += amt
                contributions.append(c)
            if e.member_id == member.id:
                member_income += amt
            if e.kind == Kind.SELF_EMPLOYMENT_GROSS:
                msg = (f"Entry {e.id} is gross self-employment/gig income. MAGI counts self-employment income net of "
                       "business expenses; if expenses exist, countable income may be lower.")
                if msg not in ambiguities:
                    ambiguities.append(msg)

    if p["income_basis_household"]:
        facts_used.append(p.get("income_basis_household").fact_id or "default:income_basis_household")

    # income -> hours proxy, allocated across applicable adults (equal split by default: a 'reasonable method')
    income_hours = 0.0
    if p["income_to_hours_allowed"] and float(p["min_wage"]) > 0:
        pool_hours = household_income / float(p["min_wage"])
        income_hours = pool_hours / max(1, len(applicable)) if p["income_basis_household"] else member_income / float(p["min_wage"])
        if p["income_basis_household"] and len(applicable) > 1:
            ambiguities.append(
                f"Income-to-hours split equally across {len(applicable)} adults subject to the requirement; "
                "the state chooses the allocation method."
            )
    combined = activity_hours + income_hours

    seasonal_avg = None
    if member.seasonal_worker:
        n = int(p["seasonal_months"])
        window = prev_months(month_bounds(key)[1] + timedelta(days=1), n)
        tot = 0.0
        for k2 in window:
            for e in case.ledger:
                if _income_value(e.kind) and (p["income_basis_household"] or e.member_id == member.id):
                    tot += prorate(e, k2)[0]
        seasonal_avg = tot / n

    hours_req = float(p["monthly_hours"])
    status, path = "does_not_meet", None
    if activity_hours >= hours_req:
        status, path = "meets", "hours"
    elif household_income >= threshold:
        status, path = "meets", "household_income"
    elif combined >= hours_req:
        status, path = "meets", "combined"
    elif seasonal_avg is not None and seasonal_avg >= threshold:
        status, path = "meets", "seasonal_average"
    elif not contributions:
        status = "insufficient_evidence"

    return MonthResult(
        month=key,
        member_id=member.id,
        status=status,
        path=path,
        activity_hours=round(activity_hours, 2),
        household_income=round(household_income, 2),
        income_threshold=round(threshold, 2),
        income_hours_equivalent=round(income_hours, 2),
        combined_hours=round(combined, 2),
        seasonal_average_income=None if seasonal_avg is None else round(seasonal_avg, 2),
        contributions=contributions,
        ambiguities=ambiguities,
        facts_used=[f for f in facts_used if f],
    )


EXEMPTION_SCREENS: list[tuple[str, str, str, list[str]]] = [
    # attribute, key, label, candidate fact ids
    ("pregnant_or_postpartum", "pregnant_postpartum", "Pregnant or postpartum", ["US.exemption.pregnant_postpartum"]),
    ("caretaker_of_young_child", "caretaker_child", "Parent or caretaker of a young child", ["US.exemption.caretaker_child"]),
    ("caretaker_of_disabled_person", "caretaker_disabled", "Caretaker of a person with a disability", ["US.exemption.caretaker_disabled"]),
    ("veteran_total_disability", "veteran_disability", "Veteran with a total disability rating", ["US.exemption.veteran_total_disability"]),
    ("american_indian_alaska_native", "ai_an", "American Indian / Alaska Native", ["US.exemption.ai_an"]),
    ("in_sud_treatment", "sud_treatment", "In substance use disorder treatment", ["US.exemption.sud_treatment"]),
    ("meets_snap_or_tanf_work_rules", "snap_tanf", "Meets SNAP or TANF work requirements", ["US.exemption.snap_tanf_compliance"]),
    ("recently_incarcerated", "incarceration", "Incarcerated or recently released", ["US.exemption.incarceration"]),
]


def screen_exemptions(case: Case, on: date) -> list[ExemptionFlag]:
    from .. import rules

    out: list[ExemptionFlag] = []
    for m in case.household:
        if not m.applicable_adult:
            continue
        for attr, key, label, fids in EXEMPTION_SCREENS:
            if getattr(m, attr) is True:
                found = [f for f in fids if rules.fact(f, on)]
                out.append(ExemptionFlag(m.id, key, label, found,
                                         "Possible exemption — confirm with the state agency and keep proof."))
        if m.medically_frail_indicators:
            out.append(ExemptionFlag(m.id, "medically_frail", "Possible medical frailty: " + ", ".join(m.medically_frail_indicators),
                                     [f for f in ["US.exemption.medically_frail"] if rules.fact(f, on)],
                                     "Ask the client's clinician for a statement; the agency decides frailty."))
    return out


def worksheet(case: Case, on: date | None = None) -> Worksheet:
    on = on or case.event_date
    p = resolve(case.jurisdiction, on)
    months = months_to_check(case, p)
    client = next(m for m in case.household if m.id == case.client_id)
    results = [_member_month(case, client, k, p) for k in months]
    warnings = [f"'{v.label}' uses an unverified default ({v.value}); no captured rule text for it yet."
                for v in p.values.values() if not v.verified]
    if case.event != "application":
        warnings.append("Renewal look-back assumed to be the month before the event date; confirm the state's method.")
    cure = case.notice_date + timedelta(days=int(p["cure_days"])) if case.notice_date else None
    return Worksheet(
        case_id=case.id,
        jurisdiction=case.jurisdiction,
        as_of=on,
        months=months,
        results=results,
        exemptions=screen_exemptions(case, on),
        cure_deadline=cure,
        params={k: {"value": v.value, "fact_id": v.fact_id, "verified": v.verified, "label": v.label} for k, v in p.values.items()},
        warnings=warnings,
    )
