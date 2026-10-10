"""Scheduled drift-watch: `uv run python -m staycovered.drift` (used by .github/workflows/drift-watch.yml)."""

from __future__ import annotations

from .watch import check_live, live_status


def main() -> None:
    events = check_live(summarise=True)
    st = live_status()
    print(f"checked {len(st.get('pages', []))} official pages at {st.get('last_checked')}; {len(events)} change(s)")
    for p in st.get("pages", []):
        print(f"  {p['status']:11s} {p['jurisdiction']}  {p['title']}")
    for e in events:
        print(f"  CHANGE: {e.title}: {(e.summary or {}).get('headline', '')}")


if __name__ == "__main__":
    main()
