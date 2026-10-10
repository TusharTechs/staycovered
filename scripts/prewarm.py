"""Pre-answer the demo's suggested questions at every Time Machine date, so judges' clicks cost nothing.

uv run python scripts/prewarm.py   -> data/cache/answers.json (committed)
"""

from __future__ import annotations

import json
import os
from datetime import date

os.environ["SC_RATE_PER_HOUR"] = "100000"  # local pre-warming is not subject to the visitor rate limit

from fastapi.testclient import TestClient

from staycovered import api, config

config.DAILY_USD_CAP = float("inf")

TM_QUESTIONS = [
    "When do Nebraska Medicaid work requirements start for people already enrolled?",
    "How is medical frailty verified?",
    "Does a spouse's income count toward the $580 income test?",
]
CASE_QUESTIONS = [
    "Does my client's spouse's income count toward the $580?",
    "How long does my client have to respond to a noncompliance notice?",
    "What documents can prove gig work hours in Nebraska?",
]
MT_TM_QUESTIONS = [
    "When does Montana start denying coverage for not meeting the requirement?",
    "How does Montana verify medical frailty?",
    "Does a spouse's income count toward the $580 income test in Montana?",
]
MT_CASE_QUESTIONS = [
    "Does my client's spouse's income count toward the $580 in Montana?",
    "How many qualifying months does my client need at redetermination?",
    "How do part-time college credit hours count?",
]
MT_DATES = ["2025-07-04", "2026-06-03", "2026-06-30", "2026-07-01", "2026-07-31", "2026-08-31", "2026-09-08", "2026-10-01",
            "2027-01-01", "2028-01-01"]
LABEL_DATES = ["2025-07-04", "2025-12-17", "2026-04-14", "2026-04-29", "2026-05-01", "2026-05-12", "2026-06-03", "2026-06-29",
               "2026-07-22", "2026-07-31", "2026-09-08", "2026-09-12", "2026-09-15", "2027-01-01", "2028-01-01"]


def main() -> None:
    c = TestClient(api.app)
    today = date.today().isoformat()
    jobs = ([(q, d, True, "NE") for q in TM_QUESTIONS for d in LABEL_DATES + [today]] + [(q, today, False, "NE") for q in CASE_QUESTIONS]
            + [(q, d, True, "MT") for q in MT_TM_QUESTIONS for d in MT_DATES + [today]] + [(q, today, False, "MT") for q in MT_CASE_QUESTIONS])
    if "--mt-only" in __import__("sys").argv:
        jobs = [j for j in jobs if j[3] == "MT"]
    for i, (q, d, cmp, j) in enumerate(jobs, 1):
        r = c.post("/api/ask", json={"question": q, "as_of": d, "jurisdiction": j, "compare_closed_book": cmp})
        print(i, len(jobs), d, r.status_code, q[:50])
    api.ANSWER_CACHE.parent.mkdir(parents=True, exist_ok=True)
    merged = json.loads(api.ANSWER_CACHE.read_text(encoding="utf-8")) if api.ANSWER_CACHE.exists() else {}
    merged |= json.loads(api.RUNTIME_ANSWERS.read_text(encoding="utf-8"))
    api.ANSWER_CACHE.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    print(f"cached {len(merged)} answers -> {api.ANSWER_CACHE}")


if __name__ == "__main__":
    main()
