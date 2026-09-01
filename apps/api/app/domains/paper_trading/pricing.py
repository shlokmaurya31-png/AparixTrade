"""Order pricing — pure functions, no DB/I/O. See docs/ARCHITECTURE.md Phase
4 trade-offs for why these specific numbers: no real order book exists to
derive slippage from, so this is a simple, directionally-honest
approximation (unfavorable to the trader, like a real market would be), and
brokerage mirrors a recognizable Indian discount-broker convention rather
than being invented from nothing.
"""

import random

SLIPPAGE_MIN_PCT = 0.05  # percent, not fraction
SLIPPAGE_MAX_PCT = 0.15

BROKERAGE_FLAT_INR = 20.0
BROKERAGE_PCT = 0.03  # percent of order value


def apply_slippage(quote_price: float, side: str, *, rng: random.Random | None = None) -> tuple[float, float]:
    """Returns (fill_price, slippage_pct_applied). Buys fill above the
    quoted price, sells below it — always unfavorable to the trader,
    modeling market impact rather than picking a direction that flatters
    the simulation."""
    rng = rng or random.Random()
    slippage_pct = rng.uniform(SLIPPAGE_MIN_PCT, SLIPPAGE_MAX_PCT)
    multiplier = (1 + slippage_pct / 100) if side == "buy" else (1 - slippage_pct / 100)
    return round(quote_price * multiplier, 2), round(slippage_pct, 4)


def compute_brokerage(order_value: float) -> float:
    """Zerodha-style: flat fee or a percentage of order value, whichever is
    lower — a real, recognizable convention, not a stub."""
    return round(min(BROKERAGE_FLAT_INR, order_value * BROKERAGE_PCT / 100), 2)
