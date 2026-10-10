"""Robustness check: re-grade an existing run's answers with a different judge model and compare rankings.

uv run python -m bench.rejudge --split dev --judge nvidia/nemotron-3-super-120b-a12b
Writes bench/results/rejudge-<split>-<model>.json and prints scores under both judges.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor

from staycovered import config

config.DAILY_USD_CAP = float("inf")  # offline evaluation is not subject to the public demo cap

from .run import RDIR, bootstrap, judge, load_questions


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--judge", default=config.SUPER.id)
    a = ap.parse_args()

    src = sorted(p for p in RDIR.glob(f"*-{a.split}.json"))[-1]
    res = json.loads(src.read_text())
    qs = {q["id"]: q for q in load_questions(a.split)}
    orig_judge = config.ROUTES["judge"]
    config.ROUTES["judge"] = a.judge
    out = {"source": src.name, "judge": a.judge, "original_judge": orig_judge, "systems": {}}
    try:
        for sname, recs in res["records"].items():
            ok = [r for r in recs if "score" in r]

            def one(r: dict) -> float | None:
                try:
                    g = judge(qs[r["qid"]], r["answer"])
                    return sum(x["passed"] for x in g) / len(g)
                except Exception:  # noqa: BLE001
                    return None

            with ThreadPoolExecutor(6) as ex:
                new = list(ex.map(one, ok))
            pairs = [(r["score"], n) for r, n in zip(ok, new) if n is not None]
            xs = [n for _, n in pairs]
            lo, hi = bootstrap(xs)
            out["systems"][sname] = {"original": sum(o for o, _ in pairs) / len(pairs), "rejudged": sum(xs) / len(xs),
                                     "ci_low": lo, "ci_high": hi, "n": len(pairs),
                                     "agreement_per_question": sum(1 for o, n in pairs if abs(o - n) < 1e-9) / len(pairs)}
    finally:
        config.ROUTES["judge"] = orig_judge
    (RDIR / f"rejudge-{a.split}-{a.judge.split('/')[-1]}.json").write_text(json.dumps(out, indent=2))
    for s, v in sorted(out["systems"].items(), key=lambda kv: -kv[1]["rejudged"]):
        print(f"{s:16s} {orig_judge.split('/')[-1]}: {v['original']:.3f}   {a.judge.split('/')[-1]}: {v['rejudged']:.3f} "
              f"[{v['ci_low']:.3f}-{v['ci_high']:.3f}]  same-score questions {v['agreement_per_question']:.0%}")


if __name__ == "__main__":
    main()
