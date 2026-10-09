"""Engine parameters resolved from fact packs as of a date.

Each parameter records the fact id it came from. If a fact is missing, the default is used and the
parameter is marked unverified so the UI and packet can say so instead of silently assuming.
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


# name -> (candidate fact ids in priority order, default, label)
SPEC: dict[str, tuple[list[str], Any, str]] = {
    "monthly_hours": (["{J}.requirement.monthly_hours", "US.requirement.monthly_hours"], 80, "Required hours per month"),
    "min_wage": (["{J}.income_alternative.min_wage", "US.income_alternative.federal_min_wage"], 7.25, "Federal minimum wage used for the income alternative"),
    "income_multiplier_hours": (["US.income_alternative.hours_multiplier"], 80, "Hours multiplied by minimum wage for the income alternative"),
    "income_basis_household": (["US.income_alternative.household_magi"], True, "Income alternative uses household MAGI income"),
    "income_to_hours_allowed": (["{J}.income_alternative.income_to_hours", "US.income_alternative.income_to_hours"], True, "Income can be converted to hours at minimum wage"),
    "seasonal_months": (["{J}.income_alternative.seasonal_average_months", "US.income_alternative.seasonal_average_months"], 6, "Months averaged for seasonal workers"),
    "lookback_months_application": (["{J}.lookback.application_months", "US.lookback.application_months_max"], 1, "Look-back months at application"),
    "cure_days": (["{J}.cure.days", "US.cure.days"], 30, "Days to respond to a noncompliance notice"),
    "age_min": (["US.applicability.age_min"], 19, "Minimum age subject to requirement"),
    "age_max": (["US.applicability.age_max"], 64, "Maximum age subject to requirement"),
}


def resolve(jurisdiction: str, on: date) -> Params:
    p = Params(jurisdiction, on)
    for name, (ids, default, label) in SPEC.items():
        chosen = None
        for fid in ids:
            f = rules.fact(fid.format(J=jurisdiction), on)
            if f is not None and f.value is not None:
                chosen = Param(f.value, f.id, True, label)
                break
        p.values[name] = chosen or Param(default, None, False, label)
    return p
