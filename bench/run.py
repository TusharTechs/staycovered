"""WorkReqBench runner + judge.

uv run python -m bench.run --split dev --systems frozen-super,rag-latest,staycovered [--limit N] [--max-usd 2]
Writes bench/results/<timestamp>.json and bench/results/latest.json (read by the web app).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

from staycovered import answer as ans
from staycovered import config, llm

config.DAILY_USD_CAP = float("inf")  # offline evaluation is not subject to the public demo cap

QDIR = Path(__file__).parent / "questions"
RDIR = Path(__file__).parent / "results"
RDIR.mkdir(exist_ok=True)


def load_questions(split: str | None = None) -> list[dict]:
    qs = []
    for p in sorted(QDIR.glob("*.yaml")):
        for q in yaml.safe_load(p.read_text(encoding="utf-8")) or []:
            q["as_of"] = str(q["as_of"])
            if split in (None, "all") or q.get("split") == split:
                qs.append(q)
    return qs


# ---------------- systems ----------------

def sys_frozen(q: dict, model: str) -> dict:
    out = llm.chat(
        "answer",
        [
            {"role": "system", "content": f"You help Medicaid navigators. Today's date is {q['as_of']}. Answer accurately and concisely."},
            {"role": "user", "content": f"State: {q['jurisdiction']}. {q['question']}"},
        ],
        model=model, tag="bench_frozen", max_tokens=1500,
    )
    return {"answer": llm._THINK.sub("", out).strip()}


FRONTIER_MODEL = os.getenv("SC_FRONTIER_MODEL", "claude-opus-5-5")
FRONTIER_PRICE = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
FRONTIER_CAP_USD = float(os.getenv("SC_FRONTIER_CAP_USD", "6"))
FRONTIER_LOG = config.RUNTIME_DIR / "frontier_calls.jsonl"


def frontier_spent() -> float:
    if not FRONTIER_LOG.exists():
        return 0.0
    return sum(json.loads(l).get("usd", 0) for l in FRONTIER_LOG.read_text(encoding="utf-8").splitlines() if l.strip())


def sys_frontier(q: dict) -> dict:
    """Frontier model with no sources (frozen at its training date), told the question's date."""
    import anthropic

    if frontier_spent() >= FRONTIER_CAP_USD:
        raise RuntimeError(f"frontier spend cap ${FRONTIER_CAP_USD} reached")
    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=FRONTIER_MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=f"You help Medicaid navigators. Today's date is {q['as_of']}. Answer accurately and concisely.",
        messages=[{"role": "user", "content": f"State: {q['jurisdiction']}. {q['question']}"}],
    )
    pin, pout = FRONTIER_PRICE.get(FRONTIER_MODEL, (4.0, 20.0))
    u = resp.usage
    usd = (u.input_tokens * pin + u.output_tokens * pout) / 1e6
    served_by = resp.model
    with FRONTIER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "model": FRONTIER_MODEL, "served_by": served_by, "in": u.input_tokens,
                            "out": u.output_tokens, "usd": round(usd, 6), "stop": resp.stop_reason}) + "\n")
    if resp.stop_reason == "refusal":
        return {"answer": "(model declined to answer)", "model": served_by}
    text = "".join(b.text for b in resp.content if b.type == "text")
    return {"answer": text, "model": served_by, "fallback": served_by != FRONTIER_MODEL}


def sys_staycovered(q: dict, *, date_aware: bool = True) -> dict:
    on = date.fromisoformat(q["as_of"]) if date_aware else date.today()
    r = ans.answer(q["question"], q["jurisdiction"], on)  # federal questions get federal sources only
    return {"answer": r.answer, "citations": r.citations, "dropped": r.dropped_citations, "unsupported": r.unsupported}


SYSTEMS = {
    "frozen-super": lambda q: sys_frozen(q, config.SUPER.id),
    "frozen-nano": lambda q: sys_frozen(q, config.NANO.id),
    "frozen-frontier": sys_frontier,
    "rag-latest": lambda q: sys_staycovered(q, date_aware=False),
    "staycovered": sys_staycovered,
}

MODEL_OF = {"frozen-super": config.SUPER.id, "frozen-nano": config.NANO.id, "rag-latest": config.SUPER.id,
            "staycovered": config.SUPER.id, "frozen-frontier": FRONTIER_MODEL}


# ---------------- judge ----------------

class Verdict(BaseModel):
    passed: bool
    reason: str


JUDGE_SYS = """You grade answers to questions about Medicaid work requirements against ONE rubric criterion.
- must_include: pass only if the answer clearly states the criterion's content (paraphrase is fine; numbers and dates must match).
- must_not_claim: pass only if the answer does NOT make the claim described.
Judge only this criterion. Do not reward extra detail. Do not penalise for other errors."""


def _claude_verdict(model: str, prompt: str) -> Verdict:
    """Cross-family judge (Claude) via the official SDK's structured-output parsing; spend is logged and capped."""
    import anthropic

    if frontier_spent() >= FRONTIER_CAP_USD:
        raise RuntimeError(f"Anthropic spend cap ${FRONTIER_CAP_USD} reached")
    resp = anthropic.Anthropic().messages.parse(
        model=model, max_tokens=4000, system=JUDGE_SYS,
        messages=[{"role": "user", "content": prompt}], output_format=Verdict,
    )
    pin, pout = FRONTIER_PRICE.get(model, (4.0, 20.0))
    usd = (resp.usage.input_tokens * pin + resp.usage.output_tokens * pout) / 1e6
    with FRONTIER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "model": model, "role": "judge", "in": resp.usage.input_tokens,
                            "out": resp.usage.output_tokens, "usd": round(usd, 6), "stop": resp.stop_reason}) + "\n")
    if resp.parsed_output is None:
        raise RuntimeError(f"judge returned no parsed output (stop={resp.stop_reason})")
    return resp.parsed_output


def judge(q: dict, answer_text: str) -> list[dict]:
    model = config.ROUTES["judge"]
    out = []
    for c in q["rubric"]:
        prompt = (f"Question (asked as of {q['as_of']}):\n{q['question']}\n\nReference answer:\n{q.get('reference_answer', '')}\n\n"
                  f"Criterion ({c.get('kind', 'must_include')}):\n{c['text']}\n\nAnswer to grade:\n{answer_text}")
        if model.startswith("claude"):
            v = _claude_verdict(model, prompt)
        else:
            v = llm.structured("judge", JUDGE_SYS, prompt, Verdict, tag="bench_judge", max_tokens=600)
        out.append({"id": c["id"], "passed": v.passed, "reason": v.reason})
    return out


# ---------------- stats ----------------

def bootstrap(xs: list[float], n: int = 2000, seed: int = 7) -> tuple[float, float]:
    if not xs:
        return 0.0, 0.0
    rnd = random.Random(seed)
    means = sorted(sum(rnd.choice(xs) for _ in xs) / len(xs) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def spent(since: float) -> float:
    if not llm.CALL_LOG.exists():
        return 0.0
    return sum(json.loads(l)["usd"] for l in llm.CALL_LOG.read_text(encoding="utf-8").splitlines() if l.strip() and json.loads(l)["ts"] >= since)


def run(split: str, systems: list[str], limit: int | None, max_usd: float, workers: int, reuse: list[str] | None = None) -> dict:
    qs = load_questions(split)
    if limit:
        qs = qs[:limit]
    t0 = time.time()
    records: dict[str, list[dict]] = {s: [] for s in systems}
    if reuse:  # carry over unchanged systems from the latest full run of this split
        prev = sorted(RDIR.glob(f"*-{split}.json"))
        if prev:
            old = json.loads(prev[-1].read_text(encoding="utf-8"))["records"]
            for s in reuse:
                if s in old:
                    records[s] = old[s]

    def one(sname: str, q: dict) -> dict:
        if spent(t0) > max_usd:
            return {"qid": q["id"], "error": "budget"}
        try:
            res = SYSTEMS[sname](q)
            grades = judge(q, res["answer"])
            score = sum(g["passed"] for g in grades) / len(grades)
            return {"qid": q["id"], "category": q["category"], "as_of": q["as_of"], "drift_sensitive": q.get("drift_sensitive", False),
                    "score": score, "grades": grades, **res}
        except Exception as e:  # noqa: BLE001
            return {"qid": q["id"], "error": f"{type(e).__name__}: {str(e)[:300]}"}

    for sname in [x for x in systems if not (reuse and x in reuse and records.get(x))]:
        w = 2 if sname == "frozen-frontier" else workers
        with ThreadPoolExecutor(w) as ex:
            records[sname] = list(ex.map(lambda q: one(sname, q), qs))
        ok = [r for r in records[sname] if "score" in r]
        print(f"{sname}: {len(ok)}/{len(qs)} scored, mean {sum(r['score'] for r in ok) / max(1, len(ok)):.3f}")

    rows, by_cat = [], {}
    for sname, recs in records.items():
        ok = [r for r in recs if "score" in r]
        xs = [r["score"] for r in ok]
        lo, hi = bootstrap(xs)
        row = {"system": sname, "model": MODEL_OF.get(sname, ""), "score": sum(xs) / max(1, len(xs)), "ci_low": lo, "ci_high": hi,
               "n": len(xs), "errors": len(recs) - len(ok)}
        if sname in ("staycovered", "rag-latest"):
            cits = [c for r in ok for c in r.get("citations", [])]
            dropped = sum(r.get("dropped", 0) for r in ok)
            row["citation_validity"] = len(cits) / max(1, len(cits) + dropped)
            row["unsupported_rate"] = sum(1 for r in ok if r.get("unsupported")) / max(1, len(ok))
        drift = [r["score"] for r in ok if r.get("drift_sensitive")]
        row["drift_sensitive_score"] = sum(drift) / len(drift) if drift else None
        rows.append(row)
        for r in ok:
            by_cat.setdefault(r["category"], {}).setdefault(sname, []).append(r["score"])

    result = {
        "version": "bench-v0", "split": split, "date": date.today().isoformat(), "n_questions": len(qs),
        "systems": rows,
        "by_category": {c: {s: sum(v) / len(v) for s, v in d.items()} for c, d in sorted(by_cat.items())},
        "judge": {"model": config.ROUTES["judge"], "human_agreement": None},
        "notes": [
            "Questions and rubrics were drafted with AI assistance from captured official sources, reviewed, and committed before tuning.",
            "Every rubric criterion cites verbatim official text (verified by script).",
            "Each question is asked 'as of' a date; frozen models are told that date.",
            "rag-latest is an ablation: the same pipeline with today's sources, ignoring the question date.",
        ],
        "records": records,
        "nemotron_usd": round(spent(t0), 4),
        "frontier_usd_total": round(frontier_spent(), 4),
    }
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    (RDIR / f"{stamp}-{split}.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    (RDIR / "latest.json").write_text(json.dumps({k: v for k, v in result.items() if k != "records"}, indent=2, default=str), encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--systems", default="frozen-super,rag-latest,staycovered")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-usd", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--reuse", default="", help="comma-separated systems to copy from the latest run of this split")
    a = ap.parse_args()
    run(a.split, a.systems.split(","), a.limit, a.max_usd, a.workers, [x for x in a.reuse.split(",") if x])


if __name__ == "__main__":
    main()
