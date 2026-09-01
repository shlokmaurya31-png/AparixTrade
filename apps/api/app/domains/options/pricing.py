"""Black-Scholes option pricing/Greeks — Phase 6.

Same rules as domains/risk/analytics.py and domains/simulation/*: pure
functions (no DB, no I/O), fixture-tested (tests/test_options_pricing.py)
against known closed-form identities and published reference values, not
eyeballed. European options only (no early exercise, no dividends) — a
standard simplification for an equity-options illustration; see
docs/ARCHITECTURE.md Phase 6 trade-offs.
"""

import math

_SQRT_2PI = math.sqrt(2 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def _d1_d2(spot: float, strike: float, t_years: float, rate: float, iv: float) -> tuple[float, float]:
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    d2 = d1 - iv * math.sqrt(t_years)
    return d1, d2


def black_scholes_price(spot: float, strike: float, t_years: float, rate: float, iv: float, option_type: str) -> float:
    """European option price. At/after expiry (t_years <= 0) or with no time
    value left to model (iv <= 0), falls back to intrinsic value rather than
    dividing by zero."""
    if t_years <= 0 or iv <= 0:
        intrinsic = max(spot - strike, 0.0) if option_type == "call" else max(strike - spot, 0.0)
        return round(intrinsic, 4)

    d1, d2 = _d1_d2(spot, strike, t_years, rate, iv)
    discounted_strike = strike * math.exp(-rate * t_years)
    if option_type == "call":
        price = spot * _norm_cdf(d1) - discounted_strike * _norm_cdf(d2)
    else:
        price = discounted_strike * _norm_cdf(-d2) - spot * _norm_cdf(-d1)
    return round(max(price, 0.0), 4)


def black_scholes_greeks(spot: float, strike: float, t_years: float, rate: float, iv: float, option_type: str) -> dict:
    """delta, gamma, theta (per calendar day), vega (per 1 vol point, e.g.
    IV 20% -> 21%), rho (per 1 rate point, e.g. 6.5% -> 7.5%) — the
    conventional per-unit quoting practitioners actually read, not the raw
    per-year/per-100%-vol calculus values."""
    if t_years <= 0 or iv <= 0:
        delta = (1.0 if spot > strike else 0.0) if option_type == "call" else (-1.0 if spot < strike else 0.0)
        return {"delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}

    d1, d2 = _d1_d2(spot, strike, t_years, rate, iv)
    pdf_d1 = _norm_pdf(d1)
    discounted_strike = strike * math.exp(-rate * t_years)
    sqrt_t = math.sqrt(t_years)

    if option_type == "call":
        delta = _norm_cdf(d1)
        theta_annual = -(spot * pdf_d1 * iv) / (2 * sqrt_t) - rate * discounted_strike * _norm_cdf(d2)
        rho = discounted_strike * t_years * _norm_cdf(d2) / 100
    else:
        delta = _norm_cdf(d1) - 1
        theta_annual = -(spot * pdf_d1 * iv) / (2 * sqrt_t) + rate * discounted_strike * _norm_cdf(-d2)
        rho = -discounted_strike * t_years * _norm_cdf(-d2) / 100

    gamma = pdf_d1 / (spot * iv * sqrt_t)
    vega = spot * pdf_d1 * sqrt_t / 100

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta_annual / 365, 4),
        "vega": round(vega, 4),
        "rho": round(rho, 4),
    }
