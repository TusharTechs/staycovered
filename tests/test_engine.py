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


# ---- Montana (published rules, 2026) ----

def test_montana_counts_spouse_income_toward_580():
    ws = worksheet(case([entry("p", "s", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 900)], household=SPOUSE, j="MT",
                        event="application", event_date=date(2026, 10, 5)), date(2026, 10, 5))
    assert ws.params["income_basis"]["value"] == "household"
    assert ws.overall == "meets" and ws.results[0].path == "income"


def test_montana_partial_credit_uses_own_income_when_household_misses():
    # own $290 -> 40 hrs credit at $7.25, + 45 volunteer hours = 85 >= 80
    ws = worksheet(case([
        entry("w", "c", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 290),
        entry("v", "c", Kind.COMMUNITY_SERVICE_HOURS, "2026-09-01", "2026-09-30", 45),
    ], j="MT", event="application", event_date=date(2026, 10, 5)), date(2026, 10, 5))
    r = ws.results[0]
    assert r.status == "meets" and r.path == "combined" and r.income_hours_equivalent == 40.0


def test_montana_renewal_needs_three_qualifying_months():
    two = [entry(f"w{m}", "c", Kind.WORK_HOURS, f"2026-{m:02d}-01", f"2026-{m:02d}-28", 85) for m in (3, 5)]
    three = two + [entry("w8", "c", Kind.WORK_HOURS, "2026-08-01", "2026-08-31", 90)]
    on = date(2026, 10, 20)
    ws2 = worksheet(case(two, j="MT", event_date=on), on)
    ws3 = worksheet(case(three, j="MT", event_date=on), on)
    assert "At least 3 qualifying months" in ws3.review
    assert ws2.overall == "does_not_meet" and ws3.overall == "meets"


def test_montana_less_than_half_time_credits_convert_to_hours():
    # 4 credits x 13 = 52 hours, + 30 volunteer hours = 82
    ws = worksheet(case([
        entry("s", "c", Kind.EDUCATION_CREDIT_HOURS, "2026-08-24", "2026-12-12", 4),
        entry("v", "c", Kind.COMMUNITY_SERVICE_HOURS, "2026-09-01", "2026-09-30", 30),
    ], j="MT", event="application", event_date=date(2026, 10, 2)), date(2026, 10, 2))
    r = ws.results[0]
    assert r.activity_hours == 82.0 and r.status == "meets"


def test_same_household_differs_by_state_in_2026():
    hh_ledger = [entry("p", "s", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 900)]
    on = date(2026, 10, 5)
    ne = worksheet(case(hh_ledger, household=SPOUSE, j="NE", event="application", event_date=on), on)
    mt = worksheet(case(hh_ledger, household=SPOUSE, j="MT", event="application", event_date=on), on)
    assert ne.overall == "conditional" and mt.overall == "meets"


# ---------- paths to stay covered + forecast ----------

from staycovered.engine.forecast import forecast  # noqa: E402
from staycovered.engine.paths import month_paths  # noqa: E402


def test_paths_find_the_exact_gap_and_prove_it():
    c = case([entry("w", "c", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 510),
              entry("h", "c", Kind.WORK_HOURS, "2026-09-01", "2026-09-30", 34),
              entry("v", "c", Kind.COMMUNITY_SERVICE_HOURS, "2026-09-01", "2026-09-30", 18)], j="NE")
    ws = worksheet(c, date(2026, 10, 10))
    assert ws.results[0].status == "does_not_meet"
    by = {p.kind: p for p in month_paths(c, ws.results[0], date(2026, 10, 10))}
    assert "28 more qualifying hours" in by["hours"].title and by["hours"].proven
    assert "$70.00 more income" in by["income"].title and "5 more paid hours at $15.00/hr" in by["income"].title
    assert by["hours"].title.startswith("Proof of")  # a past month can only be settled with evidence


def test_expense_path_uses_the_headroom():
    c = case([entry("g", "c", Kind.SELF_EMPLOYMENT_GROSS, "2026-09-01", "2026-09-30", 800),
              entry("h", "c", Kind.WORK_HOURS, "2026-09-01", "2026-09-30", 20)])
    ws = worksheet(c, date(2026, 10, 10))
    p = next(x for x in month_paths(c, ws.results[0], date(2026, 10, 10)) if x.kind == "expenses")
    assert "$220.00 or less" in p.title and p.proven


def test_forecast_isolates_the_rule_change():
    """Same household every month; only the rules move. Nebraska 2026 'may count' -> federal household MAGI in 2027."""
    c = case([entry("p", "s", Kind.EARNED_INCOME, "2026-09-01", "2026-09-30", 900)], household=SPOUSE, j="NE")
    f = forecast(c, date(2026, 10, 10))
    st = {m.month: m.status for m in f.months}
    assert st["2026-12"] == "conditional" and st["2027-01"] == "meets"
    jan = next(m for m in f.months if m.month == "2027-01")
    assert any(ch.param == "income_basis" for ch in jan.changes)
    assert "starts to qualify clearly in Jan 2027" in f.headline


def test_forecast_without_evidence_says_so():
    f = forecast(case([]), date(2026, 10, 10))
    assert f.pattern_month is None and f.months == []


# ---------- client self-check (anonymous, nothing stored) ----------

from staycovered.selfcheck import SelfCheckIn, run  # noqa: E402


def test_selfcheck_same_month_differs_by_state():
    """34 paid hours ($510) + 18 volunteer hours: short in Nebraska (no income-to-hours), meets in Montana (partial credit)."""
    ne = run(SelfCheckIn(jurisdiction="NE", work_hours=34, wages=510, volunteer_hours=18), date(2026, 10, 10))
    mt = run(SelfCheckIn(jurisdiction="MT", work_hours=34, wages=510, volunteer_hours=18), date(2026, 10, 10))
    assert ne["status"] == "does_not_meet" and mt["status"] == "meets" and mt["path"] == "combined"
    inc = next(p for p in ne["plan"] if p["kind"] == "income")
    assert inc["amount"] == 70 and inc["paid_hours"] == 5 and inc["wage"] == 15
    assert ne["stored"] is False and "632-7633" in ne["agency"]


def test_selfcheck_gig_wage_not_mixed_with_job_hours():
    d = run(SelfCheckIn(jurisdiction="NE", work_hours=20, wages=300, gig_hours=30, gig_payouts=200), date(2026, 10, 10))
    inc = next((p for p in d["plan"] if p["kind"] == "income"), None)
    assert inc is None or inc["wage"] in (None, 15)
