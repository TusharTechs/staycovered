"""Case store: one JSON file per case under data/cases/ (demo cases are synthetic; see demo/)."""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
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


# Per-visitor isolation on the public demo: a visitor's changes (added documents, explanations) go to a private
# overlay keyed by their session cookie, so one judge's test never shows up in the next judge's caseload.
SESSION: ContextVar[str | None] = ContextVar("session", default=None)
SESSIONS = config.RUNTIME_DIR / "sessions"
ISOLATE = config.ON_VERCEL or os.getenv("SC_ISOLATE") == "1"


def _overlay(case_id: str) -> Path | None:
    sid = SESSION.get()
    return SESSIONS / sid / f"{case_id}.json" if ISOLATE and sid else None


def path(case_id: str) -> Path:
    ov = _overlay(case_id)
    return ov if ov and ov.exists() else CASES / f"{case_id}.json"


def save(rec: CaseRecord) -> None:
    rec.updated = date.today()
    target = _overlay(rec.case.id) or CASES / f"{rec.case.id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rec.model_dump_json(indent=2), encoding="utf-8")


def load(case_id: str) -> CaseRecord:
    return CaseRecord.model_validate_json(path(case_id).read_text(encoding="utf-8"))


def all_cases() -> list[CaseRecord]:
    return [load(p.stem) for p in sorted(CASES.glob("*.json"))]


def changed_cases() -> list[str]:
    """Cases this visitor has changed (private overlay)."""
    sid = SESSION.get()
    d = SESSIONS / sid if ISOLATE and sid else None
    return sorted(p.stem for p in d.glob("*.json")) if d and d.exists() else []


def reset_session() -> int:
    import shutil
    n = len(changed_cases())
    sid = SESSION.get()
    if ISOLATE and sid and (SESSIONS / sid).exists():
        shutil.rmtree(SESSIONS / sid)
    return n
