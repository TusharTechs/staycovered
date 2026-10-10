"""Paths to stay covered: the smallest changes that would settle a month, each proven by re-running the engine.

For a month that is not yet `meets`, we try concrete counterfactuals (a few more hours, a little more income,
expense receipts, the agency counting household income) and keep only the ones the engine confirms. Past months
can only be settled with *evidence* of something that already happened; the wording says so. Exemptions are never
decided here: unanswered screening questions are listed as the cheapest thing to ask.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from .compute import EXEMPTION_SCREENS, MonthResult, _first_fact, _member_month, month_bounds
from .model import Case, Kind, LedgerEntry, Member
from .params import Param, Params, resolve


@dataclass
class Path:
    kind: str            # ask_exemption | hours | income | expenses | household
    title: str
    detail: str
    effort: int          # 1 = one question, 2 = one document, 3 = new activity
    month: str
    proven: bool         # the engine re-ran with this change and the month qualified
    result_status: str   # status after the change (or "exempt — agency decides")
    fact_ids: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)


def _with(case: Case, extra: list[LedgerEntry] | None = None, replace: dict[str, LedgerEntry] | None = None) -> Case:
    ledger = [replace.get(e.id, e) if replace else e for e in case.ledger] + (extra or [])
    return case.model_copy(update={"ledger": ledger})


def _override(p: Params, **vals) -> Params:
    q = Params(p.jurisdiction, p.on, dict(p.values))
    for k, v in vals.items():
        q.values[k] = Param(v, p.values[k].fact_id, p.values[k].verified, p.values[k].label)
    return q


def _rerun(case: Case, member: Member, key: str, p: Params) -> MonthResult:
    return _member_month(case, member, key, p)


def _min_amount(case: Case, member: Member, key: str, p: Params, kind: Kind, hi: float) -> float | None:
    """Smallest amount of `kind` (rounded up to 0.25) added in `key` that makes the month meet; None if even `hi` fails."""
    ms, me = month_bounds(key)

    def ok(x: float) -> bool:
        e = LedgerEntry(id="what-if", member_id=member.id, kind=kind, period_start=ms, period_end=me, amount=x)
        return _rerun(_with(case, [e]), member, key, p).status == "meets"

    if not ok(hi):
        return None
    lo = 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
    return math.ceil(hi * 4 - 1e-6) / 4


def _hourly_wage(r: MonthResult) -> float | None:
    """The client's own hourly wage, when a document in the month gives both wages and hours."""
    by_doc: dict[str, dict[str, float]] = {}
    for c in r.contributions:
        if c.member_id == r.member_id and c.kind in (Kind.EARNED_INCOME.value, Kind.WORK_HOURS.value):
            by_doc.setdefault(c.doc_id or "", {}).setdefault(c.kind, 0.0)
            by_doc[c.doc_id or ""][c.kind] += c.amount
    for d in by_doc.values():
        if d.get(Kind.WORK_HOURS.value) and d.get(Kind.EARNED_INCOME.value):
            return round(d[Kind.EARNED_INCOME.value] / d[Kind.WORK_HOURS.value], 2)
    return None


def month_paths(case: Case, r: MonthResult, today: date, wage: float | None = None) -> list[Path]:
    if r.status == "meets":
        return []
    p = resolve(case.jurisdiction, month_bounds(r.month)[0])
    member = next(m for m in case.household if m.id == case.client_id)
    past = month_bounds(r.month)[1] < today
    label = date.fromisoformat(r.month + "-01").strftime("%B %Y")
    out: list[Path] = []
    rule_facts = [f for f in (p.get("monthly_hours").fact_id, p.get("income_threshold").fact_id) if f]

    # 1. Expense receipts (gig payouts are gross): the cheapest proof when the month is conditional on expenses.
    if r.expense_headroom is not None:
        gross = [e for e in case.ledger if e.member_id == member.id and e.kind == Kind.SELF_EMPLOYMENT_GROSS]
        tot = sum(e.amount for e in gross) or 1
        # spread the allowed expenses across payouts in proportion, as net self-employment income
        repl = {e.id: e.model_copy(update={"kind": Kind.SELF_EMPLOYMENT_NET,
                                             "amount": e.amount - r.expense_headroom * e.amount / tot}) for e in gross}
        after = _rerun(_with(case, replace=repl), member, r.month, p)
        out.append(Path("expenses", f"Show {label} business expenses of ${r.expense_headroom:,.2f} or less",
                        "A mileage log or receipts (fuel, phone, platform fees). Gig payouts are before costs; "
                        "if costs are under this amount, what's left still counts.",
                        2, r.month, after.status == "meets", after.status, rule_facts))

    # 2. Household income counted (Nebraska 2026: 'may count in some cases').
    if any("household" in c for c in r.conditions):
        after = _rerun(case, member, r.month, _override(p, income_basis="household"))
        out.append(Path("household", "Ask the agency to count the household's income",
                        "Nebraska says other household members' income 'may count in some cases'. From January 2027 federal "
                        "rules count household income, so this resolves itself then.",
                        1, r.month, after.status == "meets", after.status,
                        [f for f in (p.get("income_basis").fact_id,) if f]))

    # 3. More qualifying hours (any activity: work, volunteering, school, job training).
    need_h = _min_amount(case, member, r.month, p, Kind.COMMUNITY_SERVICE_HOURS, float(p["monthly_hours"]))
    if need_h:
        weeks = month_bounds(r.month)[1].day / 7
        title = (f"Proof of {need_h:g} more qualifying hours in {label}" if past
                 else f"{need_h:g} more qualifying hours in {label} (about {need_h / weeks:.1f} a week)")
        detail = ("Hours already done but not on these documents count: another job, volunteering, classes or job training. "
                  "A signed letter from the place is enough." if past else
                  "Any mix of work, volunteering, school or a job-training program counts.")
        out.append(Path("hours", title, detail, 2 if past else 3, r.month, True, "meets", rule_facts))

    # 4. More countable income.
    need_i = _min_amount(case, member, r.month, p, Kind.EARNED_INCOME, float(p["income_threshold"]))
    if need_i:
        title = f"Proof of ${need_i:,.2f} more income in {label}" if past else f"${need_i:,.2f} more income in {label}"
        wage = _hourly_wage(r) or wage
        if wage:
            title += f" (about {math.ceil(need_i / wage)} more paid hours at ${wage:,.2f}/hr)"
        conv = " Income also converts to hours at the minimum wage here, so a mix works." if p["income_to_hours"] else ""
        out.append(Path("income", title, "Wages or other countable income not yet on file." + conv,
                        2 if past else 3, r.month, True, "meets", rule_facts))

    # 5. Unanswered exemption questions: one 'yes' could settle the whole review (agency decides).
    unknown = [(attr, lab, fids) for attr, _k, lab, fids in EXEMPTION_SCREENS if getattr(member, attr) is None]
    if unknown:
        on = month_bounds(r.month)[0]
        fids = sorted({f for _a, _l, c in unknown for f in _first_fact(c, case.jurisdiction, on)})
        out.append(Path("ask_exemption", f"Ask {len(unknown)} quick screening questions",
                        "Any 'yes' is a possible exemption from the requirement. The agency decides; keep proof.",
                        1, r.month, False, "exempt — agency decides", fids, [lab for _a, lab, _f in unknown]))

    order = {"expenses": 0, "household": 1, "ask_exemption": 2, "hours": 3, "income": 4}
    return sorted(out, key=lambda x: (x.effort, order[x.kind]))
