"""Client self-check: "Will I stay covered?" for the person, not the navigator.

The person describes a usual month in plain terms. We build a throwaway case for last month, run the same
deterministic engine, paths and forecast, and return the result. Nothing is stored, no names are asked for,
and no AI model is called.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from .engine.compute import EXEMPTION_SCREENS, month_bounds, prev_months, screen_exemptions, worksheet
from .engine.forecast import forecast
from .engine.model import Case, Kind, LedgerEntry, Member, SourceRef

H = Field(0, ge=0, le=744)        # hours in a month
USD = Field(0, ge=0, le=100_000)  # dollars in a month


class SelfCheckIn(BaseModel):
    jurisdiction: Literal["NE", "MT"]
    work_hours: float = H
    wages: float = USD
    gig_hours: float = H
    gig_payouts: float = USD
    volunteer_hours: float = H
    training_hours: float = H
    school_hours: float = H
    credits: float = Field(0, ge=0, le=30)
    other_income: float = USD
    partner_income: float = USD
    seasonal: bool = False
    exemptions: dict[str, bool | None] = Field(default_factory=dict)
    serious_medical_condition: bool | None = None


ATTRS = {a for a, *_ in EXEMPTION_SCREENS}
AGENCY = {"NE": "Nebraska DHHS: iServe Nebraska or 1-855-632-7633",
          "MT": "Montana DPHHS: Public Assistance Helpline 1-888-706-1535"}


def run(x: SelfCheckIn, today: date | None = None) -> dict:
    today = today or date.today()
    month = prev_months(today, 1)[0]
    ms, me = month_bounds(month)
    you = Member(id="you", name="You", seasonal_worker=x.seasonal,
                 medically_frail_indicators=["serious or complex medical condition (self-reported)"] if x.serious_medical_condition else [],
                 **{k: v for k, v in x.exemptions.items() if k in ATTRS})
    household = [you] + ([Member(id="partner", name="Partner", applicable_adult=False)] if x.partner_income else [])
    # (member, kind, amount, group): the group keeps a job's pay and hours together, e.g. for the hourly wage
    rows = [("you", Kind.WORK_HOURS, x.work_hours, "job"), ("you", Kind.EARNED_INCOME, x.wages, "job"),
            ("you", Kind.WORK_HOURS, x.gig_hours, "gig"), ("you", Kind.SELF_EMPLOYMENT_GROSS, x.gig_payouts, "gig"),
            ("you", Kind.COMMUNITY_SERVICE_HOURS, x.volunteer_hours, "volunteer"),
            ("you", Kind.WORK_PROGRAM_HOURS, x.training_hours, "training"), ("you", Kind.EDUCATION_HOURS, x.school_hours, "school"),
            ("you", Kind.EDUCATION_CREDIT_HOURS, x.credits, "school"), ("you", Kind.UNEARNED_INCOME, x.other_income, "other"),
            ("partner", Kind.EARNED_INCOME, x.partner_income, "partner")]
    ledger = [LedgerEntry(id=f"self-{i}", member_id=m, kind=k, period_start=ms, period_end=me, amount=v,
                          payer="(what you told us)", source=SourceRef(doc_id=g))
              for i, (m, k, v, g) in enumerate(rows) if v]
    case = Case(id="self-check", jurisdiction=x.jurisdiction, household=household, client_id="you", ledger=ledger,
                event="renewal", event_date=today, months_in_question=[month])
    ws = worksheet(case, today)
    r = ws.results[0]
    f = forecast(case, today)
    return {
        "month": month, "status": r.status, "path": r.path, "conditions": r.conditions,
        "numbers": {"activity_hours": r.activity_hours, "own_income": r.own_income, "gig_payouts": r.own_gross_self_employment,
                    "household_other_income": r.household_other_income, "threshold": r.income_threshold,
                    "hours_required": ws.params["monthly_hours"]["value"], "expense_headroom": r.expense_headroom},
        "plan": [asdict(p) for p in (f.months[0].paths if f.months else [])],
        "forecast": [{"month": m.month, "status": m.status, "changes": [asdict(c) for c in m.changes]} for m in f.months],
        "exemptions": [asdict(e) for e in screen_exemptions(case, today)],
        "rules": {k: ws.params[k] for k in ("monthly_hours", "income_threshold", "income_basis", "income_to_hours")},
        "agency": AGENCY[x.jurisdiction],
        "stored": False,
    }
