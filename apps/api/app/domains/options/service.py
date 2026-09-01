"""Synthetic options chain generation — Phase 6.

A chain is entirely derived, not persisted: strikes/IV/prices/Greeks are
computed on request from the current simulated spot price
(market_data.live_market_state) and an assumed volatility skew, using
closed-form Black-Scholes (pricing.py). Deterministic per symbol+expiry
(seeded RNG, same approach as MockMarketDataProvider) so repeated requests
return the same chain, but there is no "options candle history" table —
persisting derived numbers as if they were an independently observed feed
would misrepresent them. See docs/ARCHITECTURE.md Phase 6 trade-offs.
"""

import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.macro.service import get_indicator
from app.domains.market_data.service import get_security_by_symbol, live_market_state
from app.domains.options import pricing
from app.domains.risk.analytics import DEFAULT_RISK_FREE_RATE_ANNUAL

NUM_EXPIRIES = 4
STRIKE_RANGE_PCT = 0.20  # +/- 20% around spot
STRIKE_STEP_COUNT = 8  # 8 strikes each side of ATM, plus ATM = 17 strikes
BASE_IV_MIN = 0.18
BASE_IV_MAX = 0.32
SMILE_CURVATURE = 0.15
SKEW = 0.08  # equity-style skew: strikes below spot (put side) price richer


class UnknownSymbolError(Exception):
    pass


def list_expiries(today: date | None = None) -> list[date]:
    """A small synthetic set of near-term Thursdays — NOT NSE's real weekly/
    monthly expiry calendar (holiday adjustments, index-vs-stock rules).
    Plausible dates, not guaranteed to match a real NSE expiry."""
    today = today or datetime.now(timezone.utc).date()
    expiries: list[date] = []
    d = today
    while len(expiries) < NUM_EXPIRIES:
        d += timedelta(days=1)
        if d.weekday() == 3:  # Thursday
            expiries.append(d)
    return expiries


def _round_strike(raw: float, spot: float) -> float:
    if spot >= 5000:
        step = 50
    elif spot >= 1000:
        step = 10
    elif spot >= 100:
        step = 5
    else:
        step = 1
    return round(round(raw / step) * step, 2)


def _strike_ladder(spot: float) -> list[float]:
    raw = {
        spot * (1 + (i / STRIKE_STEP_COUNT) * STRIKE_RANGE_PCT) for i in range(-STRIKE_STEP_COUNT, STRIKE_STEP_COUNT + 1)
    }
    return sorted({_round_strike(r, spot) for r in raw if r > 0})


def _iv_for_strike(base_iv: float, strike: float, spot: float) -> float:
    moneyness = (strike - spot) / spot
    iv = base_iv + SMILE_CURVATURE * moneyness**2 - SKEW * moneyness
    return round(max(iv, 0.05), 4)


async def _risk_free_rate(db: AsyncSession) -> float:
    # Same source as domains/risk/service.py::get_risk_free_rate_annual —
    # one mock G-Sec-derived rate used everywhere pricing needs "the"
    # risk-free rate, not a second, divergent assumption for options.
    indicator = await get_indicator(db, "gsec_10y")
    return indicator.value / 100 if indicator else DEFAULT_RISK_FREE_RATE_ANNUAL


async def get_chain(db: AsyncSession, symbol: str, expiry: date) -> dict:
    security = await get_security_by_symbol(db, symbol)
    if security is None:
        raise UnknownSymbolError(symbol)
    quote = live_market_state.get_quote(security.symbol)
    if quote is None:
        raise UnknownSymbolError(symbol)
    spot = quote["last_price"]

    today = datetime.now(timezone.utc).date()
    t_years = max((expiry - today).days, 1) / 365.0
    rate = await _risk_free_rate(db)

    rng = random.Random(f"aparix-options-{security.symbol}-{expiry.isoformat()}")
    base_iv = rng.uniform(BASE_IV_MIN, BASE_IV_MAX)

    contracts = []
    for strike in _strike_ladder(spot):
        iv = _iv_for_strike(base_iv, strike, spot)
        for option_type in ("call", "put"):
            premium = pricing.black_scholes_price(spot, strike, t_years, rate, iv, option_type)
            greeks = pricing.black_scholes_greeks(spot, strike, t_years, rate, iv, option_type)
            contracts.append(
                {
                    "strike": strike,
                    "option_type": option_type,
                    "premium": premium,
                    "iv_pct": round(iv * 100, 2),
                    **greeks,
                }
            )

    return {
        "symbol": security.symbol,
        "spot": spot,
        "expiry": expiry.isoformat(),
        "days_to_expiry": max((expiry - today).days, 0),
        "risk_free_rate_annual_pct": round(rate * 100, 2),
        "contracts": contracts,
        "is_mock": True,
    }


async def price_single_option(
    db: AsyncSession, symbol: str, *, strike: float, expiry: date, option_type: str
) -> dict:
    """Used by the AI tool 'price_option' for a specific strike the user
    asks about, rather than requiring the whole chain to be fetched and
    filtered client-side."""
    security = await get_security_by_symbol(db, symbol)
    if security is None:
        raise UnknownSymbolError(symbol)
    quote = live_market_state.get_quote(security.symbol)
    if quote is None:
        raise UnknownSymbolError(symbol)
    spot = quote["last_price"]

    today = datetime.now(timezone.utc).date()
    t_years = max((expiry - today).days, 1) / 365.0
    rate = await _risk_free_rate(db)

    rng = random.Random(f"aparix-options-{security.symbol}-{expiry.isoformat()}")
    base_iv = rng.uniform(BASE_IV_MIN, BASE_IV_MAX)
    iv = _iv_for_strike(base_iv, strike, spot)

    premium = pricing.black_scholes_price(spot, strike, t_years, rate, iv, option_type)
    greeks = pricing.black_scholes_greeks(spot, strike, t_years, rate, iv, option_type)

    return {
        "symbol": security.symbol,
        "spot": spot,
        "strike": strike,
        "option_type": option_type,
        "expiry": expiry.isoformat(),
        "days_to_expiry": max((expiry - today).days, 0),
        "premium": premium,
        "iv_pct": round(iv * 100, 2),
        "risk_free_rate_annual_pct": round(rate * 100, 2),
        **greeks,
        "is_mock": True,
    }
