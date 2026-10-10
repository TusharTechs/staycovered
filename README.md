# StayCovered

**AI models are frozen at their training date. Medicaid rules aren't.**

StayCovered is an open-source copilot for Medicaid navigators. It helps them keep people covered under the new community engagement ("work") requirements, starting with Nebraska. Every answer is grounded in the official rules *as of a specific date*, and open cases are re-checked when those rules change.

Built for the Nebius × NVIDIA Global AI Hackathon 2026 (Best Apps and Agents). Inference uses NVIDIA Nemotron on Nebius Token Factory; official-source monitoring uses Tavily.

**Live demo:** https://staycovered.vercel.app. Start with "Take the 90-second tour". Evidence for the problem is in [docs/EVIDENCE.md](docs/EVIDENCE.md).

## Results (WorkReqBench, held-out)

86 dated questions that were never inspected while building or tuning:

| System | Score (95% CI) | Questions whose answer changed over time |
|---|---|---|
| **StayCovered**: Nemotron Super + official rules as of the date | **72.9%** (65.7–79.5) | **66.7%** |
| Nemotron Super + today's sources (date-blind) | 65.5% | 48.5% |
| Claude Opus 5.5 answering from memory | 63.0% (55.6–70.2) | 44.6% |
| Nemotron Super answering from memory | 35.3% | 27.0% |

Paired comparison on the same questions:

| StayCovered compared with | Overall gap (95% CI) | Date-sensitive gap (95% CI) |
|---|---|---|
| Claude Opus 5.5 | **+9.9 points** (+1.0 to +18.4) | **+22.1 points** (+8.3 to +36.3) |

How to read this:
- On federal questions the two systems are roughly tied (71% vs 70%). The advantage comes from Nebraska rules (75% vs 54%) and rules that changed over time.
- The ranking is the same under three graders: Nemotron Ultra, Nemotron Super and Claude Haiku. Details are in `bench/` and on the WorkReqBench page.

> StayCovered organises evidence against published rules. It does **not** decide eligibility or exemptions; the state agency does. All demo cases are synthetic.

## Why

- Under H.R.1, every Medicaid expansion state must verify work or community engagement from **January 1, 2027**.
- Nebraska started early, in May 2026. In its first months, most coverage losses at renewal were people not responding to information requests, rather than people found non-compliant (see `research/`).
- The rules are still moving:
  - an interim final rule (June 2026)
  - a correction (June 29)
  - CMS frailty guidance (Sept 8)
  - state process changes
- A model trained before those dates gives confidently stale answers.

## What it does

| Feature | What it means |
|---|---|
| **Attestation worksheet** | Messy client documents become a month-by-month worksheet against the 80-hour / $580 test. Inputs include gig-app weekly statements, pay stubs and volunteer letters. **Code does all arithmetic.** Every number links to the exact line in the client's document. Household MAGI income, the income-to-hours conversion, seasonal six-month averaging and weeks that cross months are handled explicitly. Gig payouts before expenses produce *"meets if expenses are ≤ $X"* instead of a false "meets". |
| **Grounded answers, as of a date** | Nemotron Super answers from the rule facts and official passages that existed on the chosen date. Citations are checked verbatim against the captured source, and a second, cheap check (Nemotron Nano) confirms each quote actually supports the answer. Anything unsupported becomes "can't confirm — check with the agency". |
| **Rule Time Machine** | Move through the real policy timeline and watch the rules, the answers and the caseload change. A frozen model's answer sits side by side for comparison. |
| **drift-watch** | Tavily Extract/Map monitors an allow-list of official pages. When text changes, Nemotron summarises the diff. Rule facts whose quoted text disappeared are marked stale, and cases that relied on them are flagged for re-check. Only allow-listed public URLs are ever sent to Tavily; the request log proves it. |
| **Packet** | A PDF with the worksheet, evidence index, items to confirm with the agency, possible exemptions to raise, and the exact rules used. |
| **Nebraska's real MLTC-118 form** | The state's actual Individual Declaration Form, pre-filled only where evidence exists. Each field shows its reason. SSN, date of birth and signatures are never filled. |
| **Snap a photo** | Photos are read by OCR in the browser, so the image never leaves the device. PDFs use their text layer. The navigator reviews the text before Nemotron extracts it. |
| **Always-on drift-watch** | A daily GitHub Actions job checks the official pages with Tavily and summarises real changes with Nemotron. It commits the status, and the site redeploys showing "last checked". |
| **Guided tour** | A 9-step, 90-second walkthrough for first-time visitors. |
| **Two states** | **Nebraska** and **Montana**, switchable in the header. The same household can get different results under each state's published rules. For example, a spouse's income counts toward $580 in Montana but only "may count" in Nebraska in 2026. Montana also needs 3 qualifying months at renewal and converts part-time credit hours to 13 hours each. |
| **Accessible** | 0 axe-core violations on every page (WCAG 2.2 AA plus best practices). Keyboard operable with visible focus, live regions for answers, honours reduced-motion settings, responsive down to phone width, and a Spanish client view. |
| **WorkReqBench** | An open benchmark of dated questions with rubrics cited to official text. See [`bench/README.md`](bench/README.md). |

## Models (Nebius Token Factory)

| Job | Model |
|---|---|
| Extraction, plain-language rewrite, citation entailment check | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` |
| Grounded answers, rule-change summaries | `nvidia/nemotron-3-super-120b-a12b` (reasoning on) |
| Benchmark judge | `nvidia/Nemotron-3-Ultra-550b-a55b` |

Every call is logged with its tokens, cost and latency (*Under the hood* page).

## Repository

```
rules/        fact packs: typed, dated facts with verbatim citations (US.yaml, NE.yaml, ...)
sources/      captured official documents (raw + text + manifest.json with url, as_of, sha256)
staycovered/  engine (deterministic), answer (grounded QA), extract, drift (drift-watch), api, packet
bench/        WorkReqBench questions, runner, judge, results
web/          React app: Caseload, Case, Rule Time Machine, WorkReqBench, Under the hood
demo/         synthetic caseload with gold-standard extraction labels
research/     problem, market and competition research behind the project
```

## Run locally

```bash
cp .env.example .env            # add NEBIUS_API_KEY and TAVILY_API_KEY
uv sync
uv run python -m demo.seed      # synthetic caseload
uv run uvicorn staycovered.api:app --port 8000
pnpm --dir web install && pnpm --dir web dev   # http://localhost:5173
```

Tests and checks:

```bash
uv run --group dev pytest
uv run --with pyyaml python scripts/verify_citations.py --bench   # every rule fact and rubric quote verified verbatim
uv run python -m bench.run --split dev
```

## Honesty notes

- Rule facts and benchmark questions were drafted with AI assistance from captured official sources. Every quote is machine-verified against the source text, and the files were committed before system tuning (tag `bench-v0-federal`).
- The benchmark is self-built. Its construction, judge and limitations are documented in `bench/README.md`.
- No real client data has been processed. For real use, enable Zero Data Retention on Nebius Token Factory.

## License

Apache-2.0
