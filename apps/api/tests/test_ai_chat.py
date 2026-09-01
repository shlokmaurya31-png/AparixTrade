from httpx import AsyncClient


async def _create_portfolio_with_holding(client: AsyncClient, headers: dict) -> str:
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "Test Portfolio", "kind": "long_term"}, headers=headers
    )
    assert portfolio.status_code == 201
    portfolio_id = portfolio.json()["id"]

    holding = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"symbol": "RELIANCE", "quantity": 10, "avg_price": 2500.0},
        headers=headers,
    )
    assert holding.status_code == 201
    return portfolio_id


async def test_ai_chat_cites_only_real_tool_output(client: AsyncClient, auth_headers: dict):
    portfolio_id = await _create_portfolio_with_holding(client, auth_headers)

    analytics = await client.get(f"/api/v1/portfolios/{portfolio_id}/analytics", headers=auth_headers)
    assert analytics.status_code == 200
    real_total_value = analytics.json()["total_value"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "How is my portfolio doing?"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()

    assert body["provider"] == "mock"
    assert len(body["tool_calls"]) == 1
    tool_call = body["tool_calls"][0]
    assert tool_call["tool_name"] == "get_portfolio"

    # The number the tool actually returned must equal the number the
    # portfolio analytics endpoint independently computed — this is the
    # no-hallucination guarantee: the AI cannot report a different total
    # value than the one the deterministic engine produced.
    assert tool_call["result"]["total_value"] == real_total_value
    assert "DEMO DATA" in body["message"]


async def test_ai_chat_sector_question_uses_sector_tool(client: AsyncClient, auth_headers: dict):
    portfolio_id = await _create_portfolio_with_holding(client, auth_headers)

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "What is my biggest sector exposure?"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "get_sector_exposure"
    assert "Energy" in body["message"]  # RELIANCE's seeded sector


async def test_ai_chat_unknown_portfolio_is_rejected(client: AsyncClient, auth_headers: dict):
    fake_id = "00000000-0000-0000-0000-000000000000"
    chat = await client.post(
        "/api/v1/ai/chat", json={"portfolio_id": fake_id, "message": "hi"}, headers=auth_headers
    )
    assert chat.status_code == 404
