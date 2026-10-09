"""Seed the synthetic demo caseload. All people, employers and platforms are fictional.

Each document carries gold-standard rows (what a careful human would extract). Seeding uses the gold rows so the
demo works without API keys; tests/eval compare Nemotron extraction against the same gold rows.

Run: uv run python -m demo.seed
"""

from __future__ import annotations

from datetime import date

from staycovered import store
from staycovered.engine.model import Case, Kind, LedgerEntry, Member, SourceRef

D = date.fromisoformat


def doc(did: str, name: str, kind: str, member: str, text: str, gold: list[tuple]) -> tuple[store.Document, list[LedgerEntry]]:
    entries = []
    for i, (k, start, end, amount, payer, span) in enumerate(gold, 1):
        assert span in text, f"gold span not in {did}: {span!r}"
        entries.append(LedgerEntry(id=f"{did}-r{i}", member_id=member, kind=k, period_start=D(start), period_end=D(end),
                                   amount=amount, payer=payer, source=SourceRef(doc_id=did, span=span)))
    d = store.Document(id=did, name=name, kind=kind, member_id=member, text=text,
                       extracted={"gold": [dict(kind=k.value, period_start=s, period_end=e, amount=a, payer=p, span=sp) for k, s, e, a, p, sp in gold]})
    return d, entries


NOTICE_MARIA = """NEBRASKA DEPARTMENT OF HEALTH AND HUMAN SERVICES — SAMPLE (SYNTHETIC DEMO)
Notice date: September 20, 2026
Case number: DEMO-40417
MARIA LOPEZ

Medicaid Work Requirements: We need more information
Our records do not show that you met the work requirement for August 2026.
You must work, volunteer, go to school, or be in a work program for at least 80 hours a month,
or have monthly income of at least $580.

What you need to do: Send proof of your hours or income for August 2026, or tell us why you should be exempt.
You have 30 days from the date of this notice to respond. If we do not hear from you, your Medicaid may end.
How to respond: Upload documents at iServe Nebraska, mail them to the address below, or call 1-855-632-7633.
"""

MARIA_GIG_A = """DashBite Driver — Weekly Earnings Summary (SYNTHETIC)
Driver: Maria Lopez
Week of Jul 27, 2026 – Aug 2, 2026
Total payout: $164.20   Active time: 13 hr 10 min   Deliveries: 21
Week of Aug 3, 2026 – Aug 9, 2026
Total payout: $201.55   Active time: 16 hr 5 min   Deliveries: 26
Week of Aug 10, 2026 – Aug 16, 2026
Total payout: $142.10   Active time: 11 hr 40 min   Deliveries: 18
Week of Aug 17, 2026 – Aug 23, 2026
Total payout: $188.00   Active time: 15 hr 0 min   Deliveries: 24
Week of Aug 24, 2026 – Aug 30, 2026
Total payout: $97.35   Active time: 8 hr 20 min   Deliveries: 12
Payouts are before expenses such as fuel and vehicle costs.
"""

MARIA_GIG_B = """CartHop Shopper — Monthly Statement (SYNTHETIC)
Shopper: M. Lopez
Statement period: August 1, 2026 – August 31, 2026
Batches completed: 9
Earnings (before tips): $96.40
Customer tips: $41.00
Total earnings: $137.40
Hours on batches: 10.5
"""

JAMES_STUB = """PRAIRIE ROOF & SIDING LLC — EARNINGS STATEMENT (SYNTHETIC)
Employee: James Carter
Seasonal crew — season ended Aug 15, 2026
Pay period: 05/01/2026 - 05/31/2026   Hours: 172.0   Gross pay: $3,612.00
Pay period: 06/01/2026 - 06/30/2026   Hours: 181.5   Gross pay: $3,811.50
Pay period: 07/01/2026 - 07/31/2026   Hours: 176.0   Gross pay: $3,696.00
Pay period: 08/01/2026 - 08/15/2026   Hours: 81.0    Gross pay: $1,701.00
"""

AISHA_STUB = """Corner Grocers — Pay Stub (SYNTHETIC)
Employee: Aisha Mohammed
Pay period: 09/01/2026 - 09/30/2026
Regular hours: 52.00   Rate: $13.50   Gross: $702.00
"""

AISHA_VOL = """Lincoln Community Food Pantry (SYNTHETIC)
To whom it may concern,
Aisha Mohammed volunteered with our pantry in September 2026 for a total of 20 hours (sorting and distribution).
Signed, Volunteer Coordinator
"""

BECKER_STUB = """Heartland Medical Billing — Pay Statement (SYNTHETIC)
Employee: Linda Becker
Pay period: September 1, 2026 to September 30, 2026
Gross earnings: $2,104.00
"""

KAYLA_SCHOOL = """Metro Community College — Enrollment Verification (SYNTHETIC)
Student: Kayla Brooks
Fall 2026 term (Aug 24, 2026 – Dec 12, 2026): enrolled 6 credit hours (half-time).
"""

KAYLA_NOTE = """Client statement taken by navigator (SYNTHETIC)
Kayla lives with her daughter, age 3, and is her only caregiver.
"""


def build() -> list[store.CaseRecord]:
    recs = []

    # 1. Maria — two gig apps, weekly periods crossing months, gross payouts; noncompliance notice for August.
    n, _ = doc("maria-notice", "State notice (Sep 20)", "notice", "maria", NOTICE_MARIA, [])
    a, ea = doc("maria-dashbite", "DashBite weekly earnings", "income", "maria", MARIA_GIG_A, [
        (Kind.SELF_EMPLOYMENT_GROSS, "2026-07-27", "2026-08-02", 164.20, "DashBite", "Total payout: $164.20"),
        (Kind.WORK_HOURS, "2026-07-27", "2026-08-02", 13.17, "DashBite", "Active time: 13 hr 10 min"),
        (Kind.SELF_EMPLOYMENT_GROSS, "2026-08-03", "2026-08-09", 201.55, "DashBite", "Total payout: $201.55"),
        (Kind.WORK_HOURS, "2026-08-03", "2026-08-09", 16.08, "DashBite", "Active time: 16 hr 5 min"),
        (Kind.SELF_EMPLOYMENT_GROSS, "2026-08-10", "2026-08-16", 142.10, "DashBite", "Total payout: $142.10"),
        (Kind.WORK_HOURS, "2026-08-10", "2026-08-16", 11.67, "DashBite", "Active time: 11 hr 40 min"),
        (Kind.SELF_EMPLOYMENT_GROSS, "2026-08-17", "2026-08-23", 188.00, "DashBite", "Total payout: $188.00"),
        (Kind.WORK_HOURS, "2026-08-17", "2026-08-23", 15.0, "DashBite", "Active time: 15 hr 0 min"),
        (Kind.SELF_EMPLOYMENT_GROSS, "2026-08-24", "2026-08-30", 97.35, "DashBite", "Total payout: $97.35"),
        (Kind.WORK_HOURS, "2026-08-24", "2026-08-30", 8.33, "DashBite", "Active time: 8 hr 20 min"),
    ])
    b, eb = doc("maria-carthop", "CartHop monthly statement", "income", "maria", MARIA_GIG_B, [
        (Kind.SELF_EMPLOYMENT_GROSS, "2026-08-01", "2026-08-31", 137.40, "CartHop", "Total earnings: $137.40"),
        (Kind.WORK_HOURS, "2026-08-01", "2026-08-31", 10.5, "CartHop", "Hours on batches: 10.5"),
    ])
    case = Case(id="maria-lopez", jurisdiction="NE", client_id="maria",
                household=[Member(id="maria", name="Maria Lopez", age=34)],
                ledger=ea + eb, event="noncompliance_notice", event_date=D("2026-09-01"), notice_date=D("2026-09-20"))
    recs.append(store.CaseRecord(case=case, client_name="Maria Lopez", language="es", documents=[n, a, b],
                                 notice={"notice_type": "noncompliance", "notice_date": "2026-09-20", "respond_by": None,
                                         "months_in_question": ["2026-08"],
                                         "requested_items": ["Proof of hours or income for August 2026, or a reason you should be exempt"],
                                         "how_to_respond": ["Upload at iServe Nebraska", "Mail to DHHS", "Call 1-855-632-7633"]}))

    # 2. James — seasonal worker, no September income; six-month average.
    s, es = doc("james-stub", "Prairie Roof earnings statement", "income", "james", JAMES_STUB, [
        (Kind.EARNED_INCOME, "2026-05-01", "2026-05-31", 3612.00, "Prairie Roof & Siding", "Pay period: 05/01/2026 - 05/31/2026   Hours: 172.0   Gross pay: $3,612.00"),
        (Kind.EARNED_INCOME, "2026-06-01", "2026-06-30", 3811.50, "Prairie Roof & Siding", "Pay period: 06/01/2026 - 06/30/2026   Hours: 181.5   Gross pay: $3,811.50"),
        (Kind.EARNED_INCOME, "2026-07-01", "2026-07-31", 3696.00, "Prairie Roof & Siding", "Pay period: 07/01/2026 - 07/31/2026   Hours: 176.0   Gross pay: $3,696.00"),
        (Kind.EARNED_INCOME, "2026-08-01", "2026-08-15", 1701.00, "Prairie Roof & Siding", "Pay period: 08/01/2026 - 08/15/2026   Hours: 81.0    Gross pay: $1,701.00"),
    ])
    recs.append(store.CaseRecord(
        case=Case(id="james-carter", jurisdiction="NE", client_id="james",
                  household=[Member(id="james", name="James Carter", age=41, seasonal_worker=True)],
                  ledger=es, event="renewal", event_date=D("2026-10-05")),
        client_name="James Carter", documents=[s]))

    # 3. Aisha — 52 work hours + 20 volunteer hours = 72; short by 8 unless income converts.
    p, ep = doc("aisha-stub", "Corner Grocers pay stub", "income", "aisha", AISHA_STUB, [
        (Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 702.00, "Corner Grocers", "Gross: $702.00"),
        (Kind.WORK_HOURS, "2026-09-01", "2026-09-30", 52.0, "Corner Grocers", "Regular hours: 52.00"),
    ])
    v, ev = doc("aisha-pantry", "Food pantry volunteer letter", "income", "aisha", AISHA_VOL, [
        (Kind.COMMUNITY_SERVICE_HOURS, "2026-09-01", "2026-09-30", 20.0, "Lincoln Community Food Pantry", "for a total of 20 hours"),
    ])
    recs.append(store.CaseRecord(
        case=Case(id="aisha-mohammed", jurisdiction="NE", client_id="aisha",
                  household=[Member(id="aisha", name="Aisha Mohammed", age=29)],
                  ledger=ep + ev, event="noncompliance_notice", event_date=D("2026-10-01"), notice_date=D("2026-10-02")),
        client_name="Aisha Mohammed", documents=[p, v]))

    # 4. Tom Becker — no own income; spouse's earnings count as household MAGI income.
    bs, eb2 = doc("becker-stub", "Linda's pay statement", "income", "linda", BECKER_STUB, [
        (Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 2104.00, "Heartland Medical Billing", "Gross earnings: $2,104.00"),
    ])
    recs.append(store.CaseRecord(
        case=Case(id="tom-becker", jurisdiction="NE", client_id="tom",
                  household=[Member(id="tom", name="Tom Becker", age=58), Member(id="linda", name="Linda Becker", age=55, applicable_adult=False)],
                  ledger=eb2, event="renewal", event_date=D("2026-10-12")),
        client_name="Tom Becker", documents=[bs]))

    # 5. Kayla — half-time student and sole caregiver of a 3-year-old: possible exemption.
    k1, _ = doc("kayla-school", "College enrollment verification", "activity", "kayla", KAYLA_SCHOOL, [])
    k2, _ = doc("kayla-note", "Navigator intake note", "other", "kayla", KAYLA_NOTE, [])
    recs.append(store.CaseRecord(
        case=Case(id="kayla-brooks", jurisdiction="NE", client_id="kayla",
                  household=[Member(id="kayla", name="Kayla Brooks", age=24, caretaker_of_young_child=True)],
                  ledger=[], event="noncompliance_notice", event_date=D("2026-10-01"), notice_date=D("2026-09-28")),
        client_name="Kayla Brooks", documents=[k1, k2]))

    # 6. Robert — no documents yet; possible medical frailty.
    recs.append(store.CaseRecord(
        case=Case(id="robert-nguyen", jurisdiction="NE", client_id="robert",
                  household=[Member(id="robert", name="Robert Nguyen", age=47, medically_frail_indicators=["type 2 diabetes with neuropathy", "recent hospitalization"])],
                  ledger=[], event="noncompliance_notice", event_date=D("2026-10-01"), notice_date=D("2026-10-06")),
        client_name="Robert Nguyen", documents=[]))
    return recs


def main() -> None:
    for p in store.CASES.glob("*.json"):
        p.unlink()
    for r in build():
        store.save(r)
    print(f"seeded {len(store.all_cases())} synthetic cases")


if __name__ == "__main__":
    main()
