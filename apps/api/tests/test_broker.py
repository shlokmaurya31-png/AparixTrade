import pytest
from httpx import AsyncClient

from app.core.crypto import EncryptionNotConfiguredError, decrypt_secret, encrypt_secret
from app.domains.broker.adapter import BrokerCredentials, MockBrokerAdapter

# ── Crypto (pure-ish, but reads settings) ───────────────────────────────────


def test_encrypt_decrypt_round_trip():
    ciphertext = encrypt_secret("super-secret-token")
    assert ciphertext != "super-secret-token"
    assert decrypt_secret(ciphertext) == "super-secret-token"


def test_encryption_not_configured_raises_instead_of_storing_plaintext(monkeypatch):
    from app.core import config

    monkeypatch.setenv("BROKER_ENCRYPTION_KEY", "")
    config.get_settings.cache_clear()
    try:
        with pytest.raises(EncryptionNotConfiguredError):
            encrypt_secret("anything")
    finally:
        config.get_settings.cache_clear()


# ── MockBrokerAdapter (pure-ish async, no DB) ───────────────────────────────


async def test_mock_adapter_complete_login_always_succeeds():
    adapter = MockBrokerAdapter()
    result = await adapter.complete_login(api_key=None, api_secret=None, request_token=None)
    assert result.access_token
    assert result.broker_user_id == "MOCK001"


async def test_mock_adapter_returns_fixed_seeded_holdings():
    adapter = MockBrokerAdapter()
    holdings = await adapter.get_holdings(BrokerCredentials())
    symbols = {h.symbol for h in holdings}
    assert symbols == {"INFY", "HDFCBANK", "ITC"}


async def test_mock_adapter_place_order_is_rejected_not_executed():
    adapter = MockBrokerAdapter()
    result = await adapter.place_order(BrokerCredentials(), symbol="INFY", side="buy", quantity=1)
    assert result.status == "rejected"
    assert result.fill_price is None


# ── HTTP-level: connect / sync / disconnect flow ────────────────────────────


async def test_status_reports_disconnected_before_any_connect(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/broker/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["broker"] is None
    assert body["live_trading_enabled"] is False


async def test_connect_then_status_reports_connected(client: AsyncClient, auth_headers: dict):
    connect = await client.post("/api/v1/broker/connect", json={}, headers=auth_headers)
    assert connect.status_code == 200
    body = connect.json()
    assert body["connected"] is True
    assert body["broker"] == "mock"
    assert body["broker_user_id"] == "MOCK001"

    status_response = await client.get("/api/v1/broker/status", headers=auth_headers)
    assert status_response.json()["connected"] is True


async def test_sync_before_connect_is_rejected_not_a_crash(client: AsyncClient, auth_headers: dict):
    response = await client.post("/api/v1/broker/sync", headers=auth_headers)
    assert response.status_code == 400


async def test_connect_then_sync_populates_broker_portfolio(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/broker/connect", json={}, headers=auth_headers)

    sync = await client.post("/api/v1/broker/sync", headers=auth_headers)
    assert sync.status_code == 200
    body = sync.json()
    assert body["synced_holdings"] == 3
    assert body["skipped_symbols"] == []

    portfolio = await client.get("/api/v1/broker/portfolio", headers=auth_headers)
    assert portfolio.status_code == 200
    holdings = portfolio.json()["holdings"]
    assert {h["symbol"] for h in holdings} == {"INFY", "HDFCBANK", "ITC"}
    assert portfolio.json()["is_mock"] is True
    assert portfolio.json()["total_value"] > 0


async def test_resync_replaces_holdings_not_duplicates_them(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/broker/connect", json={}, headers=auth_headers)
    await client.post("/api/v1/broker/sync", headers=auth_headers)
    await client.post("/api/v1/broker/sync", headers=auth_headers)  # second sync, same fixed mock holdings

    portfolio = await client.get("/api/v1/broker/portfolio", headers=auth_headers)
    holdings = portfolio.json()["holdings"]
    assert len(holdings) == 3  # not 6 — re-sync upserts, doesn't append


async def test_disconnect_removes_connection_but_keeps_last_synced_holdings(
    client: AsyncClient, auth_headers: dict
):
    await client.post("/api/v1/broker/connect", json={}, headers=auth_headers)
    await client.post("/api/v1/broker/sync", headers=auth_headers)

    disconnect = await client.delete("/api/v1/broker/disconnect", headers=auth_headers)
    assert disconnect.status_code == 204

    status_response = await client.get("/api/v1/broker/status", headers=auth_headers)
    assert status_response.json()["connected"] is False

    # A prior sync's holdings are a local record, not deleted just because
    # the live connection was revoked — same as disconnecting a bank sync
    # doesn't erase your transaction history.
    portfolio = await client.get("/api/v1/broker/portfolio", headers=auth_headers)
    assert len(portfolio.json()["holdings"]) == 3

    # But a sync attempt after disconnect is rejected, not silently reusing
    # the old (now revoked) credentials.
    sync = await client.post("/api/v1/broker/sync", headers=auth_headers)
    assert sync.status_code == 400


# ── Live order placement gate ───────────────────────────────────────────────


async def test_live_order_placement_is_disabled_by_default(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/broker/connect", json={}, headers=auth_headers)
    response = await client.post(
        "/api/v1/broker/orders", json={"symbol": "INFY", "side": "buy", "quantity": 1}, headers=auth_headers
    )
    assert response.status_code == 403


async def test_live_order_placement_when_enabled_uses_the_adapter(
    client: AsyncClient, auth_headers: dict, monkeypatch
):
    from app.core import config

    monkeypatch.setenv("BROKER_LIVE_TRADING_ENABLED", "true")
    config.get_settings.cache_clear()
    try:
        await client.post("/api/v1/broker/connect", json={}, headers=auth_headers)
        response = await client.post(
            "/api/v1/broker/orders", json={"symbol": "INFY", "side": "buy", "quantity": 1}, headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        # MockBrokerAdapter.place_order always rejects — proves the real
        # adapter call path was exercised, not faked a fill.
        assert body["status"] == "rejected"
        assert body["fill_price"] is None
    finally:
        config.get_settings.cache_clear()


async def test_live_order_placement_without_connection_is_rejected(
    client: AsyncClient, auth_headers: dict, monkeypatch
):
    from app.core import config

    monkeypatch.setenv("BROKER_LIVE_TRADING_ENABLED", "true")
    config.get_settings.cache_clear()
    try:
        response = await client.post(
            "/api/v1/broker/orders", json={"symbol": "INFY", "side": "buy", "quantity": 1}, headers=auth_headers
        )
        assert response.status_code == 400
    finally:
        config.get_settings.cache_clear()


# ── AI Terminal integration (mock provider) ─────────────────────────────────


async def test_ai_chat_broker_holdings_without_connection_gives_honest_error(
    client: AsyncClient, auth_headers: dict
):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "Long Term", "kind": "long_term"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "what does my broker account hold"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "get_broker_holdings"
    assert "error" in body["tool_calls"][0]["result"]


async def test_ai_chat_broker_holdings_after_sync(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/broker/connect", json={}, headers=auth_headers)
    await client.post("/api/v1/broker/sync", headers=auth_headers)

    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "Long Term 2", "kind": "long_term"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "what's in my broker account"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "get_broker_holdings"
    assert len(body["tool_calls"][0]["result"]["holdings"]) == 3
