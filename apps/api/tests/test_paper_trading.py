import random

import pytest
from httpx import AsyncClient

from app.domains.paper_trading.pricing import SLIPPAGE_MAX_PCT, SLIPPAGE_MIN_PCT, apply_slippage, compute_brokerage

# ── Pricing (pure functions) ────────────────────────────────────────────────


def test_apply_slippage_buy_fills_above_quote():
    fill_price, slippage_pct = apply_slippage(1000.0, "buy", rng=random.Random(42))
    assert fill_price > 1000.0
    assert SLIPPAGE_MIN_PCT <= slippage_pct <= SLIPPAGE_MAX_PCT


def test_apply_slippage_sell_fills_below_quote():
    fill_price, slippage_pct = apply_slippage(1000.0, "sell", rng=random.Random(42))
    assert fill_price < 1000.0
    assert SLIPPAGE_MIN_PCT <= slippage_pct <= SLIPPAGE_MAX_PCT


def test_apply_slippage_is_deterministic_given_a_seed():
    a = apply_slippage(1000.0, "buy", rng=random.Random(7))
    b = apply_slippage(1000.0, "buy", rng=random.Random(7))
    assert a == b


def test_compute_brokerage_caps_at_flat_fee_for_large_orders():
    # 0.03% of 1,000,000 = 300, well above the ₹20 flat cap
    assert compute_brokerage(1_000_000) == pytest.approx(20.0)


def test_compute_brokerage_uses_percentage_for_small_orders():
    # 0.03% of 10,000 = 3.0, below the ₹20 flat fee
    assert compute_brokerage(10_000) == pytest.approx(3.0)


# ── HTTP-level: full stack, real DB, real (mock) market data ────────────────


async def test_paper_portfolio_is_created_lazily_with_starting_capital(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/paper/portfolio", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == pytest.approx(1_000_000.0)

    again = await client.get("/api/v1/paper/portfolio", headers=auth_headers)
    assert again.json()["id"] == body["id"]  # same account, not recreated


async def test_buy_order_within_budget_fills_and_debits_cash(client: AsyncClient, auth_headers: dict):
    await client.get("/api/v1/paper/portfolio", headers=auth_headers)
    response = await client.post(
        "/api/v1/paper/portfolio/orders",
        json={"symbol": "RELIANCE", "side": "buy", "quantity": 10},
        headers=auth_headers,
    )
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "filled"
    assert order["fill_price"] > 0
    assert order["brokerage_fee"] > 0
    assert order["rejection_reason"] is None

    portfolio = (await client.get("/api/v1/paper/portfolio", headers=auth_headers)).json()
    expected_cash = 1_000_000.0 - (order["fill_price"] * 10 + order["brokerage_fee"])
    assert portfolio["cash_balance"] == pytest.approx(expected_cash, abs=0.01)


async def test_buy_order_exceeding_cash_is_rejected_not_an_error(client: AsyncClient, auth_headers: dict):
    portfolio_before = (await client.get("/api/v1/paper/portfolio", headers=auth_headers)).json()

    response = await client.post(
        "/api/v1/paper/portfolio/orders",
        json={"symbol": "RELIANCE", "side": "buy", "quantity": 1_000_000},
        headers=auth_headers,
    )
    assert response.status_code == 201  # a rejection is a normal outcome, not an HTTP error
    order = response.json()
    assert order["status"] == "rejected"
    assert order["rejection_reason"] is not None
    assert order["fill_price"] is None

    portfolio_after = (await client.get("/api/v1/paper/portfolio", headers=auth_headers)).json()
    assert portfolio_after["cash_balance"] == pytest.approx(portfolio_before["cash_balance"])


async def test_sell_exceeding_holding_is_rejected(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/paper/portfolio/orders", json={"symbol": "TCS", "side": "sell", "quantity": 5}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "rejected"
    assert "insufficient holding" in body["rejection_reason"].lower()


async def test_sell_partial_holding_reduces_quantity_and_credits_cash(client: AsyncClient, auth_headers: dict):
    buy = await client.post(
        "/api/v1/paper/portfolio/orders",
        json={"symbol": "HDFCBANK", "side": "buy", "quantity": 20},
        headers=auth_headers,
    )
    assert buy.json()["status"] == "filled"
    cash_after_buy = (await client.get("/api/v1/paper/portfolio", headers=auth_headers)).json()["cash_balance"]

    sell = await client.post(
        "/api/v1/paper/portfolio/orders",
        json={"symbol": "HDFCBANK", "side": "sell", "quantity": 8},
        headers=auth_headers,
    )
    assert sell.status_code == 201
    sell_body = sell.json()
    assert sell_body["status"] == "filled"

    cash_after_sell = (await client.get("/api/v1/paper/portfolio", headers=auth_headers)).json()["cash_balance"]
    expected_proceeds = sell_body["fill_price"] * 8 - sell_body["brokerage_fee"]
    assert cash_after_sell == pytest.approx(cash_after_buy + expected_proceeds, abs=0.01)


async def test_preview_does_not_write_to_db(client: AsyncClient, auth_headers: dict):
    portfolio_before = (await client.get("/api/v1/paper/portfolio", headers=auth_headers)).json()
    orders_before = (await client.get("/api/v1/paper/portfolio/orders", headers=auth_headers)).json()

    preview = await client.post(
        "/api/v1/paper/portfolio/preview",
        json={"symbol": "INFY", "side": "buy", "quantity": 5},
        headers=auth_headers,
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["estimated_fill_price"] > 0
    assert body["affordable"] is True

    portfolio_after = (await client.get("/api/v1/paper/portfolio", headers=auth_headers)).json()
    orders_after = (await client.get("/api/v1/paper/portfolio/orders", headers=auth_headers)).json()
    assert portfolio_after["cash_balance"] == pytest.approx(portfolio_before["cash_balance"])
    assert len(orders_after) == len(orders_before)


async def test_evaluate_order_uses_real_candle_data(client: AsyncClient, auth_headers: dict):
    buy = await client.post(
        "/api/v1/paper/portfolio/orders", json={"symbol": "ITC", "side": "buy", "quantity": 3}, headers=auth_headers
    )
    order_id = buy.json()["id"]

    evaluation = await client.get(f"/api/v1/paper/portfolio/orders/{order_id}/evaluation", headers=auth_headers)
    assert evaluation.status_code == 200
    body = evaluation.json()
    assert body["symbol"] == "ITC"
    assert body["range_30d_low"] is not None
    assert body["range_30d_high"] is not None
    assert body["range_30d_low"] <= body["range_30d_high"]
    assert body["fill_percentile_in_30d_range"] is not None


async def test_evaluate_rejected_order_still_returns_data(client: AsyncClient, auth_headers: dict):
    reject = await client.post(
        "/api/v1/paper/portfolio/orders",
        json={"symbol": "RELIANCE", "side": "buy", "quantity": 1_000_000},
        headers=auth_headers,
    )
    order_id = reject.json()["id"]

    evaluation = await client.get(f"/api/v1/paper/portfolio/orders/{order_id}/evaluation", headers=auth_headers)
    assert evaluation.status_code == 200
    assert evaluation.json()["status"] == "rejected"
    assert evaluation.json()["fill_price"] is None


# ── AI Terminal integration (mock provider — the whole test session runs AI_PROVIDER=mock) ──


async def test_ai_chat_preview_trade_uses_the_paper_account_not_the_active_portfolio(
    client: AsyncClient, auth_headers: dict
):
    # The chat is scoped to a completely different (long_term) portfolio —
    # preview_trade must still resolve the user's paper account, not this one.
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "Long Term", "kind": "long_term"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "should I buy RELIANCE"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "preview_trade"
    assert body["tool_calls"][0]["result"]["symbol"] == "RELIANCE"
    assert body["tool_calls"][0]["result"]["side"] == "buy"


async def test_ai_chat_evaluate_order_intent(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "Long Term 2", "kind": "long_term"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    await client.post(
        "/api/v1/paper/portfolio/orders", json={"symbol": "TCS", "side": "buy", "quantity": 2}, headers=auth_headers
    )

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "how was that trade"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "evaluate_order"
    assert body["tool_calls"][0]["result"]["symbol"] == "TCS"
