"""Macro vintage/revision generation (Tier 1 §17) — deterministic, seeded,
and deliberately scoped to only the indicators India's statistics bodies
actually revise in practice: CPI inflation (MOSPI) and GDP growth
(MOSPI/CSO, advance -> provisional -> final estimates). The other 5 seeded
indicators (repo rate, 10Y G-Sec yield, INR/USD, Brent crude, gold) are
continuously market-quoted rates/prices, not periodically-revised
statistics — inventing a fake "vintage history" for them would be
precision this data doesn't have. See docs/ARCHITECTURE.md §9.
"""

import random
from datetime import date, timedelta

# code -> (release frequency, days after period-end for the first release,
# days after the first release for a single revision)
VINTAGE_INDICATORS: dict[str, tuple[str, int, int]] = {
    "cpi_inflation": ("monthly", 14, 30),
    "gdp_growth": ("quarterly", 45, 75),
}

PERIODS_TO_GENERATE = 8


def _month_end(d: date) -> date:
    next_month = d.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)


def _quarter_end(d: date) -> date:
    quarter_month = ((d.month - 1) // 3) * 3 + 3
    return _month_end(date(d.year, quarter_month, 1))


def _shift_period(period_end: date, frequency: str, back: int) -> date:
    if frequency == "monthly":
        month_index = period_end.year * 12 + (period_end.month - 1) - back
        year, month = divmod(month_index, 12)
        return _month_end(date(year, month + 1, 1))
    quarter_index = (period_end.year * 4 + (period_end.month - 1) // 3) - back
    year, quarter = divmod(quarter_index, 4)
    return _quarter_end(date(year, quarter * 3 + 1, 1))


def generate_releases(code: str, current_value: float, today: date) -> list[dict]:
    """Returns [{"period","value","revision_number","release_date"}, ...],
    oldest first. Deterministic per (code, current_value, today). The most
    recent period's latest revision equals `current_value` — consistent
    with the single-current-value MacroIndicator row this vintage history
    supplements, not contradicts."""
    if code not in VINTAGE_INDICATORS:
        return []

    frequency, first_lag_days, revision_lag_days = VINTAGE_INDICATORS[code]
    rng = random.Random(f"aparix-macro-vintage-{code}")
    latest_period_end = _month_end(today) if frequency == "monthly" else _quarter_end(today)

    releases: list[dict] = []
    value = current_value
    for periods_ago in range(PERIODS_TO_GENERATE):
        period_end = _shift_period(latest_period_end, frequency, periods_ago)
        if periods_ago > 0:
            # Walk backward from the current value with small, plausible
            # period-over-period noise.
            noise = rng.gauss(0.0, abs(current_value) * 0.03 + 0.05)
            value = value - noise if periods_ago == 1 else value + rng.gauss(0.0, abs(current_value) * 0.02)

        first_release_date = period_end + timedelta(days=first_lag_days)
        if first_release_date > today:
            continue  # this period hasn't actually been released yet

        first_value = round(value + rng.gauss(0.0, abs(current_value) * 0.015), 2)
        releases.append(
            {"period": period_end, "value": first_value, "revision_number": 0, "release_date": first_release_date}
        )

        revised_release_date = first_release_date + timedelta(days=revision_lag_days)
        if revised_release_date <= today:
            # The most recent period's final revision matches the stored
            # current value exactly; earlier periods drift slightly on
            # revision, same as real statistical practice.
            revised_value = round(current_value, 2) if periods_ago == 0 else round(value, 2)
            releases.append(
                {
                    "period": period_end,
                    "value": revised_value,
                    "revision_number": 1,
                    "release_date": revised_release_date,
                }
            )

    return releases
