"""Deterministic compliance worksheet.

The LLM never does arithmetic. This module turns ledger rows into a month-by-month worksheet in which every number
carries the ledger rows (and so the client-document spans) and the rule facts it used.

Month outcomes:
  meets                  the published rules are satisfied using only income/hours that clearly count
  conditional            satisfied only if something the agency decides goes the client's way; `conditions` says what
                         (e.g. business expenses at most $X; the agency counting a spouse's income)
  does_not_meet          evidence exists but falls short
  insufficient_evidence  no evidence for the month

Exemptions are only ever "possible — confirm with the agency".
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from .model import HOURS_KINDS, INCOME_KINDS, Case, Kind, LedgerEntry, Member
from .params import Params, resolve

Status = Literal["meets", "conditional", "does_not_meet", "insufficient_evidence"]


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
    month: str
    member_id: str
    status: Status
    path: str | None  # hours | income | combined | seasonal_average
    conditions: list[str]
    activity_hours: float
    own_income: float  # clearly countable income of the client (wages, unearned, net self-employment)
    own_gross_self_employment: float  # gig/self-employment payouts before expenses
    household_other_income: float  # income of other household members
    income_threshold: float
    income_hours_equivalent: float
    combined_hours: float
    seasonal_average_income: float | None
    expense_headroom: float | None
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
    review: str  # human description of the review rule applied
    months: list[str]
    results: list[MonthResult]
    overall: Status
    exemptions: list[ExemptionFlag]
    cure_deadline: date | None
    cure_note: str
    params: dict[str, dict]
    warnings: list[str] = field(default_factory=list)


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


def _review(case: Case, p: Params) -> tuple[list[str], bool, str]:
    """Months to check, whether one qualifying month is enough, and a description."""
    if case.months_in_question:
        return sorted(case.months_in_question), False, "Months named in the agency's notice"
    if case.event == "application":
        n = int(p["application_months"])
        return prev_months(case.event_date, n), False, f"The {n} calendar month(s) before the application"
    n = int(p["renewal_window_months"])
    any_month = bool(p["renewal_any_month"])
    months = prev_months(case.event_date, n)
    desc = (f"Any one month in the {n} months before renewal" if any_month and n > 1
            else f"The {n} month(s) before renewal")
    return months, any_month, desc


def _member_month(case: Case, member: Member, key: str, p: Params) -> MonthResult:
    threshold = float(p["income_threshold"])
    hours_req = float(p["monthly_hours"])
    min_wage = float(p["min_wage"])
    basis = p["income_basis"]
    contributions: list[Contribution] = []
    ambiguities: list[str] = []
    facts_used = [p.get(k).fact_id for k in ("monthly_hours", "income_threshold", "income_basis") if p.get(k).fact_id]

    activity_hours = own_net = own_gross = other_net = other_gross = 0.0
    for e in case.ledger:
        amt, share = prorate(e, key)
        if share == 0:
            continue
        if share < 1 and (e.period_end - e.period_start).days > 0:
            ambiguities.append(f"{e.payer or e.id}: {e.period_start:%b %d}–{e.period_end:%b %d} crosses months; "
                               f"{share:.0%} counted in {key} by days. Confirm how the agency counts it.")
        c = Contribution(e.id, e.member_id, e.kind.value, round(amt, 2), round(share, 4),
                         e.source.doc_id if e.source else None, e.source.span if e.source else "")
        mine = e.member_id == member.id
        if e.kind in HOURS_KINDS:
            if mine:
                activity_hours += amt
                contributions.append(c)
        elif e.kind in INCOME_KINDS:
            gross = e.kind == Kind.SELF_EMPLOYMENT_GROSS
            if mine:
                own_gross += amt if gross else 0
                own_net += 0 if gross else amt
                contributions.append(c)
            elif basis != "own":
                other_gross += amt if gross else 0
                other_net += 0 if gross else amt
                contributions.append(c)

    def income_hours(income: float) -> float:
        return income / min_wage if p["income_to_hours"] and min_wage > 0 else 0.0

    def passes(income: float) -> str | None:
        if activity_hours >= hours_req:
            return "hours"
        if income >= threshold:
            return "income"
        if p["income_to_hours"] and activity_hours + income_hours(income) >= hours_req:
            return "combined"
        return None

    # Levels of certainty: clearly-countable income first, then income that depends on an agency decision.
    sure_income = own_net + (other_net if basis == "household" else 0)
    status: Status = "does_not_meet"
    path: str | None = None
    conditions: list[str] = []
    headroom = None
    if (path := passes(sure_income)):
        status = "meets"
    else:
        extras: list[tuple[str, float]] = []
        if own_gross + (other_gross if basis == "household" else 0) > 0:
            extras.append(("expenses", own_gross + (other_gross if basis == "household" else 0)))
        if basis == "own_plus_maybe_household" and (other_net + other_gross) > 0:
            extras.append(("household", other_net + other_gross))
        acc = sure_income
        needed: list[str] = []
        for kind, amt in extras:
            acc += amt
            needed.append(kind)
            if (path := passes(acc)):
                status = "conditional"
                break
        if status == "conditional":
            if "expenses" in needed:
                gross_total = dict(extras)["expenses"]
                need_income = threshold if path == "income" else max(0.0, hours_req - activity_hours) * min_wage
                headroom = round(acc - need_income, 2)
                conditions.append(f"Business expenses for the month are ${headroom:,.2f} or less "
                                  f"(${gross_total:,.2f} is gig/self-employment payout before costs like fuel and phone).")
            if "household" in needed:
                conditions.append("The agency counts other household members' income for this client "
                                  "(Nebraska: 'may count in some cases', 477 NAC 16).")
        elif not contributions:
            status = "insufficient_evidence"

    if own_gross > 0 and status != "conditional":
        ambiguities.append(f"${own_gross:,.2f} is self-employment payout before expenses; countable income may be lower.")

    seasonal_avg = None
    if member.seasonal_worker:
        n = int(p["seasonal_months"])
        window = prev_months(month_bounds(key)[1] + timedelta(days=1), n)
        tot = 0.0
        for k2 in window:
            for e in case.ledger:
                if e.kind in INCOME_KINDS and e.kind != Kind.SELF_EMPLOYMENT_GROSS and (e.member_id == member.id or basis == "household"):
                    tot += prorate(e, k2)[0]
        seasonal_avg = tot / n
        facts_used.append(p.get("seasonal_months").fact_id or "default:seasonal_months")
        if status != "meets" and seasonal_avg >= threshold:
            status, path, conditions = "meets", "seasonal_average", []

    all_income = own_net + own_gross + (other_net + other_gross if basis != "own" else 0)
    ih = income_hours(all_income)
    return MonthResult(
        month=key, member_id=member.id, status=status, path=path, conditions=conditions,
        activity_hours=round(activity_hours, 2), own_income=round(own_net, 2), own_gross_self_employment=round(own_gross, 2),
        household_other_income=round(other_net + other_gross, 2), income_threshold=round(threshold, 2),
        income_hours_equivalent=round(ih, 2), combined_hours=round(activity_hours + ih, 2),
        seasonal_average_income=None if seasonal_avg is None else round(seasonal_avg, 2),
        expense_headroom=headroom, contributions=contributions, ambiguities=list(dict.fromkeys(ambiguities)),
        facts_used=[f for f in facts_used if f],
    )


EXEMPTION_SCREENS: list[tuple[str, str, str, list[str]]] = [
    ("pregnant_or_postpartum", "pregnant_postpartum", "Pregnant or postpartum",
     ["{J}.exemption.pregnancy_postpartum", "US.exemption.pregnant_postpartum"]),
    ("caretaker_of_young_child", "caretaker_child", "Parent or caretaker of a child 13 or younger",
     ["{J}.exemption.parent_caretaker.v2", "{J}.exemption.parent_caretaker.v1", "US.exemption.parent_caregiver_dependent_child"]),
    ("caretaker_of_disabled_person", "caretaker_disabled", "Caretaker of a person with a disability",
     ["{J}.exemption.parent_caretaker.v2", "US.exemption.parent_caregiver_dependent_child"]),
    ("veteran_total_disability", "veteran_disability", "Veteran with a total disability rating",
     ["{J}.exemption.veteran_total_disability", "US.exemption.veteran_total_disability"]),
    ("american_indian_alaska_native", "ai_an", "American Indian / Alaska Native",
     ["{J}.exemption.tribal.v2", "{J}.exemption.tribal.v1", "US.exemption.american_indian_alaska_native"]),
    ("in_sud_treatment", "sud_treatment", "In substance use disorder treatment",
     ["{J}.exemption.sud_treatment_program", "US.exemption.substance_use_treatment"]),
    ("meets_snap_or_tanf_work_rules", "snap_tanf", "Meets SNAP or TANF work requirements",
     ["{J}.exemption.snap_tanf", "US.exemption.snap_work_requirements"]),
    ("recently_incarcerated", "incarceration", "Incarcerated or recently released",
     ["{J}.exemption.incarceration", "US.exemption.recent_inmate"]),
]


def _first_fact(cands: list[str], j: str, on: date) -> list[str]:
    from .. import rules

    for c in cands:
        fid = c.format(J=j)
        if rules.fact(fid, on):
            return [fid]
    return []


def screen_exemptions(case: Case, on: date) -> list[ExemptionFlag]:
    out: list[ExemptionFlag] = []
    for m in case.household:
        if not m.applicable_adult:
            continue
        for attr, key, label, fids in EXEMPTION_SCREENS:
            if getattr(m, attr) is True:
                out.append(ExemptionFlag(m.id, key, label, _first_fact(fids, case.jurisdiction, on),
                                         "Possible exemption — tell the agency and keep proof. The agency decides."))
        if m.medically_frail_indicators:
            out.append(ExemptionFlag(
                m.id, "medically_frail", "Possible medical frailty: " + ", ".join(m.medically_frail_indicators),
                _first_fact(["{J}.exemption.medically_frail.definition.v2", "US.exemption.medically_frail_definition"], case.jurisdiction, on),
                "Ask the agency how frailty is being verified now, and the client's clinician for a statement if needed. The agency decides."))
    return out


ORDER: dict[str, int] = {"meets": 0, "conditional": 1, "does_not_meet": 2, "insufficient_evidence": 3}


def _overall(results: list[MonthResult], any_month: bool) -> Status:
    sts = [r.status for r in results]
    if not sts:
        return "insufficient_evidence"
    if any_month:
        best = min(sts, key=lambda s: ORDER[s])
        if best == "insufficient_evidence" and "does_not_meet" in sts:
            return "does_not_meet"
        return best  # type: ignore[return-value]
    worst = max(sts, key=lambda s: ORDER[s])
    return worst  # type: ignore[return-value]


def worksheet(case: Case, on: date | None = None) -> Worksheet:
    on = on or case.event_date
    p = resolve(case.jurisdiction, on)
    months, any_month, desc = _review(case, p)
    client = next(m for m in case.household if m.id == case.client_id)
    results = [_member_month(case, client, k, p) for k in months]
    if any_month and len(results) > 3:  # show months with evidence (plus the latest), not 12 empty rows
        keep = [r for r in results if r.contributions] or results[-1:]
        results = keep
    warnings = [f"'{v.label}' has no published rule text for this date; using a conservative default ({v.value})."
                for k, v in p.values.items() if not v.verified and k not in ("receipt_days",)]
    cure, note = None, ""
    if case.notice_date:
        base = int(p["cure_days"])
        receipt = int(p["receipt_days"])
        cure = case.notice_date + timedelta(days=base + receipt)
        note = (f"{base} days from the notice date" if not receipt else f"{base} days after the notice is treated as received ({receipt} days after its date)")
        if case.jurisdiction == "NE" and not receipt:
            note += ". Nebraska says '30 days of getting the notice', and its sample notice shows a due date 35 days after the notice date — use the date printed on the client's notice if it is later."
    return Worksheet(
        case_id=case.id, jurisdiction=case.jurisdiction, as_of=on, review=desc, months=[r.month for r in results],
        results=results, overall=_overall(results, any_month), exemptions=screen_exemptions(case, on),
        cure_deadline=cure, cure_note=note,
        params={k: {"value": v.value, "fact_id": v.fact_id, "verified": v.verified, "label": v.label} for k, v in p.values.items()},
        warnings=warnings,
    )
