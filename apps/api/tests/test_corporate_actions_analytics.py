import datetime

import pytest

from app.domains.corporate_actions.analytics import adjust_price_series, cumulative_adjustment_factor

# A hand-constructed raw series with a real 2-for-1 split discontinuity on
# 2024-01-10 (ratio=2.0): pre-split trades around 200, post-split around
# 100 — exactly what a real, unadjusted raw feed looks like. Not live data.
SPLIT_DATE = datetime.date(2024, 1, 10)
RAW_CANDLES = [
    {"trade_date": datetime.date(2024, 1, 8), "open": 198.0, "high": 202.0, "low": 197.0, "close": 200.0, "volume": 1000},
    {"trade_date": datetime.date(2024, 1, 9), "open": 200.0, "high": 204.0, "low": 199.0, "close": 202.0, "volume": 1100},
    # ex_date itself trades at the new (post-split) scale.
    {"trade_date": SPLIT_DATE, "open": 101.0, "high": 103.0, "low": 99.0, "close": 101.0, "volume": 2200},
    {"trade_date": datetime.date(2024, 1, 11), "open": 101.0, "high": 105.0, "low": 100.0, "close": 103.0, "volume": 2000},
]
SPLIT_ACTION = {"ex_date": SPLIT_DATE, "ratio": 2.0}


def test_cumulative_factor_is_one_on_or_after_ex_date():
    assert cumulative_adjustment_factor(SPLIT_DATE, [SPLIT_ACTION]) == 1.0
    assert cumulative_adjustment_factor(datetime.date(2024, 1, 11), [SPLIT_ACTION]) == 1.0


def test_cumulative_factor_halves_a_pre_split_price():
    assert cumulative_adjustment_factor(datetime.date(2024, 1, 8), [SPLIT_ACTION]) == pytest.approx(0.5)


def test_cumulative_factor_with_no_actions_is_one():
    assert cumulative_adjustment_factor(datetime.date(2024, 1, 8), []) == 1.0


def test_adjust_price_series_smooths_the_split_discontinuity():
    adjusted = adjust_price_series(RAW_CANDLES, [SPLIT_ACTION])
    closes = [row["close"] for row in adjusted]
    # Raw: 200, 202, 101, 103 (a ~2x jump at the split). Adjusted: 100, 101,
    # 101, 103 — continuous, no artificial discontinuity.
    assert closes == pytest.approx([100.0, 101.0, 101.0, 103.0])


def test_adjust_price_series_scales_pre_split_volume_up():
    adjusted = adjust_price_series(RAW_CANDLES, [SPLIT_ACTION])
    # Same rupee value trades as 2x the shares post-split — pre-split
    # volume should double under adjustment (1000 -> 2000).
    assert adjusted[0]["volume"] == 2000
    assert adjusted[2]["volume"] == 2200  # on/after ex_date: unchanged


def test_adjust_price_series_does_not_mutate_input():
    original_first_close = RAW_CANDLES[0]["close"]
    adjust_price_series(RAW_CANDLES, [SPLIT_ACTION])
    assert RAW_CANDLES[0]["close"] == original_first_close


def test_adjust_price_series_with_no_ratio_actions_is_unchanged():
    adjusted = adjust_price_series(RAW_CANDLES, [])
    assert [row["close"] for row in adjusted] == [row["close"] for row in RAW_CANDLES]
    assert all(row["adjustment_factor"] == 1.0 for row in adjusted)


def test_adjust_price_series_compounds_multiple_actions():
    # A second, later split (ratio 1.5) should compound with the first for
    # candles before both ex_dates.
    second_split = {"ex_date": datetime.date(2024, 1, 11), "ratio": 1.5}
    adjusted = adjust_price_series(RAW_CANDLES, [SPLIT_ACTION, second_split])
    # Day 2024-01-08: before both -> factor = 1/(2.0*1.5) = 1/3
    assert adjusted[0]["adjustment_factor"] == pytest.approx(1 / 3, abs=1e-6)
    # Day 2024-01-10 (the split's own ex_date): only the second split is still ahead -> factor = 1/1.5
    assert adjusted[2]["adjustment_factor"] == pytest.approx(1 / 1.5, abs=1e-6)
    # Day 2024-01-11 (on/after both ex_dates): factor = 1
    assert adjusted[3]["adjustment_factor"] == pytest.approx(1.0, abs=1e-6)
