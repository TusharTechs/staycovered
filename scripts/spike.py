"""Day-1 spike: verify Token Factory models, structured output, reasoning toggle, and Tavily extract.

Run: uv run python scripts/spike.py
Never prints API keys.
"""

from __future__ import annotations

import json
import time

from pydantic import BaseModel

from staycovered import config, llm


class Probe(BaseModel):
    month: str
    hours: float
    payer: str


DOC = "DashBite Driver — Week of Aug 3, 2026 – Aug 9, 2026. Total payout: $201.55. Active time: 16 hr 5 min."


def main() -> None:
    print("NEBIUS key set:", bool(config.NEBIUS_API_KEY), "| TAVILY key set:", bool(config.TAVILY_API_KEY))
    ids = [m.id for m in llm.client().models.list().data]
    nem = sorted(i for i in ids if "emotron" in i)
    print(f"{len(ids)} models available; Nemotron: {nem}")
    for m in config.MODELS:
        print(f"  {m}: {'OK' if m in ids else 'MISSING'}")

    for mid in [config.NANO.id, config.LIGHTNING.id, config.SUPER.id]:
        if mid not in ids:
            continue
        t0 = time.time()
        try:
            r = llm.structured("extract", "Extract the fields.", DOC + "\nReturn month as YYYY-MM of the week start.", Probe, model=mid, tag="spike")
            print(f"  structured {mid}: {r.model_dump()} in {time.time() - t0:.1f}s")
        except Exception as e:  # noqa: BLE001
            print(f"  structured {mid}: FAILED {str(e)[:200]}")
        for think in (False, True):
            t0 = time.time()
            try:
                out = llm.chat("answer", [{"role": "user", "content": "In one sentence: what is 80 times 7.25?"}], model=mid,
                               reasoning=think, max_tokens=800, tag=f"spike_think_{think}")
                print(f"  reasoning={think} {mid}: {len(out)} chars, think-tags={'<think>' in out}, {time.time() - t0:.1f}s :: {out[-120:]!r}")
            except Exception as e:  # noqa: BLE001
                print(f"  reasoning={think} {mid}: FAILED {str(e)[:200]}")

    if config.TAVILY_API_KEY:
        from staycovered.drift import watch

        t0 = time.time()
        try:
            got = watch.tavily_extract(["https://dhhs.ne.gov/Pages/WorkRequirements.aspx"])
            for u, t in got.items():
                print(f"  tavily extract {u}: {len(t)} chars in {time.time() - t0:.1f}s; starts {t[:150]!r}")
        except Exception as e:  # noqa: BLE001
            print("  tavily extract FAILED", str(e)[:300])

    calls = [json.loads(x) for x in llm.CALL_LOG.read_text().splitlines() if '"spike' in x]
    print(f"spike cost: ${sum(c['usd'] for c in calls):.5f} over {len(calls)} calls")


if __name__ == "__main__":
    main()
