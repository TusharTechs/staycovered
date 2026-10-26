"""Re-review every live drift-watch event with the current, stricter logic (re-runnable; writes the committed log).

Model votes on borderline edits can differ between runs; the deterministic guards (boilerplate filter, link-target
normalisation, rule-term check, partial-capture rule) do not.

Per page, in date order, each capture is compared with the last *accepted* capture (not a half-size one):
- a capture that shrank by more than 40% and recovered later is a transient partial capture (ignored);
- one that stayed shrunken on later checks is a confirmed rewrite;
- otherwise the diff (without site boilerplate) is re-summarised with the stricter 'substantive' definition, and the
  verdict is the majority of three independent Nemotron Super judgements (borderline edits are unstable on one call);
- rule facts whose cited quote was in the accepted capture and is gone now are listed, even after a rewording.
The first summary is kept for transparency.

uv run python scripts/review_drift.py
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date

from staycovered import config, sources
from staycovered.drift import watch

config.DAILY_USD_CAP = float("inf")


def main() -> None:
    log = json.loads(watch.LIVE_EVENTS.read_text(encoding="utf-8"))
    by_url = defaultdict(list)
    for e in log:
        by_url[e["url"]].append(e)
    status = json.loads(watch.STATUS.read_text(encoding="utf-8"))
    for url, evs in by_url.items():
        evs.sort(key=lambda e: e["new_as_of"])
        base_id = evs[0]["old_id"]
        for i, e in enumerate(evs):
            old, new = sources.get(base_id).text, sources.get(e["new_id"]).text
            e.setdefault("first_summary", e.get("summary"))
            e["compared_with"] = base_id
            if watch._words(new) < watch.PARTIAL * watch._words(old):
                later = [x for x in evs[i + 1:] if watch._words(sources.get(x["new_id"]).text) >= watch.PARTIAL * watch._words(old)]
                if later:
                    e["classification"], e["summary"], e["stale_facts"], e["affected_cases"] = "transient partial capture", None, [], []
                    e["review_note"] = (f"Page text dropped from {watch._words(old)} to {watch._words(new)} words and was back to full "
                                        f"size on {later[0]['new_as_of']}: a capture glitch, ignored.")
                    continue
                e["review_note"] = (f"Page text dropped from {watch._words(old)} to {watch._words(new)} words and stayed that way on "
                                    f"every later check through {status.get('last_checked', '')[:10]}: a real rewrite.")
            added, removed = watch.diff_texts(old, new)
            e["added"], e["removed"] = added[:25], removed[:25]
            e["stale_facts"] = watch.stale_facts_live(url, old, new)
            if not (added or removed):
                e["summary"], subst = None, False
            else:
                d = watch.Diff(url, base_id, e["new_id"], sources.get(base_id).as_of.isoformat(), e["new_as_of"], added, removed)
                runs = [watch.summarize(d, e["title"], temperature=0.7).model_dump() for _ in range(3)]  # majority of 3 independent judgements
                votes = [r["substantive"] for r in runs]
                subst = sum(votes) >= 2 and watch.rule_bearing(d)  # the changed lines must mention rule content
                e["summary"] = next(r for r in runs if r["substantive"] == subst) | {"votes": f"{sum(votes)} of 3 judged substantive", "rule_terms_in_diff": watch.rule_bearing(d)}
            if "review_note" in e:  # shrank and stayed shrunken: a structural rewrite, whatever the vote on wording
                e["classification"] = "confirmed rewrite"
            else:
                e["classification"] = "rule change" if subst else ("reworded: cited quotes to update" if e["stale_facts"] else "cosmetic")
            e["affected_cases"] = watch.affected_cases(watch.DriftEvent(**{k: e[k] for k in (
                "url", "title", "jurisdiction", "old_id", "new_id", "old_as_of", "new_as_of", "added", "removed", "stale_facts", "summary")})) \
                if e["classification"] != "cosmetic" else []
            base_id = e["new_id"]
    for e in sorted(log, key=lambda e: e["new_as_of"]):
        e["reviewed"] = f"{date.today().isoformat()} (stricter review)"
        print(f"{e['new_as_of']} {e['jurisdiction']} {e['classification']:33s} stale {len(e.get('stale_facts', [])):2d} "
              f"cases {len(e.get('affected_cases', []))} | {(e.get('summary') or {}).get('headline', e.get('review_note', ''))[:80]}")
    watch.LIVE_EVENTS.write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(Counter(e["classification"] for e in log))


if __name__ == "__main__":
    main()
