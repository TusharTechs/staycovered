"""Lexical (BM25) retrieval over captured source snapshots, restricted to what existed on a date."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from . import sources

_TOK = re.compile(r"[a-z0-9$%.]+")
_STOP = set("the a an and or of to in for on by with is are be as at that this it from any each may must shall not no".split())


def tokens(text: str) -> list[str]:
    return [t.strip(".") for t in _TOK.findall(text.lower()) if t.strip(".") and t not in _STOP]


@dataclass(frozen=True)
class Chunk:
    source_id: str
    idx: int
    text: str


@lru_cache(maxsize=256)
def chunks_for(source_id: str, size: int = 900, overlap: int = 150) -> tuple[Chunk, ...]:
    t = sources.norm(sources.get(source_id).text)
    out, i, n = [], 0, 0
    while i < len(t):
        j = min(len(t), i + size)
        if j < len(t):  # end on a sentence boundary when possible
            k = t.rfind(". ", i + size // 2, j)
            if k > 0:
                j = k + 1
        out.append(Chunk(source_id, n, t[i:j].strip()))
        n += 1
        if j >= len(t):
            break
        i = max(j - overlap, i + 1)
    return tuple(out)


def rank_facts(query: str, facts: list, k: int = 24) -> list:
    """BM25 over fact statements + quotes; keeps the context focused on the question."""
    if len(facts) <= k:
        return facts
    texts = [tokens(f.statement + " " + f.topic + " " + " ".join(c.quote for c in f.citations)) for f in facts]
    df = Counter(t for ts in texts for t in set(ts))
    N = len(texts)
    avg = sum(len(ts) for ts in texts) / N
    q = tokens(query)
    scored = []
    for f, ts in zip(facts, texts):
        tf = Counter(ts)
        sc = sum(math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5)) * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(ts) / avg))
                 for t in q if t in tf)
        scored.append((sc, f))
    scored.sort(key=lambda x: -x[0])
    return [f for _, f in scored[:k]]


def search(query: str, on: date, jurisdictions: set[str] | None = None, k: int = 8) -> list[tuple[float, Chunk]]:
    docs: list[Chunk] = []
    for s in sources.sources_as_of(on, jurisdictions):
        if s.retrieval:
            docs.extend(chunks_for(s.id))
    if not docs:
        return []
    toks = [tokens(c.text) for c in docs]
    df = Counter(t for ts in toks for t in set(ts))
    N = len(docs)
    avg = sum(len(ts) for ts in toks) / N
    q = tokens(query)
    scored = []
    for c, ts in zip(docs, toks):
        tf = Counter(ts)
        s = 0.0
        for term in q:
            if term not in tf:
                continue
            idf = math.log(1 + (N - df[term] + 0.5) / (df[term] + 0.5))
            f = tf[term]
            s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(ts) / avg))
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return scored[:k]
