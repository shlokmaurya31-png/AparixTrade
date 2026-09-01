import math

import pytest

from app.domains.options.pricing import black_scholes_greeks, black_scholes_price

# Hull, "Options, Futures, and Other Derivatives": S=42, K=40, r=10%, sigma=20%,
# T=0.5 years -> c ~= 4.76, p ~= 0.81. A widely-published textbook example,
# used here as an external reference point (not just an internal identity).
HULL_SPOT = 42.0
HULL_STRIKE = 40.0
HULL_T = 0.5
HULL_RATE = 0.10
HULL_IV = 0.20


def test_call_price_matches_published_reference_value():
    price = black_scholes_price(HULL_SPOT, HULL_STRIKE, HULL_T, HULL_RATE, HULL_IV, "call")
    assert price == pytest.approx(4.76, abs=0.05)


def test_put_price_matches_published_reference_value():
    price = black_scholes_price(HULL_SPOT, HULL_STRIKE, HULL_T, HULL_RATE, HULL_IV, "put")
    assert price == pytest.approx(0.81, abs=0.05)


def test_put_call_parity_holds_exactly():
    # c - p = S - K*e^(-rT) is an algebraic identity, independent of any
    # memorized reference value — a stronger check than the fixture above.
    call = black_scholes_price(HULL_SPOT, HULL_STRIKE, HULL_T, HULL_RATE, HULL_IV, "call")
    put = black_scholes_price(HULL_SPOT, HULL_STRIKE, HULL_T, HULL_RATE, HULL_IV, "put")
    expected = HULL_SPOT - HULL_STRIKE * math.exp(-HULL_RATE * HULL_T)
    assert (call - put) == pytest.approx(expected, abs=0.01)


def test_delta_difference_equals_one():
    # d(call - put)/dS = 1 always, another exact identity.
    call_greeks = black_scholes_greeks(HULL_SPOT, HULL_STRIKE, HULL_T, HULL_RATE, HULL_IV, "call")
    put_greeks = black_scholes_greeks(HULL_SPOT, HULL_STRIKE, HULL_T, HULL_RATE, HULL_IV, "put")
    assert (call_greeks["delta"] - put_greeks["delta"]) == pytest.approx(1.0, abs=1e-4)


def test_gamma_and_vega_are_identical_for_call_and_put():
    call_greeks = black_scholes_greeks(HULL_SPOT, HULL_STRIKE, HULL_T, HULL_RATE, HULL_IV, "call")
    put_greeks = black_scholes_greeks(HULL_SPOT, HULL_STRIKE, HULL_T, HULL_RATE, HULL_IV, "put")
    assert call_greeks["gamma"] == pytest.approx(put_greeks["gamma"], abs=1e-8)
    assert call_greeks["vega"] == pytest.approx(put_greeks["vega"], abs=1e-8)
    assert call_greeks["gamma"] > 0
    assert call_greeks["vega"] > 0


def test_call_delta_is_between_zero_and_one():
    greeks = black_scholes_greeks(HULL_SPOT, HULL_STRIKE, HULL_T, HULL_RATE, HULL_IV, "call")
    assert 0.0 <= greeks["delta"] <= 1.0


def test_put_delta_is_between_minus_one_and_zero():
    greeks = black_scholes_greeks(HULL_SPOT, HULL_STRIKE, HULL_T, HULL_RATE, HULL_IV, "put")
    assert -1.0 <= greeks["delta"] <= 0.0


def test_at_the_money_call_delta_is_near_half():
    price_greeks = black_scholes_greeks(100.0, 100.0, 1.0, 0.05, 0.20, "call")
    assert price_greeks["delta"] == pytest.approx(0.6, abs=0.15)


def test_expired_option_falls_back_to_intrinsic_value():
    itm_call = black_scholes_price(110.0, 100.0, 0.0, 0.05, 0.20, "call")
    assert itm_call == pytest.approx(10.0, abs=1e-6)
    otm_call = black_scholes_price(90.0, 100.0, 0.0, 0.05, 0.20, "call")
    assert otm_call == pytest.approx(0.0, abs=1e-6)


def test_expired_option_has_zero_gamma_vega_theta():
    greeks = black_scholes_greeks(110.0, 100.0, 0.0, 0.05, 0.20, "call")
    assert greeks["gamma"] == 0.0
    assert greeks["vega"] == 0.0
    assert greeks["theta"] == 0.0
