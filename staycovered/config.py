"""Runtime configuration: environment, model routing, prices."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SOURCES_DIR = ROOT / "sources"
RULES_DIR = ROOT / "rules"
BENCH_DIR = ROOT / "bench"
ON_VERCEL = bool(os.getenv("VERCEL"))
# Serverless hosts have a read-only filesystem except /tmp; runtime logs and caches go there.
RUNTIME_DIR = Path("/tmp/staycovered-runtime") if ON_VERCEL else ROOT / "data" / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "")
NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


@dataclass(frozen=True)
class Model:
    id: str
    usd_per_m_in: float
    usd_per_m_out: float


# Verified against the Token Factory catalog on 2026-10-03 (research/tech_feasibility.md).
NANO = Model("nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B", 0.06, 0.24)
LIGHTNING = Model("nvidia/Nemotron-3_5-Lightning", 0.06, 0.24)
SUPER = Model("nvidia/nemotron-3-super-120b-a12b", 0.30, 0.90)
ULTRA = Model("nvidia/Nemotron-3-Ultra-550b-a55b", 1.00, 3.00)

MODELS = {m.id: m for m in (NANO, LIGHTNING, SUPER, ULTRA)}

# Job -> model. Extraction/rewriting is high-volume and cheap; reasoning over rules uses Super;
# the benchmark judge is a different, larger tier than the system under test.
ROUTES = {
    "extract": os.getenv("SC_MODEL_EXTRACT", NANO.id),
    "rewrite": os.getenv("SC_MODEL_REWRITE", NANO.id),
    "answer": os.getenv("SC_MODEL_ANSWER", SUPER.id),
    "drift_summary": os.getenv("SC_MODEL_DRIFT", SUPER.id),
    "judge": os.getenv("SC_MODEL_JUDGE", ULTRA.id),
}

# Public-demo protection: model spend per UTC day across all visitors (USD). Benchmarks set SC_DAILY_USD_CAP higher.
DAILY_USD_CAP = float(os.getenv("SC_DAILY_USD_CAP", "0.75"))
ADMIN_TOKEN = os.getenv("SC_ADMIN_TOKEN", "")
