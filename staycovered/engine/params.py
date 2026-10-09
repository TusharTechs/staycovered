"""Engine parameters resolved from fact packs as of a date.

Every parameter records the fact it came from. Federal rules that take effect on 2027-01-01 override state
practice from that date (states must comply); before that, the state's published rules apply. Where nothing
is published, a conservative default is used and marked unverified so the UI and packet say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from .. import rules


@dataclass
class Param:
    value: Any
    fact_id: str | None
    verified: bool
    label: str


@dataclass
class Params:
    jurisdiction: str
    on: date
    values: dict[str, Param] = field(default_factory=dict)

    def __getitem__(self, k: str) -> Any:
        return self.values[k].value

    def get(self, k: str) -> Param:
        return self.values[k]


# (fact id template, transform(value) -> param value | None, verified)
Cand = tuple[str, Callable[[Any], Any], bool]
same: Callable[[Any], Any] = lambda v: v  # noqa: E731


def const(c: Any) -> Callable[[Any], Any]:
    return lambda _v: c


SPEC: dict[str, tuple[list[Cand], Any, str]] = {
    "monthly_hours": ([("{J}.requirement.hours_80", same, True), ("US.requirement.hours_per_month", same, True)],
                      80, "Required hours of qualifying activity per month"),
    "income_threshold": ([("US.income_alternative.threshold_2026", same, True), ("{J}.income_alternative.monthly_580", same, True)],
                         580, "Monthly income that satisfies the requirement"),
    "min_wage": ([("US.income_alternative.federal_wage_only", same, True)], 7.25, "Federal minimum wage"),
    # household: federal MAGI household income from 2027; Nebraska 2026: own earnings, others' income "may count in some cases"
    "income_basis": ([("US.income_alternative.magi_household_income", const("household"), True),
                      ("{J}.income_alternative.what_income_counts.v2", const("own_plus_maybe_household"), True),
                      ("{J}.income_alternative.what_income_counts.v1", const("own"), True)],
                     "own", "Whose income counts toward the income test"),
    # Nebraska combines activity hours only; the federal rule makes income-to-hours conversion a state option.
    "income_to_hours": ([("{J}.income_alternative.income_to_hours", same, True),
                         ("{J}.requirement.combine_hours", const(False), True)],
                        False, "Income converted to hours at minimum wage (state option; off unless the state publishes it)"),
    "seasonal_months": ([("{J}.income_alternative.seasonal_six_month_average", const(6), True),
                         ("US.income_alternative.seasonal_worker", lambda v: v.get("months") if isinstance(v, dict) else None, True)],
                        6, "Months averaged for seasonal workers"),
    "application_months": ([("{J}.lookback.new_applicants.activities_and_income", same, True),
                            ("US.lookback.application", lambda v: v.get("min") if isinstance(v, dict) else None, False)],
                           1, "Months reviewed before an application"),
    "renewal_window_months": ([("{J}.lookback.existing_members.twelve_months", same, True)],
                              1, "Months reviewed at renewal"),
    "renewal_any_month": ([("{J}.lookback.one_month_covers_full_period", const(True), True)],
                          False, "One qualifying month covers the whole period"),
    "cure_days": ([("{J}.cure.response_deadline_30_days", same, True), ("US.cure.period_30_days", same, True)],
                  30, "Days to respond to a request or noncompliance notice"),
    "receipt_days": ([("US.notice.deemed_received_after_5_days", same, True)],
                     0, "Days after the notice date it is treated as received"),
}


def resolve(jurisdiction: str, on: date) -> Params:
    p = Params(jurisdiction, on)
    for name, (cands, default, label) in SPEC.items():
        chosen = None
        for tmpl, fn, verified in cands:
            f = rules.fact(tmpl.format(J=jurisdiction), on)
            if f is None:
                continue
            v = fn(f.value)
            if v is None:
                continue
            chosen = Param(v, f.id, verified, label)
            break
        p.values[name] = chosen or Param(default, None, False, label)
    return p
