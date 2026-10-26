# WorkReqBench

An open benchmark for questions about Medicaid community engagement (work) requirements. Each question is asked **as of a specific date**: the answer must be correct under the official rules published by that date.

## Why dates matter

The federal rule was published on 2026-06-03 and took effect on 2026-07-31. It was corrected on 2026-06-29. CMS issued frailty guidance on 2026-09-08. Nebraska started early (2026-05-01) and changed its process later. A model frozen at its training cutoff cannot know which of these applies on a given day.

## Question format

Questions live in `bench/questions/*.yaml`. Each one looks like this:

```yaml
- id: wr-0001
  split: dev            # dev | heldout. Held-out questions are never looked at while tuning the system.
  jurisdiction: NE      # US for federal-only questions
  as_of: 2026-10-01     # date the question is asked
  category: income_alternative   # timeline | applicability | requirement | income_alternative | lookback |
                                 # verification | exemption | good_cause | notice_cure | process | calculation | drift
  drift_sensitive: true # the correct answer differs at some other date on the timeline
  question: "..."       # phrased the way a navigator would ask it
  reference_answer: "..."   # short gold answer
  rubric:               # each criterion is graded pass/fail; question score = fraction passed
    - id: c1
      text: "States that the threshold is $580 per month (80 x $7.25)."
      kind: must_include        # must_include | must_not_claim
      citations:
        - {source_id: fed-ifr-2026-06-03, quote: "verbatim quote"}
```

## Integrity protocol

1. Questions, rubrics and citations are written from captured official sources only. Every rubric citation must pass `scripts/verify_citations.py --bench`.
2. Questions were drafted with AI assistance (Claude) from the sources, then reviewed. This is disclosed because a Claude model is also one of the systems compared.
3. The question files are committed and tagged before any benchmark run (`bench-v0-federal`, before the system was built; `bench-v0-nebraska`, after the Nebraska pipeline existed but before its first run). The held-out split is used only for final reporting.
4. Grading uses an LLM judge (Nemotron Ultra). The judge sees the question, its as-of date, the reference answer, the rubric criterion and the answer, but not which system produced the answer. Judge-vs-human agreement is measured on a random sample and reported.
5. Scores are reported with 95% bootstrap confidence intervals.

## Systems compared

| System | What it is |
|---|---|
| `frozen-super` | Nemotron Super, no sources. Told the question's as-of date. |
| `frozen-frontier` | A frontier model (Claude Opus 5.5), no sources, told the question's as-of date. Ran all 86 held-out questions. |
| `rag-latest` | Nemotron Super with the latest sources but **no as-of filtering**. A date-blind ablation. |
| `staycovered` | Nemotron Super with sources and rule facts **as of the question date**, plus verbatim citation checks. |

## Run

```
uv run python -m bench.run --split dev --systems frozen-super,staycovered
```
