import datetime

import pytest
from httpx import AsyncClient

from app.core.db import AsyncSessionLocal
from app.domains.options.service import UnknownSymbolError, get_chain, list_expiries

# ── Pure/service-level chain generation ─────────────────────────────────────


def test_list_expiries_returns_four_upcoming_thursdays():
    expiries = list_expiries(today=datetime.date(2026, 1, 1))  # a Thursday
    assert len(expiries) == 4
    assert all(e.weekday() == 3 for e in expiries)
    assert expiries == sorted(expiries)
    assert all(e > datetime.date(2026, 1, 1) for e in expiries)


async def test_get_chain_returns_calls_and_puts_around_spot(client: AsyncClient):
    # `client` fixture drives app startup (lifespan), which seeds securities
    # and initializes live_market_state — required before get_chain can
    # resolve a spot price.
    expiry = list_expiries()[0]
    async with AsyncSessionLocal() as db:
        chain = await get_chain(db, "RELIANCE", expiry)

    assert chain["symbol"] == "RELIANCE"
    assert chain["spot"] > 0
    assert chain["is_mock"] is True
    calls = [c for c in chain["contracts"] if c["option_type"] == "call"]
    puts = [c for c in chain["contracts"] if c["option_type"] == "put"]
    assert len(calls) == len(puts) > 0
    assert all(c["premium"] >= 0 for c in chain["contracts"])
    assert all(c["iv_pct"] > 0 for c in chain["contracts"])


async def test_chain_is_deterministic_for_same_symbol_and_expiry(client: AsyncClient):
    expiry = list_expiries()[0]
    async with AsyncSessionLocal() as db:
        chain_a = await get_chain(db, "TCS", expiry)
        chain_b = await get_chain(db, "TCS", expiry)
    assert chain_a["contracts"] == chain_b["contracts"]


async def test_get_chain_unknown_symbol_raises(client: AsyncClient):
    expiry = list_expiries()[0]
    async with AsyncSessionLocal() as db:
        with pytest.raises(UnknownSymbolError):
            await get_chain(db, "NOTASYMBOL", expiry)


async def test_put_skew_prices_downside_strikes_with_higher_iv(client: AsyncClient):
    # Equity-style skew (see domains/options/service.py SKEW): a strike well
    # below spot should carry higher assumed IV than one well above spot.
    expiry = list_expiries()[0]
    async with AsyncSessionLocal() as db:
        chain = await get_chain(db, "HDFCBANK", expiry)
    spot = chain["spot"]
    low_strike_iv = min(
        (c["iv_pct"] for c in chain["contracts"] if c["strike"] < spot * 0.85), default=None
    )
    high_strike_iv = min(
        (c["iv_pct"] for c in chain["contracts"] if c["strike"] > spot * 1.15), default=None
    )
    if low_strike_iv is not None and high_strike_iv is not None:
        assert low_strike_iv > high_strike_iv


# ── HTTP endpoints ───────────────────────────────────────────────────────────


async def test_expiries_endpoint(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/options/expiries", params={"symbol": "RELIANCE"}, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "RELIANCE"
    assert len(body["expiries"]) == 4


async def test_chain_endpoint(client: AsyncClient, auth_headers: dict):
    expiry = list_expiries()[0].isoformat()
    response = await client.get(
        "/api/v1/options/chain", params={"symbol": "INFY", "expiry": expiry}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "INFY"
    assert len(body["contracts"]) > 0


async def test_chain_endpoint_unknown_symbol_is_404(client: AsyncClient, auth_headers: dict):
    expiry = list_expiries()[0].isoformat()
    response = await client.get(
        "/api/v1/options/chain", params={"symbol": "NOPE", "expiry": expiry}, headers=auth_headers
    )
    assert response.status_code == 404


async def test_price_endpoint(client: AsyncClient, auth_headers: dict):
    expiry = list_expiries()[0].isoformat()
    response = await client.get(
        "/api/v1/options/price",
        params={"symbol": "ITC", "strike": 460, "expiry": expiry, "option_type": "call"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "ITC"
    assert body["option_type"] == "call"
    assert body["premium"] >= 0


# ── AI Terminal integration (mock provider) ─────────────────────────────────


async def test_ai_chat_options_chain_intent(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post("/api/v1/portfolios", json={"name": "P", "kind": "trading"}, headers=auth_headers)
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "show me the options chain for RELIANCE"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "get_options_chain"
    assert body["tool_calls"][0]["result"]["symbol"] == "RELIANCE"


async def test_ai_chat_price_option_intent(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post("/api/v1/portfolios", json={"name": "P2", "kind": "trading"}, headers=auth_headers)
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "what's the delta on a TCS call option"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "price_option"
    assert body["tool_calls"][0]["result"]["symbol"] == "TCS"
    assert body["tool_calls"][0]["result"]["option_type"] == "call"
