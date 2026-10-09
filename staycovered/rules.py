"""Fact packs (rules/<JURISDICTION>.yaml): typed, dated facts with verbatim citations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import Any

import yaml

from . import config, sources


@dataclass(frozen=True)
class Citation:
    source_id: str
    quote: str


@dataclass(frozen=True)
class Fact:
    id: str
    jurisdiction: str
    topic: str
    statement: str
    value: Any
    unit: str | None
    effective_from: date | None
    effective_to: date | None
    known_from: date | None
    citations: tuple[Citation, ...]
    confidence: str = "high"
    notes: str = ""

    def in_force(self, on: date) -> bool:
        if self.effective_from and on < self.effective_from:
            return False
        if self.effective_to and on >= self.effective_to:
            return False
        return True

    def knowable(self, on: date) -> bool:
        """Was this fact published (in a captured source) by `on`? Drives the Time Machine."""
        return self.known_from is None or self.known_from <= on


def _d(v: Any) -> date | None:
    if v in (None, "", "null"):
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


@lru_cache(maxsize=1)
def _load() -> tuple[Fact, ...]:
    facts: list[Fact] = []
    for p in sorted(config.RULES_DIR.glob("*.yaml")):
        doc = yaml.safe_load(p.read_text()) or {}
        j = doc.get("jurisdiction", p.stem)
        for f in doc.get("facts", []) or []:
            facts.append(
                Fact(
                    id=f["id"],
                    jurisdiction=j,
                    topic=f.get("topic", ""),
                    statement=f.get("statement", ""),
                    value=f.get("value"),
                    unit=f.get("unit"),
                    effective_from=_d(f.get("effective_from")),
                    effective_to=_d(f.get("effective_to")),
                    known_from=_d(f.get("known_from")),
                    citations=tuple(Citation(c["source_id"], c["quote"]) for c in f.get("citations", []) or []),
                    confidence=f.get("confidence", "high"),
                    notes=f.get("notes", "") or "",
                )
            )
    return tuple(facts)


def reload() -> None:
    _load.cache_clear()
    sources.reload()


def all_facts() -> list[Fact]:
    return list(_load())


def facts_as_of(on: date, jurisdictions: set[str] | None = None, *, require_knowable: bool = True) -> list[Fact]:
    out = []
    for f in _load():
        if jurisdictions and f.jurisdiction not in jurisdictions:
            continue
        if not f.in_force(on):
            continue
        if require_knowable and not f.knowable(on):
            continue
        out.append(f)
    return out


def fact(fact_id: str, on: date | None = None) -> Fact | None:
    """Latest version of a fact id in force on `on` (or any version if on is None)."""
    cands = [f for f in _load() if f.id == fact_id and (on is None or f.in_force(on))]
    if not cands:
        return None
    return max(cands, key=lambda f: f.effective_from or date.min)


@dataclass
class CitationCheck:
    fact_id: str
    source_id: str
    ok: bool
    quote: str = field(repr=False, default="")


def verify_all() -> list[CitationCheck]:
    out = []
    for f in _load():
        for c in f.citations:
            out.append(CitationCheck(f.id, c.source_id, sources.verify_quote(c.source_id, c.quote), c.quote))
    return out
