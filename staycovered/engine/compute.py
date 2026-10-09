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
    status: Literal["meets", "depends_on_expenses", "does_not_meet", "insufficient_evidence"]
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
    gross_self_employment: float = 0.0
    expense_headroom: float | None = None  # meets if business expenses are at most this much (depends_on_expenses)


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
    net_income = 0.0  # countable without further information (wages, unearned, stated net self-employment)
    gross_se = 0.0  # gig/self-employment payouts before expenses: countable only after expenses
    member_net = 0.0
    member_gross = 0.0
    applicable = [m for m in case.household if m.applicable_adult]
    household_basis = bool(p["income_basis_household"])

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
            mine = e.member_id == member.id
            if household_basis or mine:
                contributions.append(c)
                if e.kind == Kind.SELF_EMPLOYMENT_GROSS:
                    gross_se += amt
                else:
                    net_income += amt
            if mine:
                if e.kind == Kind.SELF_EMPLOYMENT_GROSS:
                    member_gross += amt
                else:
                    member_net += amt

    if household_basis:
        facts_used.append(p.get("income_basis_household").fact_id or "default:income_basis_household")
    if gross_se > 0:
        ambiguities.append(
            f"${gross_se:,.2f} is gig/self-employment payout before expenses. Income counts after business expenses "
            "(fuel, mileage, phone), so only part of it may count."
        )

    min_wage = float(p["min_wage"])
    hours_req = float(p["monthly_hours"])
    n_adults = max(1, len(applicable))
    if household_basis and len(applicable) > 1 and p["income_to_hours_allowed"]:
        ambiguities.append(
            f"Income-to-hours split equally across {len(applicable)} adults subject to the requirement; "
            "the state chooses the allocation method."
        )

    def income_hours(inc_household: float, inc_member: float) -> float:
        if not p["income_to_hours_allowed"] or min_wage <= 0:
            return 0.0
        return (inc_household / n_adults) / min_wage if household_basis else inc_member / min_wage

    def seasonal(include_gross: bool) -> float | None:
        if not member.seasonal_worker:
            return None
        n = int(p["seasonal_months"])
        window = prev_months(month_bounds(key)[1] + timedelta(days=1), n)
        tot = 0.0
        for k2 in window:
            for e in case.ledger:
                if not _income_value(e.kind) or not (household_basis or e.member_id == member.id):
                    continue
                if e.kind == Kind.SELF_EMPLOYMENT_GROSS and not include_gross:
                    continue
                tot += prorate(e, k2)[0]
        return tot / n

    def evaluate(inc: float, inc_member: float, include_gross: bool) -> str | None:
        if activity_hours >= hours_req:
            return "hours"
        if inc >= threshold:
            return "household_income"
        if activity_hours + income_hours(inc, inc_member) >= hours_req:
            return "combined"
        sa = seasonal(include_gross)
        if sa is not None and sa >= threshold:
            return "seasonal_average"
        return None

    status, path, headroom = "does_not_meet", None, None
    sure = evaluate(net_income, member_net, False)
    if sure:
        status, path = "meets", sure
    else:
        maybe = evaluate(net_income + gross_se, member_net + member_gross, True)
        if maybe and gross_se > 0:
            # Report the most forgiving path: how much in expenses can there be and the month still passes?
            options = []
            total = net_income + gross_se
            if total >= threshold:
                options.append(("household_income", total - threshold))
            if p["income_to_hours_allowed"] and min_wage > 0:
                need_income = max(0.0, hours_req - activity_hours) * min_wage * (n_adults if household_basis else 1)
                have = total if household_basis else (member_net + member_gross)
                if have >= need_income:
                    options.append(("combined", have - need_income))
            if options:
                path, headroom = max(options, key=lambda o: o[1])
            else:
                path = maybe
            status = "depends_on_expenses"
        elif not contributions:
            status = "insufficient_evidence"

    household_income = net_income + gross_se
    ih = income_hours(household_income, member_net + member_gross)
    seasonal_avg = seasonal(True)

    return MonthResult(
        month=key,
        member_id=member.id,
        status=status,
        path=path,
        activity_hours=round(activity_hours, 2),
        household_income=round(household_income, 2),
        income_threshold=round(threshold, 2),
        income_hours_equivalent=round(ih, 2),
        combined_hours=round(activity_hours + ih, 2),
        seasonal_average_income=None if seasonal_avg is None else round(seasonal_avg, 2),
        contributions=contributions,
        ambiguities=ambiguities,
        facts_used=[f for f in facts_used if f],
        gross_self_employment=round(gross_se, 2),
        expense_headroom=None if headroom is None else round(headroom, 2),
    )


EXEMPTION_SCREENS: list[tuple[str, str, str, list[str]]] = [
    # attribute, key, label, candidate fact ids
    ("pregnant_or_postpartum", "pregnant_postpartum", "Pregnant or postpartum", ["{J}.exemption.pregnant_postpartum", "US.exemption.pregnant_postpartum"]),
    ("caretaker_of_young_child", "caretaker_child", "Parent or caretaker of a young child", ["{J}.exemption.parent_caregiver_dependent_child", "US.exemption.parent_caregiver_dependent_child"]),
    ("caretaker_of_disabled_person", "caretaker_disabled", "Caretaker of a person with a disability", ["{J}.exemption.parent_caregiver_dependent_child", "US.exemption.parent_caregiver_dependent_child", "US.exemption.disabled_individual_definition"]),
    ("veteran_total_disability", "veteran_disability", "Veteran with a total disability rating", ["{J}.exemption.veteran_total_disability", "US.exemption.veteran_total_disability"]),
    ("american_indian_alaska_native", "ai_an", "American Indian / Alaska Native", ["{J}.exemption.american_indian_alaska_native", "US.exemption.american_indian_alaska_native"]),
    ("in_sud_treatment", "sud_treatment", "In substance use disorder treatment", ["{J}.exemption.substance_use_treatment", "US.exemption.substance_use_treatment"]),
    ("meets_snap_or_tanf_work_rules", "snap_tanf", "Meets SNAP or TANF work requirements", ["{J}.exemption.snap_work_requirements", "US.exemption.snap_work_requirements", "US.exemption.tanf_work_requirements"]),
    ("recently_incarcerated", "incarceration", "Incarcerated or recently released", ["{J}.exemption.recent_inmate", "US.exemption.recent_inmate"]),
]


def screen_exemptions(case: Case, on: date) -> list[ExemptionFlag]:
    from .. import rules

    out: list[ExemptionFlag] = []
    for m in case.household:
        if not m.applicable_adult:
            continue
        for attr, key, label, fids in EXEMPTION_SCREENS:
            if getattr(m, attr) is True:
                found = [fid for f in fids if rules.fact(fid := f.format(J=case.jurisdiction), on) or rules.fact(fid)]
                out.append(ExemptionFlag(m.id, key, label, found,
                                         "Possible exemption — confirm with the state agency and keep proof."))
        if m.medically_frail_indicators:
            out.append(ExemptionFlag(m.id, "medically_frail", "Possible medical frailty: " + ", ".join(m.medically_frail_indicators),
                                     [fid for f in ["{J}.exemption.medically_frail_definition", "US.exemption.medically_frail_definition"] if rules.fact(fid := f.format(J=case.jurisdiction))],
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
