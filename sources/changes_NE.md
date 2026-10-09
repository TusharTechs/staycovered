# Nebraska DHHS work-requirement guidance: changes detected between captured sources

Method: Wayback Machine captures of https://dhhs.ne.gov/Pages/WorkRequirements.aspx (CDX: about 90 captures 2025-12-17 to 2026-10-05, text changes visible at the dates below) and of the FAQ/PDF documents, compared by text diff. The live site (dhhs.ne.gov) did not respond to automated requests from the collection environment on 2026-10-09 (timeouts), so the latest evidence is the 2026-10-05 capture. Source ids refer to `sources/manifest.json`; each quoted string appears verbatim in the cited source's text file (checked by script). "Window" = interval between the last capture without the change and the first capture with it. Items marked MINOR are wording-only.

## A. Web page `WorkRequirements.aspx`

### A1. 2025-12-17 -> 2026-03-03: Spanish documents added (MINOR; no rule change)
- Window: 2025-12-17 to 2026-03-03.
- Before (ne-dhhs-wr-page-2025-12-17): "Nebraska Medicaid Work Requirements Outreach Notice / Spanish translation coming soon."
- After (ne-dhhs-wr-page-2026-03-03): "Nebraska Medicaid Work Requirements Outreach Notice / Spanish"
- Footer address ZIP changed 68509 to 68508 (cosmetic).

### A2. 2026-03-03 -> 2026-04-14: Rewrite - renewal-based schedule for existing members, new income figures, new exemption wording, hardship process
- Window: 2026-03-03 to 2026-04-14 (04-14 capture is 00:57 UTC; a 03-11 capture exists but was not retrieved).
- Existing members. Before (ne-dhhs-wr-page-2026-03-03): "This includes people with Medicaid coverage under Medicaid expansion on this date or people who apply on or after this date."  After (ne-dhhs-wr-page-2026-04-14): "DHHS will begin checking work requirements for members whose annual eligibility periods end on or after July 31, 2026."
- Applicants. After (ne-dhhs-wr-page-2026-04-14): "Individuals applying for Medicaid on or after May 1, 2026, must meet work requirements in the month before they apply."
- Income limit. Before (ne-dhhs-wr-page-2026-03-03): "about $21,610 per year for a single person, or $44,380 for a family of four"  After (ne-dhhs-wr-page-2026-04-14): "about $22,025 per year for one person or $45,540 for a family of four"
- Tribal exemption. Before (ne-dhhs-wr-page-2026-03-03): "People who are members of recognized Native American tribes"  After (ne-dhhs-wr-page-2026-04-14): "A member of a federally recognized Native American tribe, an Urban Indian, a California Indian, or if you receive services through the Indian Health Service (IHS)"
- Caregiver exemption. Before (ne-dhhs-wr-page-2026-03-03): "Parents, caretakers or guardians of children up to age 13 or of an individual with disabilities"  After (ne-dhhs-wr-page-2026-04-14): "Caring for a person with a disability"
- Temporary hardship process. Before (ne-dhhs-wr-page-2026-03-03): "Members and applicants who have one of these temporary hardship reasons may need to make a request to DHHS in person, online, by phone, or through the mail."  After (ne-dhhs-wr-page-2026-04-14): "Members cannot complete a declaration form for living in a county under a federal emergency or with high unemployment."
- Hardship look-back removed. Before (ne-dhhs-wr-page-2026-03-03): "People who were hospitalized or lived in a nursing home since their last coverage renewal."  After (ne-dhhs-wr-page-2026-04-14): "They were hospitalized or in a nursing facility."
- $580 wording. Before (ne-dhhs-wr-page-2026-03-03): "As of December 2025, this is about $580 per month."  After (ne-dhhs-wr-page-2026-04-14): "This is currently about $580 per month."

### A3. 2026-04-14 -> 2026-04-15: frailty wording corrected (MINOR but substantive for screening)
- Window: 2026-04-14 00:57 to 2026-04-15 18:23 UTC (FAQ capture 04-15; the 04-15 page capture text differs only here).
- Before (ne-dhhs-wr-page-2026-04-14): "A serious and complex medical condition"
- After (ne-dhhs-wr-page-2026-10-05): "You have a serious or complex medical condition"

### A4. 2026-04-15 -> 2026-04-29: page restructured into plain-language Q&A; deferral of May/June 2026 renewals; review periods; response channels; forms section
- Window: 2026-04-15 to 2026-04-29 (04-22 capture returned errors). First restructured capture: 2026-04-29 (first stored copy is the 2026-05-13 capture, text identical on these points).
- Deferral. After (ne-dhhs-wr-page-2026-05-13): "Members with renewal dates in May or June 2026 will not have to show they've met work requirements until their renewal in 2027."  Before: no such sentence (ne-dhhs-wr-page-2026-04-14).
- Applicant review periods. Before (ne-dhhs-wr-page-2026-04-14): "Individuals applying for Medicaid on or after May 1, 2026, must meet work requirements in the month before they apply."  After (ne-dhhs-wr-page-2026-05-13): "If you qualify for an exemption the work requirement review period is the calendar month you apply or the calendar month before you apply."
- Existing members. After (ne-dhhs-wr-page-2026-05-13): "If you're already on Medicaid, the work requirement review period is 12 months."
- Seasonal workers (new on page; FAQ v1 already had it). After (ne-dhhs-wr-page-2026-05-13): "You can also meet work requirements if your average monthly income from working over the last six months from seasonal work is at least $580, regardless of the number of hours worked."
- Forms. After (ne-dhhs-wr-page-2026-05-13): "Optional Screening Questions / Spanish (Sample Form)"; Verification of Compliance Notice and Declaration Form now linked; Medically Frail and SUD Treatment Exemption Information section added.

### A5. 2026-06-03 -> 2026-07-22: Dawson County high-unemployment hardship banner
- Window: 2026-07-17 (absent) to 2026-07-22 (present).
- Before: banner absent (ne-dhhs-wr-page-2026-07-17).
- After (ne-dhhs-wr-page-2026-07-22): "If you lived in Dawson County during any qualifying month since February 2026, DHHS will automatically and temporarily exempt you from completing work requirement activities."
- Page text between 2026-05-13 and 2026-07-17 is otherwise unchanged (the 2026-06-03 capture is the one nearest the 2026-06-01 timeline date; the 2026-08-01 capture, nearest 2026-07-31, equals the 07-22 text).

### A6. 2026-09-08 -> 2026-09-12: fourteen-county hardship exemptions and medical vs county-based hardship rewrite
- Window: 2026-09-10 21:49 UTC (absent) to 2026-09-12 08:44 UTC (present).
- Before (ne-dhhs-wr-page-2026-09-08): "Attention Dawson County Residents Eligible Under Medicaid Expansion:"
- After (ne-dhhs-wr-page-2026-09-15): "Attention: Temporary Hardship Exemptions in Effect for 14 Counties"
- Hardship process. Before (ne-dhhs-wr-page-2026-09-08): "If you were in the hospital, staying at a nursing facility, or traveling to get medical care, you will have to fill out a declaration form and sent it to DHHS."  After (ne-dhhs-wr-page-2026-09-15): "Medical Hardships – You must submit a declaration to DHHS (online, by phone, by mail, or in person) if:"
- County rules (new table). After (ne-dhhs-wr-page-2026-09-15): "Lasts Until: April 30, 2026" (wildfire counties) and "Existing Members – This exemption applies to you if you lived in one of these counties during May 2026 and you have a Medicaid renewal through July 2026 and April 2027." (severe weather counties).
- Reprocessing promise (new). After (ne-dhhs-wr-page-2026-09-15): "DHHS will reprocess your application or renewal. You do not need to take any action."

### A7. 2026-09-13 -> 2026-09-15: frailty/SUD process link labelled "Updated September 14, 2026"
- Window: 2026-09-13 21:14 UTC (no label) to 2026-09-15 23:57 UTC (label present).
- Before (ne-dhhs-wr-page-2026-09-12): "Medically Frail and SUD Treatment Program Exemptions Process"
- After (ne-dhhs-wr-page-2026-09-15): "Medically Frail and SUD Treatment Program Exemptions Process (Updated September 14, 2026)"
- Open: the updated PDF at the same URL is not in the Wayback Machine (latest capture 2026-09-11 is the May 1, 2026 text); what changed is UNKNOWN. A Community Partner Meeting of September 15, 2026 was added to the page's video list in the 2026-10-05 capture ("Community Partner Meeting September 15, 2026").

### A8. Cosmetic additions (MINOR)
- 2026-08-01 -> 2026-09-08: Spanish video links added ("Click here for the Spanish video.").

## B. FAQ PDF (MLTC-WR-Requirements-FAQ.pdf)

Captures: 2025-12-30 (v1.0, published Dec 22, 2025; identical text to the 2026-03-11 capture), 2026-04-15 (published April 14, 2026), 2026-05-12 through 2026-08-08 (published April 29, 2026, identical text). A 2025-12-17 capture used "short-term hardship" instead of "temporary hardship" (draft).

### B1. What kind of income counts toward $580
- Before (ne-faq-2026-04-15): "Nebraska Medicaid is working with the federal government to confirm guidance on income. This question will be updated once guidance is received."
- After (ne-faq-2026-05-12): "Income you earn from a job counts, as well as income you may receive from other sources such as other benefits."  Reference added: "see state regulations in 477 NAC 16".
- Window: 2026-04-15 to 2026-05-12.

### B2. Income from dependents
- Before (ne-faq-2026-04-15): "No. Meeting Medicaid work requirements will be determined on an individual basis for each applicant or current member based on Medicaid income rules."
- After (ne-faq-2026-05-12): "It may count in some cases. For more information, see state regulations in 477 NAC 16."

### B3. Half-time enrollment
- Before (ne-faq-2026-04-15): "Nebraska Medicaid is working with the federal government to confirm the number of hours needed for “halftime” enrollment."
- After (ne-faq-2026-05-12): "Half-time means enrollment in at least half of the program’s full-time status."

### B4. Premium tax credits after non-compliance
- v1.0 (ne-faq-2025-12-30): "During this time, this individual will not be eligible for advanced premium tax credits on the federal marketplace."
- April 14 (ne-faq-2026-04-15): "If you are not meeting Medicaid work requirements, you will not qualify for advanced premium tax credits."
- April 29 (ne-faq-2026-05-12): "If you are not meeting Medicaid work requirements you may still qualify for coverage through the marketplace, but you might not qualify for financial assistance."

### B5. Medically frail documentation
- Before (ne-faq-2026-04-15): "Medicaid may ask for documentation."
- After (ne-faq-2026-05-12): "If you’re applying for the first time, you can use the declaration form to tell DHHS about your health condition. You will not need to send in medical records."

### B6. Notice-then-closure sequence
- v1.0 (ne-faq-2025-12-30) had no second-notice statement; April 14 (ne-faq-2026-04-15): "Medicaid will send another notice prior to closing your coverage."
- After (ne-faq-2026-05-12): "Medicaid will send another notice prior to denying or closing your coverage."

### B7. How to report work, school, volunteer hours
- Before (ne-faq-2026-04-15): "You must complete a declaration form to report volunteer hours."
- After (ne-faq-2026-05-12): "To report volunteer hours, you must complete the individual declaration form (IDF)."

### B8. Self-employed and "how do I show DHHS I'm working" (new in the April 29 version)
- After (ne-faq-2026-05-12): "Or, you can work 80 hours in a qualifying month as self-employed even if your business operates at a loss during a qualifying calendar month."

## C. Documents with no detected change
- Verification of Compliance Notice sample (ENG): identical bytes in captures 2026-04-29 and 2026-07-22.
- Individual Declaration Form MLTC-118 (5/2026): identical bytes in captures 2026-05-29, 06-02, 06-15, 07-15 (fillable AcroForm, 103 fields; see `sources/raw/NE/mltc118_fields.json`).
- Outreach notice (dated December 2025): identical bytes 2025-12-18 to 2026-05-12.
- Medically Frail and SUD Conditions code index (295 pages): identical digest 2026-04-30 to 2026-09-09.
- Medically Frail and SUD Treatment Program Exemptions PDF (heading "May 1, 2026"): identical bytes 2026-05-12 to 2026-09-11. The September 14, 2026 update is not captured.
- One-pager: identical digest 2026-05-09 and 2026-05-12 (states guidance as of April 6, 2026).

## D. Press releases
- ne-pr-community-partners-2026-04-13 and ne-pr-take-effect-2026-04-30 are single-version documents; the second states the renewal-based schedule that appears on the web page from 2026-04-14.
