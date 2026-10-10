"""Case data model for the deterministic work-requirement engine."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Kind(str, Enum):
    # hours-type activities
    WORK_HOURS = "work_hours"
    COMMUNITY_SERVICE_HOURS = "community_service_hours"
    WORK_PROGRAM_HOURS = "work_program_hours"
    EDUCATION_HOURS = "education_hours"
    EDUCATION_CREDIT_HOURS = "education_credit_hours"  # credits enrolled in a term; converted to hours by state rule
    # income-type (counts toward household MAGI)
    EARNED_INCOME = "earned_income"
    SELF_EMPLOYMENT_GROSS = "self_employment_gross"  # e.g. gig platform payouts before expenses
    SELF_EMPLOYMENT_NET = "self_employment_net"
    UNEARNED_INCOME = "unearned_income"


HOURS_KINDS = {Kind.WORK_HOURS, Kind.COMMUNITY_SERVICE_HOURS, Kind.WORK_PROGRAM_HOURS, Kind.EDUCATION_HOURS}
INCOME_KINDS = {Kind.EARNED_INCOME, Kind.SELF_EMPLOYMENT_GROSS, Kind.SELF_EMPLOYMENT_NET, Kind.UNEARNED_INCOME}


class SourceRef(BaseModel):
    doc_id: str
    span: str = ""  # verbatim text from the client document supporting the number
    page: int | None = None


class LedgerEntry(BaseModel):
    id: str
    member_id: str
    kind: Kind
    period_start: date
    period_end: date  # inclusive
    amount: float  # hours or USD depending on kind
    payer: str = ""
    source: SourceRef | None = None
    note: str = ""


class Member(BaseModel):
    id: str
    name: str
    age: int | None = None
    applicable_adult: bool = True  # in the expansion population subject to the requirement
    seasonal_worker: bool = False
    # exemption screen-in attributes (None = unknown, ask)
    pregnant_or_postpartum: bool | None = None
    caretaker_of_young_child: bool | None = None
    caretaker_of_disabled_person: bool | None = None
    veteran_total_disability: bool | None = None
    american_indian_alaska_native: bool | None = None
    medically_frail_indicators: list[str] = Field(default_factory=list)
    in_sud_treatment: bool | None = None
    meets_snap_or_tanf_work_rules: bool | None = None
    recently_incarcerated: bool | None = None


class Case(BaseModel):
    id: str
    jurisdiction: str = "NE"
    location: str = ""  # "City, ST" only; used to look up nearby qualifying activities, never sent with anything else
    household: list[Member]
    client_id: str
    ledger: list[LedgerEntry] = Field(default_factory=list)
    event: Literal["application", "renewal", "noncompliance_notice"] = "renewal"
    event_date: date
    notice_date: date | None = None
    months_in_question: list[str] = Field(default_factory=list)  # YYYY-MM named in an agency notice
    notes: str = ""
