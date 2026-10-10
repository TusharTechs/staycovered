"""Summarise logged Token Factory and Tavily usage into data/cache/usage_summary.json (committed for the public demo)."""

from __future__ import annotations

import json
import statistics as st
from collections import defaultdict
from datetime import datetime, timezone

from staycovered import config
from staycovered.drift import watch
from staycovered.llm import CALL_LOG


def main() -> None:
    calls = [json.loads(line) for line in CALL_LOG.read_text().splitlines() if line.strip()]
    by = defaultdict(list)
    for c in calls:
        by[(c["model"], c["job"])].append(c)
    rows = []
    for (model, job), cs in sorted(by.items()):
        lat = sorted(c["latency_s"] for c in cs)
        rows.append({"model": model, "job": job, "calls": len(cs), "tokens": sum((c["prompt_tokens"] or 0) + (c["completion_tokens"] or 0) for c in cs),
                     "usd": round(sum(c["usd"] for c in cs), 4), "p50_latency_s": round(st.median(lat), 2)})
    tav = [json.loads(line) for line in watch.TAVILY_LOG.read_text().splitlines() if line.strip()] if watch.TAVILY_LOG.exists() else []
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "total_calls": len(calls),
           "total_usd": round(sum(c["usd"] for c in calls), 3), "rows": rows,
           "tavily": [{"ts": t["ts"], "kind": t["kind"], "urls": t["payload"].get("urls") or [t["payload"].get("url")], "results": t["results"], "ok": t["ok"]} for t in tav]}
    p = config.ROOT / "data" / "cache" / "usage_summary.json"
    p.write_text(json.dumps(out, indent=1))
    print(f"{len(calls)} calls, ${out['total_usd']} -> {p}")


if __name__ == "__main__":
    main()
