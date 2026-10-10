# Feedback on Nebius Token Factory, NVIDIA Nemotron and Tavily

These notes come from building StayCovered between 2026-10-09 and 2026-10-30. The numbers are from our own call logs (`data/runtime/calls.jsonl`). As of 2026-10-10 the logs held 1,171 Token Factory calls, about 2.3M tokens, at a total cost of **$1.05**.

## What worked well

| Area | Observation |
|---|---|
| **OpenAI compatibility** | We used the standard `openai` Python SDK with `base_url=https://api.tokenfactory.nebius.com/v1/` and changed nothing else. `models.list()` returned all four Nemotron models. |
| **Structured output** | `response_format={"type": "json_schema", ...}` worked on Nemotron 3 Nano, 3.5 Lightning and 3 Super, even though the catalog does not tag these models with "JSON mode". In about 1,100 structured calls we never had to fall back to prompt-only JSON. |
| **Price and performance** | Nano: 355 calls, p50 1.4 s, $0.036 in total. Super, with reasoning on: 273 calls, p50 5.0 s, $0.71. Ultra (as the benchmark judge): 540 calls, p50 0.7 s, $0.30. A complete 47-question benchmark run across three systems, including judging, cost about $0.50. |
| **Reliability** | No retries were needed. We saw no 429s or 5xx errors at our volume, with up to 6 parallel workers. |
| **Model ladder** | Nano for extraction, Super for grounded reasoning and Ultra for judging gave a natural cost and quality split on one API. |
| **Tavily Extract** | It fetched `dhhs.ne.gov` pages in about 2 s, while our own direct `curl` requests to the same site timed out repeatedly. One call covered 8 official pages across 5 states. |

## Friction and suggestions

### 1. Nemotron reasoning toggle is undocumented on Token Factory

We pass `extra_body={"chat_template_kwargs": {"enable_thinking": true/false}}`, which the server accepts, and latency changes as expected. However:

- The docs don't say whether this is the supported switch.
- They don't say whether `reasoning_effort` maps to it.
- They don't say where the reasoning text goes; it never appeared in `content`.

**Suggestion:** a short "Nemotron reasoning on Token Factory" page with one example.

### 2. The catalog under-reports capabilities

The model pages don't list JSON or structured output for Nemotron, yet it works. Developers reading the catalog would assume they need prompt-only JSON. **Suggestion:** show a "structured output: tested" badge for each model.

### 3. No Nemotron fine-tuning

The fine-tuning catalog covers Llama, Qwen, Gemma, gpt-oss and DeepSeek, but no Nemotron base. For a hackathon centred on Nemotron, a LoRA path for Nano would be valuable, for example distilling Super's behaviour into Nano for extraction.

### 4. No vision or speech Nemotron on serverless

Real client documents are photographed pay stubs. With only text models on serverless, OCR has to happen outside the platform. **Suggestion:** a serverless Nemotron VLM, or document-parse endpoint.

### 5. Model retirement churn

Models were removed from serverless on 2026-06-22 and 2026-08-31 with no automatic rerouting. **Suggestion:** stable aliases (e.g. `nemotron-super-latest`) plus a deprecation header on responses well before removal.

### 6. Data retention

The Legal Quick Guide is clear: content is not used for training, inputs may be retained for speculative decoding unless ZDR is enabled, and ZDR is an organisation-level toggle. However:

- It is unclear whether ZDR is available on accounts running on hackathon credits.
- For a tool that handles Medicaid documents, ZDR is the deciding factor.

**Suggestion:** mention ZDR in the onboarding flow, and offer it on trial accounts.

### 7. Onboarding

- Many hackathon participants reported that their country was missing from the billing list.
- The $1 trial credit is small for evaluating a 550B model.

## Nemotron behaviour worth knowing (with our mitigations)

| Behaviour | Mitigation |
|---|---|
| Super sometimes cited our internal fact IDs instead of document IDs. | Resolve fact IDs to their source documents in code; clearer prompt wording. |
| Super paraphrased "quotes" slightly, so verbatim checks failed. | Fuzzy repair (at least 90% similar) maps each quote back to the exact source text. If nothing verifies, one retry. |
| With an "as of" date in June, Super described a July event in the past tense. | Explicit tense rule in the system prompt. |
| Nano mislabelled gig payouts as wages, and skipped hours rows on pay stubs. | Redesign: the model labels *what each number is* and copies it exactly; deterministic code parses and classifies. One worked example in the prompt fixed the missing pay-stub hours. Held-out extraction F1 rose from 0.45 to 0.995. |
| Prompt injection inside documents. | Out of 7 held-out documents with injected instructions, none produced inflated numbers. Document text is treated as data, and extraction has no tools. |

## Tavily-specific

- `extract` returns Markdown. We strip link targets and markup before diffing, so formatting differences are not mistaken for rule changes.
- Comparing Tavily captures with archive captures made by a different HTML-to-text method produces false "changes". We compare like with like only.
- The privacy policy advises against personal data in queries. Rule monitoring sends only allow-listed official URLs; the nearby-programs search sends only a city name and the activity type. Our request log shows both.
