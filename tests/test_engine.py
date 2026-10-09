from datetime import date

from staycovered.engine.compute import prev_months, prorate, worksheet
from staycovered.engine.model import Case, Kind, LedgerEntry, Member


def entry(i, member, kind, start, end, amount):
    return LedgerEntry(id=i, member_id=member, kind=kind, period_start=date.fromisoformat(start),
                       period_end=date.fromisoformat(end), amount=amount)


def case(ledger, household=None, j="XX", **kw):
    """j='XX' has no published rules: conservative defaults (own income only, no income-to-hours, 1 month)."""
    household = household or [Member(id="c", name="Client", age=34)]
    return Case(id="t", jurisdiction=j, household=household, client_id="c", ledger=ledger,
                event=kw.pop("event", "renewal"), event_date=kw.pop("event_date", date(2026, 10, 15)), **kw)


SPOUSE = [Member(id="c", name="Client", age=34), Member(id="s", name="Spouse", age=36, applicable_adult=False)]


def test_prev_months_crosses_year():
    assert prev_months(date(2026, 2, 10), 3) == ["2025-11", "2025-12", "2026-01"]


def test_prorate_week_crossing_month():
    e = entry("w", "c", Kind.WORK_HOURS, "2026-08-29", "2026-09-04", 35)
    amt_aug, share_aug = prorate(e, "2026-08")
    amt_sep, _ = prorate(e, "2026-09")
    assert round(share_aug, 4) == round(3 / 7, 4)
    assert round(amt_aug + amt_sep, 6) == 35


def test_meets_on_hours():
    ws = worksheet(case([entry("a", "c", Kind.WORK_HOURS, "2026-09-01", "2026-09-30", 82)]))
    assert ws.months == ["2026-09"] and ws.results[0].status == "meets" and ws.results[0].path == "hours"


def test_meets_on_own_income():
    ws = worksheet(case([entry("w", "c", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 600)]))
    assert ws.results[0].status == "meets" and ws.results[0].path == "income"


def test_spouse_income_ignored_without_household_rule():
    ws = worksheet(case([entry("p", "s", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 1200)], household=SPOUSE))
    assert ws.results[0].status == "insufficient_evidence"


def test_gross_gig_income_is_conditional_on_expenses():
    ws = worksheet(case([
        entry("g", "c", Kind.SELF_EMPLOYMENT_GROSS, "2026-09-01", "2026-09-30", 800),
        entry("h", "c", Kind.WORK_HOURS, "2026-09-01", "2026-09-30", 20),
    ]))
    r = ws.results[0]
    assert r.status == "conditional" and r.path == "income" and r.expense_headroom == 220.0
    assert "expenses" in r.conditions[0]


def test_wages_settle_it_without_gig_income():
    ws = worksheet(case([
        entry("w", "c", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 600),
        entry("g", "c", Kind.SELF_EMPLOYMENT_GROSS, "2026-09-01", "2026-09-30", 100),
    ]))
    assert ws.results[0].status == "meets"


def test_does_not_meet_and_insufficient():
    assert worksheet(case([entry("g", "c", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 300)])).results[0].status == "does_not_meet"
    assert worksheet(case([])).results[0].status == "insufficient_evidence"


def test_seasonal_average():
    ledger = [entry(f"s{m}", "c", Kind.EARNED_INCOME, f"2026-{m:02d}-01", f"2026-{m:02d}-28", 1500) for m in (5, 6, 7)]
    ws = worksheet(case(ledger, household=[Member(id="c", name="Client", age=40, seasonal_worker=True)]))
    r = ws.results[0]
    assert r.status == "meets" and r.path == "seasonal_average" and r.seasonal_average_income == 750.0


def test_notice_months_override():
    ws = worksheet(case([], months_in_question=["2026-08"], event="noncompliance_notice", notice_date=date(2026, 9, 20)))
    assert ws.months == ["2026-08"]
    assert ws.cure_deadline == date(2026, 10, 20)


# ---- Nebraska (published rules, 2026) ----

def test_nebraska_renewal_any_one_month_in_twelve():
    ws = worksheet(case([entry("w", "c", Kind.WORK_HOURS, "2026-03-01", "2026-03-31", 85)], j="NE"), date(2026, 10, 15))
    assert ws.overall == "meets" and "Any one month" in ws.review
    assert ws.params["renewal_window_months"]["verified"]


def test_nebraska_2026_spouse_income_is_conditional():
    ws = worksheet(case([entry("p", "s", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 1200)], household=SPOUSE, j="NE"),
                   date(2026, 10, 15))
    r = ws.results[0]
    assert r.status == "conditional" and any("household" in c for c in r.conditions)


def test_federal_2027_household_magi_counts_spouse():
    c = case([entry("p", "s", Kind.EARNED_INCOME, "2027-01-01", "2027-01-31", 1200)], household=SPOUSE, j="NE",
             event_date=date(2027, 2, 15))
    ws = worksheet(c, date(2027, 2, 15))
    assert ws.params["income_basis"]["value"] == "household"
    assert ws.overall == "meets"


def test_nebraska_exemption_flag_cites_state_fact():
    hh = [Member(id="c", name="Client", age=29, caretaker_of_young_child=True)]
    ws = worksheet(case([], household=hh, j="NE"), date(2026, 10, 15))
    assert ws.exemptions[0].fact_ids == ["NE.exemption.parent_caretaker.v2"]
