import pytest

from app.domains.fundamentals import analytics as fa

# A clean, hand-verifiable fixture — not real company data, chosen so every
# ratio comes out to a number that's easy to check by hand rather than just
# trusted from the code.
REVENUE = 1000.0
GROSS_PROFIT = 600.0
EBITDA = 400.0
EBIT = 300.0
PBT = 250.0
PAT = 200.0
EPS = 20.0
TOTAL_ASSETS = 2000.0
TOTAL_LIABILITIES = 800.0
TOTAL_EQUITY = 1200.0
CASH = 100.0
TOTAL_DEBT = 500.0
CURRENT_ASSETS = 600.0
CURRENT_LIABILITIES = 300.0
INTEREST_EXPENSE = 50.0
FREE_CASH_FLOW = 150.0
SHARES_OUTSTANDING = 10.0
PRICE = 100.0


def test_roe():
    assert fa.roe_pct(PAT, TOTAL_EQUITY) == pytest.approx(16.667, abs=0.001)


def test_roce():
    # capital employed = 2000 - 300 = 1700; 300/1700 = 17.647%
    assert fa.roce_pct(EBIT, TOTAL_ASSETS, CURRENT_LIABILITIES) == pytest.approx(17.647, abs=0.001)


def test_roa():
    assert fa.roa_pct(PAT, TOTAL_ASSETS) == pytest.approx(10.0, abs=1e-6)


def test_debt_to_equity():
    assert fa.debt_to_equity(TOTAL_DEBT, TOTAL_EQUITY) == pytest.approx(0.4167, abs=0.001)


def test_interest_coverage():
    assert fa.interest_coverage(EBIT, INTEREST_EXPENSE) == pytest.approx(6.0, abs=1e-6)


def test_current_ratio():
    assert fa.current_ratio(CURRENT_ASSETS, CURRENT_LIABILITIES) == pytest.approx(2.0, abs=1e-6)


def test_asset_turnover():
    assert fa.asset_turnover(REVENUE, TOTAL_ASSETS) == pytest.approx(0.5, abs=1e-6)


def test_market_cap():
    assert fa.market_cap(PRICE, SHARES_OUTSTANDING) == pytest.approx(1000.0, abs=1e-6)


def test_market_cap_none_without_shares_outstanding():
    assert fa.market_cap(PRICE, None) is None


def test_pe_ratio():
    assert fa.pe_ratio(PRICE, EPS) == pytest.approx(5.0, abs=1e-6)


def test_pb_ratio():
    # book value per share = 1200/10 = 120; 100/120 = 0.8333
    assert fa.pb_ratio(PRICE, TOTAL_EQUITY, SHARES_OUTSTANDING) == pytest.approx(0.8333, abs=0.001)


def test_enterprise_value_and_ev_multiples():
    mcap = fa.market_cap(PRICE, SHARES_OUTSTANDING)
    ev = fa.enterprise_value(mcap, TOTAL_DEBT, CASH)
    assert ev == pytest.approx(1400.0, abs=1e-6)  # 1000 + 500 - 100
    assert fa.ev_to_ebitda(ev, EBITDA) == pytest.approx(3.5, abs=1e-6)
    assert fa.ev_to_sales(ev, REVENUE) == pytest.approx(1.4, abs=1e-6)


def test_fcf_yield():
    mcap = fa.market_cap(PRICE, SHARES_OUTSTANDING)
    assert fa.fcf_yield_pct(FREE_CASH_FLOW, mcap) == pytest.approx(15.0, abs=1e-6)


def test_ratios_guard_against_division_by_zero():
    assert fa.roe_pct(PAT, 0) is None
    assert fa.roce_pct(EBIT, 300, 300) is None  # capital employed == 0
    assert fa.roa_pct(PAT, 0) is None
    assert fa.debt_to_equity(TOTAL_DEBT, 0) is None
    assert fa.interest_coverage(EBIT, 0) is None
    assert fa.current_ratio(CURRENT_ASSETS, 0) is None
    assert fa.asset_turnover(REVENUE, 0) is None
    assert fa.pe_ratio(PRICE, 0) is None
    assert fa.pb_ratio(PRICE, TOTAL_EQUITY, 0) is None
    assert fa.ev_to_ebitda(1000.0, 0) is None
    assert fa.ev_to_sales(1000.0, 0) is None
    assert fa.fcf_yield_pct(FREE_CASH_FLOW, 0) is None
