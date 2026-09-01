"""Corporate action adjustment engine — pure functions, no I/O, fixture-
tested against a hand-constructed series with a real embedded split
discontinuity (tests/test_corporate_actions_analytics.py), same discipline
as every other quant module in this codebase.

Not applied to this app's live seeded candle history this session —
Candle.close is treated as already-adjusted (the convention most real
market-data feeds use for "Close" by default), so there is nothing to
retroactively rewrite for the currently-tradable mock universe. This
module exists to prove the algorithm is correct on its own terms; see
docs/ARCHITECTURE.md §9 for the full trade-off.
"""

from datetime import date


def cumulative_adjustment_factor(as_of: date, ratio_actions: list[dict]) -> float:
    """The multiplier that converts a RAW price observed on `as_of` to the
    current (fully-adjusted) share-count scale: 1 / product(ratio) over
    every action whose ex_date is strictly after `as_of`. A price on or
    after an action's ex_date is already on the post-action scale and
    needs no adjustment for that action."""
    cumulative_ratio = 1.0
    for action in ratio_actions:
        if action["ex_date"] > as_of and action["ratio"]:
            cumulative_ratio *= action["ratio"]
    return 1.0 / cumulative_ratio if cumulative_ratio else 1.0


def adjust_price_series(candles: list[dict], ratio_actions: list[dict]) -> list[dict]:
    """`candles`: list of {"trade_date": date, "open","high","low","close": float, "volume": int}.
    `ratio_actions`: list of {"ex_date": date, "ratio": float} — caller
    filters to split/bonus/rights (core/corporate_action_types.py::RATIO_ACTION_TYPES)
    before calling; dividends/buybacks don't affect the share count and
    have no place here.

    Returns a new list (input untouched) with open/high/low/close scaled so
    the whole series is comparable on today's share-count scale, and volume
    inversely scaled (the same rupee value trades as more shares after a
    split). Adds `adjustment_factor` per row so a caller can see exactly
    what was applied, not just the result.
    """
    adjusted = []
    for candle in candles:
        factor = cumulative_adjustment_factor(candle["trade_date"], ratio_actions)
        adjusted.append(
            {
                **candle,
                "open": round(candle["open"] * factor, 4),
                "high": round(candle["high"] * factor, 4),
                "low": round(candle["low"] * factor, 4),
                "close": round(candle["close"] * factor, 4),
                "volume": round(candle["volume"] / factor) if factor else candle["volume"],
                "adjustment_factor": round(factor, 6),
            }
        )
    return adjusted
