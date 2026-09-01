import datetime

from app.domains.macro.vintage import generate_releases

TODAY = datetime.date(2026, 9, 1)


def test_non_vintage_indicators_return_no_history():
    # repo_rate/gsec_10y/inr_usd/crude_brent/gold are market-quoted, not
    # periodically-revised statistics — see module docstring.
    assert generate_releases("repo_rate", 6.0, TODAY) == []
    assert generate_releases("gsec_10y", 6.5, TODAY) == []


def test_generate_releases_is_deterministic():
    a = generate_releases("cpi_inflation", 4.2, TODAY)
    b = generate_releases("cpi_inflation", 4.2, TODAY)
    assert a == b


def test_generate_releases_never_has_a_future_release_date():
    for release in generate_releases("cpi_inflation", 4.2, TODAY):
        assert release["release_date"] <= TODAY


def test_generate_releases_includes_at_least_one_revision():
    releases = generate_releases("cpi_inflation", 4.2, TODAY)
    revision_numbers = {r["revision_number"] for r in releases}
    assert 0 in revision_numbers
    assert 1 in revision_numbers  # some period old enough to have been revised by today


def test_most_recently_available_reading_is_close_to_current_value():
    # By design, the most recently *released* period lags "today" by the
    # real-world publication delay (e.g. CPI for a given month isn't known
    # until well into the next one) — so the latest available reading
    # won't always be exactly current_value (that only happens once its
    # own revision has actually been published), but it should always be
    # in the same ballpark, not wildly different.
    current_value = 4.2
    releases = generate_releases("cpi_inflation", current_value, TODAY)
    latest = max(releases, key=lambda r: (r["period"], r["revision_number"]))
    assert abs(latest["value"] - current_value) < 1.0


def test_gdp_growth_uses_quarterly_periods():
    releases = generate_releases("gdp_growth", 6.8, TODAY)
    periods = sorted({r["period"] for r in releases})
    # Consecutive quarterly periods should be ~90 days apart.
    for a, b in zip(periods, periods[1:]):
        assert 85 <= (b - a).days <= 95


def test_cpi_inflation_uses_monthly_periods():
    releases = generate_releases("cpi_inflation", 4.2, TODAY)
    periods = sorted({r["period"] for r in releases})
    for a, b in zip(periods, periods[1:]):
        assert 25 <= (b - a).days <= 32
