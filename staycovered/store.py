"""Case store: one JSON file per case under data/cases/ (demo cases are synthetic; see demo/)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from . import config
from .engine.model import Case

_SEED_CASES = config.ROOT / "data" / "cases"
if config.ON_VERCEL:
    # writable copy of the synthetic demo caseload for this instance
    import shutil

    CASES = config.RUNTIME_DIR / "cases"
    if not CASES.exists():
        shutil.copytree(_SEED_CASES, CASES)
else:
    CASES = _SEED_CASES
CASES.mkdir(parents=True, exist_ok=True)


class Document(BaseModel):
    id: str
    name: str
    kind: str  # notice | income | activity | other
    member_id: str | None = None
    text: str
    extracted: dict | None = None
    problems: list[str] = Field(default_factory=list)


class CaseRecord(BaseModel):
    case: Case
    client_name: str
    navigator: str = "Demo navigator"
    language: str = "en"
    documents: list[Document] = Field(default_factory=list)
    notice: dict | None = None
    flags: list[dict] = Field(default_factory=list)  # e.g. drift re-check flags
    synthetic: bool = True
    updated: date | None = None


def path(case_id: str) -> Path:
    return CASES / f"{case_id}.json"


def save(rec: CaseRecord) -> None:
    rec.updated = date.today()
    path(rec.case.id).write_text(rec.model_dump_json(indent=2))


def load(case_id: str) -> CaseRecord:
    return CaseRecord.model_validate_json(path(case_id).read_text())


def all_cases() -> list[CaseRecord]:
    return [CaseRecord.model_validate(json.loads(p.read_text())) for p in sorted(CASES.glob("*.json"))]
