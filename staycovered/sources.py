"""Captured official sources: manifest, as-of lookup, and verbatim citation verification."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from . import config

_WS = re.compile(r"\s+")


def norm(text: str) -> str:
    """Normalisation used for every citation check: unify quotes/dashes, collapse whitespace."""
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
        .replace(" ", " ")
    )
    return _WS.sub(" ", text).strip()


@dataclass(frozen=True)
class Source:
    id: str
    jurisdiction: str
    title: str
    url: str
    as_of: date
    text_path: str
    wayback_url: str | None = None
    publisher: str = ""

    @property
    def text(self) -> str:
        return _read_text(self.text_path)


@lru_cache(maxsize=512)
def _read_text(path: str) -> str:
    return (config.ROOT / path).read_text(encoding="utf-8", errors="replace")


@lru_cache(maxsize=1)
def _manifest_raw() -> tuple[dict, ...]:
    p = config.SOURCES_DIR / "manifest.json"
    if not p.exists():
        return ()
    return tuple(json.loads(p.read_text()))


def reload() -> None:
    _manifest_raw.cache_clear()
    _read_text.cache_clear()


def all_sources() -> list[Source]:
    out = []
    for e in _manifest_raw():
        out.append(
            Source(
                id=e["id"],
                jurisdiction=e.get("jurisdiction", ""),
                title=e.get("title", ""),
                url=e.get("url", ""),
                as_of=date.fromisoformat(str(e["as_of"])[:10]),
                text_path=e["text_path"],
                wayback_url=e.get("wayback_url"),
                publisher=e.get("publisher", ""),
            )
        )
    return out


def get(source_id: str) -> Source:
    for s in all_sources():
        if s.id == source_id:
            return s
    raise KeyError(source_id)


def sources_as_of(on: date, jurisdictions: set[str] | None = None) -> list[Source]:
    """Sources that existed on a date. For the same URL, keep only the latest snapshot not after `on`."""
    latest: dict[str, Source] = {}
    for s in all_sources():
        if s.as_of > on:
            continue
        if jurisdictions and s.jurisdiction not in jurisdictions:
            continue
        key = s.url or s.id
        if key not in latest or s.as_of > latest[key].as_of:
            latest[key] = s
    return sorted(latest.values(), key=lambda s: (s.jurisdiction, s.id))


def verify_quote(source_id: str, quote: str) -> bool:
    try:
        return norm(quote) in norm(get(source_id).text)
    except (KeyError, FileNotFoundError):
        return False


def locate(source_id: str, quote: str, context: int = 240) -> str | None:
    """Return the quote with surrounding context from the normalised source text (for UI previews)."""
    try:
        t = norm(get(source_id).text)
    except (KeyError, FileNotFoundError):
        return None
    q = norm(quote)
    i = t.find(q)
    if i < 0:
        return None
    return t[max(0, i - context) : i + len(q) + context]
