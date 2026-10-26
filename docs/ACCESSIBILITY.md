# Accessibility check

**Result:** 0 axe-core violations on every view checked, run on 2026-10-26 against the current build.

- Tool: axe-core 4.10.2, rule tags `wcag2a`, `wcag2aa`, `wcag21aa`, `wcag22aa` and `best-practice`.
- How: each view loaded in Chromium at desktop width with the local dev server; `axe.run(document)` after the page settled.

| View | Violations |
|---|---|
| Home `/` | 0 |
| Caseload `/caseload` | 0 |
| Case: Maria (with "What to do now", paths, forecast) | 0 |
| Case: Maria, notice in Spanish | 0 |
| Case: Maria, agent run finished (all 10 steps and the receipt) | 0 |
| Case: Dani, Tom, Rosa | 0 each |
| Self-check `/check`, and its Spanish result | 0 each |
| Policy sandbox, default and with two switches on | 0 each |
| Rule Time Machine, default, Oct 26, and with an answer and evidence check | 0 each |
| WorkReqBench `/bench` | 0 |
| Under the hood `/under-the-hood` | 0 |

Also built in, and checked by hand: keyboard operation with a visible focus outline; live regions that announce answers and agent steps; reduced-motion support; layouts that work at 375 px phone width without sideways scrolling.

Automated checks don't find everything (for example, how clear the plain-language text is to a real reader), and no screen-reader user has tested the app yet.
