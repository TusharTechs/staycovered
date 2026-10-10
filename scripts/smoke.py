"""API smoke test with no API keys: every deterministic endpoint and a cached answer must work (run in CI on every OS)."""

from __future__ import annotations

import os
import sys

os.environ["NEBIUS_API_KEY"] = ""
os.environ["TAVILY_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from staycovered import api, config  # noqa: E402

config.NEBIUS_API_KEY = config.TAVILY_API_KEY = ""
c = TestClient(api.app)
GET = ["/api/health", "/api/cases", "/api/cases/maria-lopez", "/api/cases/dani-ortiz/plan", "/api/forecast?jurisdiction=MT",
       "/api/sandbox?jurisdiction=NE&ex_parte=true", "/api/timeline", "/api/drift/replay", "/api/facts", "/api/bench/results",
       "/api/cases/maria-lopez/packet.pdf", "/api/cases/maria-lopez/mltc118.pdf", "/api/cases/tom-becker/reminders.ics",
       "/api/cases/dani-ortiz/nearby?kind=volunteer"]
failed = []
for u in GET:
    r = c.get(u)
    print(r.status_code, u)
    if r.status_code != 200:
        failed.append(u)
r = c.post("/api/selfcheck", json={"jurisdiction": "NE", "work_hours": 34, "wages": 510, "volunteer_hours": 18})
print(r.status_code, "/api/selfcheck", r.json().get("status"))
if r.status_code != 200 or r.json()["status"] != "does_not_meet":
    failed.append("/api/selfcheck")
r = c.post("/api/ask", json={"question": "Does my client's spouse's income count toward the $580?", "as_of": "2026-10-10", "jurisdiction": "NE"})
print(r.status_code, "/api/ask (cached)")
if r.status_code != 200:
    failed.append("/api/ask cached")
r = c.post("/api/ask", json={"question": "Does my client's spouse's income count toward the $580?", "as_of": "2026-12-07", "jurisdiction": "NE"})
print(r.status_code, "/api/ask (cached by knowledge state, judging-week date)", r.json().get("same_rules_as"))
if r.status_code != 200:
    failed.append("/api/ask knowledge-state cache")
r = c.post("/api/ask", json={"question": "An uncached question with no key configured?", "as_of": "2026-10-10", "jurisdiction": "NE"})
print(r.status_code, "/api/ask (uncached, no key) ->", r.json().get("detail", "")[:60])
if r.status_code != 503:
    failed.append("/api/ask uncached should be 503")
sys.exit(f"FAILED: {failed}" if failed else 0)
