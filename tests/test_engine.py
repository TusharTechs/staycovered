from datetime import date

from staycovered.engine.compute import prev_months, prorate, worksheet
from staycovered.engine.model import Case, Kind, LedgerEntry, Member


def entry(i, member, kind, start, end, amount):
    return LedgerEntry(id=i, member_id=member, kind=kind, period_start=date.fromisoformat(start),
                       period_end=date.fromisoformat(end), amount=amount)


def case(ledger, household=None, **kw):
    household = household or [Member(id="c", name="Client", age=34)]
    return Case(id="t", household=household, client_id="c", ledger=ledger,
                event=kw.pop("event", "renewal"), event_date=kw.pop("event_date", date(2026, 10, 15)), **kw)


def test_prev_months_crosses_year():
    assert prev_months(date(2026, 2, 10), 3) == ["2025-11", "2025-12", "2026-01"]


def test_prorate_week_crossing_month():
    e = entry("w", "c", Kind.WORK_HOURS, "2026-08-29", "2026-09-04", 35)  # 7 days, 3 in Aug
    amt_aug, share_aug = prorate(e, "2026-08")
    amt_sep, _ = prorate(e, "2026-09")
    assert round(share_aug, 4) == round(3 / 7, 4)
    assert round(amt_aug + amt_sep, 6) == 35


def test_meets_on_hours():
    ws = worksheet(case([entry("a", "c", Kind.WORK_HOURS, "2026-09-01", "2026-09-30", 82)]))
    r = ws.results[0]
    assert ws.months == ["2026-09"]
    assert r.status == "meets" and r.path == "hours"


def test_meets_on_household_income_from_spouse():
    hh = [Member(id="c", name="Client", age=34), Member(id="s", name="Spouse", age=36, applicable_adult=False)]
    ws = worksheet(case([entry("p", "s", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 1200)], household=hh))
    r = ws.results[0]
    assert r.status == "meets" and r.path == "household_income"
    assert r.income_threshold == 580.0


def test_combined_hours_and_income_proxy():
    # $380 income -> 52.41 hours at $7.25, plus 30 volunteer hours -> 82.41 >= 80
    ws = worksheet(case([
        entry("i", "c", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 380),
        entry("v", "c", Kind.COMMUNITY_SERVICE_HOURS, "2026-09-01", "2026-09-30", 30),
    ]))
    r = ws.results[0]
    assert r.status == "meets" and r.path == "combined"
    assert r.income_hours_equivalent == 52.41


def test_does_not_meet_and_gross_gig_flagged():
    ws = worksheet(case([entry("g", "c", Kind.SELF_EMPLOYMENT_GROSS, "2026-09-01", "2026-09-30", 300)]))
    r = ws.results[0]
    assert r.status == "does_not_meet"
    assert any("gross" in a for a in r.ambiguities)


def test_insufficient_evidence_when_no_rows():
    ws = worksheet(case([]))
    assert ws.results[0].status == "insufficient_evidence"


def test_seasonal_average():
    # Seasonal worker: big summer income, nothing in September; 6-month average >= 580 -> meets
    ledger = [entry(f"s{m}", "c", Kind.EARNED_INCOME, f"2026-{m:02d}-01", f"2026-{m:02d}-28", 1500) for m in (5, 6, 7)]
    hh = [Member(id="c", name="Client", age=40, seasonal_worker=True)]
    ws = worksheet(case(ledger, household=hh))
    r = ws.results[0]
    assert r.month == "2026-09"
    assert r.status == "meets" and r.path == "seasonal_average"
    assert r.seasonal_average_income == 750.0


def test_cure_deadline_and_exemption_flag():
    hh = [Member(id="c", name="Client", age=29, pregnant_or_postpartum=True)]
    ws = worksheet(case([], household=hh, event="noncompliance_notice", notice_date=date(2026, 9, 20)))
    assert ws.cure_deadline == date(2026, 10, 20)
    assert ws.exemptions and ws.exemptions[0].key == "pregnant_postpartum"
    assert "confirm" in ws.exemptions[0].action.lower()


def test_application_lookback_uses_param():
    ws = worksheet(case([], event="application", event_date=date(2026, 10, 3)))
    assert ws.months == ["2026-09"]  # default 1 month until a fact overrides it
