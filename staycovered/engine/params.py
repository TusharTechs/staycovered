"""Engine parameters resolved from fact packs as of a date.

Each parameter records the fact id it came from. State facts win over federal ones. Where the federal rule
only makes something a *state option*, finding the federal fact does not count as verified for the state.
If nothing is found, the default is used and marked unverified so the UI and packet say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

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


# candidate = (fact id template, key into dict value or None, counts_as_verified)
Cand = tuple[str, str | None, bool]

SPEC: dict[str, tuple[list[Cand], Any, str]] = {
    "monthly_hours": ([("{J}.requirement.hours_per_month", None, True), ("US.requirement.hours_per_month", None, True)],
                      80, "Required hours per month"),
    "min_wage": ([("{J}.income_alternative.federal_min_wage", None, True), ("US.income_alternative.federal_wage_only", None, True)],
                 7.25, "Federal minimum wage used for the income alternative"),
    "income_multiplier_hours": ([("{J}.requirement.hours_per_month", None, True), ("US.requirement.hours_per_month", None, True)],
                                80, "Hours multiplied by minimum wage for the income alternative"),
    "income_basis_household": ([("{J}.income_alternative.magi_household_income", None, True),
                                ("US.income_alternative.magi_household_income", None, True)],
                               True, "Income alternative uses household MAGI income"),
    "income_to_hours_allowed": ([("{J}.income_alternative.income_to_hours", None, True),
                                 ("US.income_alternative.income_to_hours_option", None, False)],
                                True, "Income converted to hours at minimum wage (a state option)"),
    "seasonal_months": ([("{J}.income_alternative.seasonal_worker", "months", True), ("US.income_alternative.seasonal_worker", "months", True)],
                        6, "Months averaged for seasonal workers"),
    "lookback_months_application": ([("{J}.lookback.application", "months", True), ("US.lookback.application", "min", False)],
                                    1, "Look-back months at application (state picks 1-3)"),
    "cure_days": ([("{J}.cure.period_days", None, True), ("US.cure.period_30_days", None, True)],
                  30, "Days to respond to a noncompliance notice"),
}


def _pick(value: Any, key: str | None) -> Any:
    if key is None:
        return value
    return value.get(key) if isinstance(value, dict) else None


def resolve(jurisdiction: str, on: date) -> Params:
    p = Params(jurisdiction, on)
    for name, (cands, default, label) in SPEC.items():
        chosen = None
        for tmpl, key, verified in cands:
            f = rules.fact(tmpl.format(J=jurisdiction), on)
            if f is None:
                continue
            v = _pick(f.value, key)
            if v is None:
                continue
            if name == "income_basis_household":
                v = True
            if name == "income_to_hours_allowed" and isinstance(v, str):
                v = True
            chosen = Param(v, f.id, verified, label)
            break
        p.values[name] = chosen or Param(default, None, False, label)
    return p
