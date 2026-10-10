"""Measure LLM-judge agreement with a human grader on a random sample of benchmark criteria.

1) Export:  uv run python scripts/judge_sample.py export --n 40   -> bench/results/judge_sample.csv
2) A human fills the `human_pass` column with y/n (without looking at `judge_pass`; it is the last column).
3) Score:   uv run python scripts/judge_sample.py score            -> prints agreement + Cohen's kappa, updates latest.json
"""

from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "bench" / "results"
CSV = R / "judge_sample.csv"


def latest_full() -> dict:
    files = sorted(p for p in R.glob("*.json") if p.name != "latest.json")
    return json.loads(files[-1].read_text(encoding="utf-8"))


def export(n: int) -> None:
    import yaml

    qs = {}
    for p in (R.parent / "questions").glob("*.yaml"):
        for q in yaml.safe_load(p.read_text(encoding="utf-8")):
            qs[q["id"]] = q
    res = latest_full()
    rows = []
    for system, recs in res["records"].items():
        for r in recs:
            if "grades" not in r:
                continue
            q = qs[r["qid"]]
            crit = {c["id"]: c for c in q["rubric"]}
            for g in r["grades"]:
                rows.append({"system": system, "qid": r["qid"], "as_of": q["as_of"], "question": q["question"],
                             "criterion_kind": crit[g["id"]].get("kind", "must_include"), "criterion": crit[g["id"]]["text"],
                             "answer": r["answer"][:2000], "human_pass": "", "judge_pass": "y" if g["passed"] else "n"})
    random.Random(11).shuffle(rows)
    rows = rows[:n]
    with CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {CSV}")


def score() -> None:
    graded = R / "grade_me.csv"
    if graded.exists():  # blind copy filled in by the human + separate key
        key = {r["row"]: r["judge_pass"] for r in csv.DictReader((R / "judge_key.csv").open(encoding="utf-8"))}
        rows = [{**r, "judge_pass": key[r["row"]]} for r in csv.DictReader(graded.open(encoding="utf-8"))
                if r["human_pass"].strip().lower() in ("y", "n")]
    else:
        rows = [r for r in csv.DictReader(CSV.open(encoding="utf-8")) if r["human_pass"].strip().lower() in ("y", "n")]
    if not rows:
        sys.exit("no graded rows")
    h = [r["human_pass"].strip().lower() == "y" for r in rows]
    j = [r["judge_pass"] == "y" for r in rows]
    n = len(rows)
    agree = sum(a == b for a, b in zip(h, j)) / n
    ph, pj = sum(h) / n, sum(j) / n
    pe = ph * pj + (1 - ph) * (1 - pj)
    kappa = (agree - pe) / (1 - pe) if pe < 1 else 1.0
    print(f"n={n} agreement={agree:.3f} kappa={kappa:.3f}")
    lp = R / "latest.json"
    if lp.exists():
        d = json.loads(lp.read_text(encoding="utf-8"))
        d.setdefault("judge", {})["human_agreement"] = round(agree, 3)
        d["judge"]["human_kappa"] = round(kappa, 3)
        d["judge"]["human_n"] = n
        lp.write_text(json.dumps(d, indent=2), encoding="utf-8")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "export"
    if cmd == "export":
        export(int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 40)
    else:
        score()
