# Why this problem matters: evidence

These are public sources, accessed October 2026. Figures marked *(reported)* come from press or secondary summaries rather than primary data. All rule text that StayCovered relies on is captured in `sources/` and cited verbatim in `rules/`.

## The requirement

H.R.1 (Public Law 119-21, Sec. 71119) requires Medicaid expansion adults aged 19–64 to show 80 hours a month of work, community service, a work program or education, or monthly income of at least the federal minimum wage × 80 ($580). States must implement the requirement for coverage from **January 1, 2027**.

| Source | Link |
|---|---|
| Statute text | `sources/text/US/fed-statute-sec71119-2025-07-04.txt` |
| CMS interim final rule, 91 FR 33348, published 2026-06-03 | [Federal Register](https://www.federalregister.gov/documents/2026/06/03/2026-11094/medicaid-program-community-engagement-requirement-for-certain-individuals) |
| Plain-language summary | [CHCS: A summary of national Medicaid work requirements](https://www.chcs.org/resource/a-summary-of-national-medicaid-work-requirements/) |

## Nebraska went first, and coverage losses followed

- **Timeline.** Nebraska began checking new applicants on May 1, 2026, and existing members at renewals from July 31 ([DHHS](https://dhhs.ne.gov/Pages/WorkRequirements.aspx); 13 dated versions of that page are in `sources/text/NE/`).
- **Early results.** KFF's early analysis of Nebraska ([KFF](https://www.kff.org/medicaid/early-medicaid-work-requirement-insights-from-nebraska/)) and reporting on the first months ([TechTarget](https://www.techtarget.com/healthcarepayers/news/366651186/Neb-Medicaid-work-requirements-yield-7-coverage-losses), *reported*) describe coverage losses and denials. Most of them were for not providing requested information, not for being found non-compliant.
- **Who lost coverage, and why.** First disenrollments are covered by [Nebraska Public Media](https://nebraskapublicmedia.org/en/news/news-articles/nebraska-becomes-first-state-to-disenroll-medicaid-recipients-under-new-work-requirements/) and [Human Rights Watch](https://www.hrw.org/news/2026/10/01/us-nebraskans-losing-coverage-as-medicaid-changes). Confusion over long notices and call-centre waits is covered by [Medical Daily](https://www.medicaldaily.com/nebraska-medicaid-work-requirements-confusion-lessons-479089) and [PBS NewsHour](https://www.pbs.org/newshour/nation/as-states-face-stricter-medicaid-work-requirements-nebraska-is-an-early-test). These are all *reported*.

## The same failure mode happened before

Arkansas, 2018: most people who lost coverage were unaware of the requirement or failed to *report*, even though many were working ([KFF](https://www.kff.org/medicaid/medicaid-work-requirements-in-arkansas-experience-and-perspectives-of-enrollees/)).

## The rules keep moving

| Change | Date | Source |
|---|---|---|
| Federal rule published | June 3 | `sources/` |
| Federal rule corrected | June 29 | `sources/` |
| CMS medical-frailty guidance | Sept 8 | `sources/` |
| Nebraska: 9 substantive changes to its official page, Dec 2025 to Oct 2026 | various | `sources/changes_NE.md` |
| Nebraska FAQ on whose income counts: changed between versions | 2026 | `sources/changes_NE.md` |

States are implementing amid delayed federal guidance and cost constraints ([KFF survey](https://www.kff.org/medicaid/survey-offers-early-look-at-states-differing-approaches-to-implementing-medicaid-work-requirements-amid-cost-and-time-constraints-and-uncertainty-from-delayed-federal-guidance/); [Georgetown CCF](https://ccf.georgetown.edu/2026/02/11/implementing-costly-medicaid-work-reporting-requirements-who-will-foot-the-bill/)).

## The people doing the work have less support

- Navigators, assisters, health-centre staff and legal aid help clients with this paperwork ([Health Center Association of Nebraska](https://www.hcanebraska.org/advocacy/medicaid-in-nebraska/); [Legal Aid of Nebraska](https://legalaidofnebraska.org/what-we-do/income-and-benefits.html/article/2026/04/23/medicaid-work-requirements-in-nebraska)).
- Federal ACA navigator funding was cut by about 90% ([KFF](https://www.kff.org/quick-take/a-90-cut-to-the-aca-navigator-program/)).

## Why a general chatbot is not enough

WorkReqBench (`bench/`) measures this directly. A frontier model answering from memory is wrong about rules that changed after its training date. A common example: it claims that a spouse's income does not count toward the $580 test. Under the federal rule it is MAGI household income, and Nebraska's FAQ says others' income "may count in some cases".
