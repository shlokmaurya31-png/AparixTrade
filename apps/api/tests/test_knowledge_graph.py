from httpx import AsyncClient

from app.core.db import AsyncSessionLocal
from app.domains.knowledge_graph.service import exposure_multipliers, resolve_graph_exposure

# ── Service: resolve_graph_exposure() ───────────────────────────────────


async def test_location_resolves_to_real_affected_securities(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        resolved = await resolve_graph_exposure(db, "Gujarat")
    assert resolved is not None
    assert resolved["kind"] == "location"
    symbols = {a["symbol"] for a in resolved["affected"]}
    assert "RELIANCE" in symbols
    assert "TATAMOTORS" in symbols
    assert "ADANIENT" in symbols


async def test_location_lookup_is_case_insensitive(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        resolved = await resolve_graph_exposure(db, "gujarat")
    assert resolved is not None
    assert resolved["name"] == "Gujarat"


async def test_commodity_resolves_to_real_affected_securities(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        resolved = await resolve_graph_exposure(db, "coal")
    assert resolved is not None
    assert resolved["kind"] == "commodity"
    symbols = {a["symbol"] for a in resolved["affected"]}
    assert "NTPC" in symbols
    assert "ADANIENT" in symbols


async def test_commodity_lookup_also_matches_display_name(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        resolved = await resolve_graph_exposure(db, "Crude Oil")
    assert resolved is not None
    assert resolved["name"] == "Crude Oil"


async def test_unknown_target_resolves_to_none(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        resolved = await resolve_graph_exposure(db, "Antarctica")
    assert resolved is None


async def test_exposure_multipliers_flattens_the_resolved_result():
    resolved = {
        "kind": "location",
        "name": "Gujarat",
        "pass_through_pct": 40.0,
        "affected": [{"symbol": "RELIANCE", "relationship": "major_facility"}],
    }
    assert exposure_multipliers(resolved) == {"RELIANCE": 0.4}


async def test_exposure_multipliers_of_none_is_empty():
    assert exposure_multipliers(None) == {}


# ── HTTP endpoint ────────────────────────────────────────────────────────


async def test_exposure_endpoint_returns_ranked_affected_securities(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/knowledge-graph/exposure/Gujarat", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "location"
    assert any(a["symbol"] == "RELIANCE" for a in body["affected"])


async def test_exposure_endpoint_404s_for_unknown_target(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/knowledge-graph/exposure/Narnia", headers=auth_headers)
    assert response.status_code == 404


async def test_exposure_endpoint_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/knowledge-graph/exposure/Gujarat")
    assert response.status_code == 401


# ── Real event propagation end-to-end (the actual feature this unlocks) ──


async def test_gujarat_cyclone_event_propagates_to_multiple_real_holdings(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "Graph Test", "kind": "long_term"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    for symbol in ["RELIANCE", "TATAMOTORS", "TCS"]:
        await client.post(
            f"/api/v1/portfolios/{portfolio_id}/holdings",
            json={"symbol": symbol, "quantity": 10, "avg_price": 500.0},
            headers=auth_headers,
        )

    events = await client.get("/api/v1/events")
    cyclone_id = next(e for e in events.json() if "Cyclone" in e["headline"] and "Gujarat" in e["headline"])["id"]

    impact = await client.get(
        f"/api/v1/events/{cyclone_id}/impact", params={"portfolio_id": portfolio_id}, headers=auth_headers
    )
    assert impact.status_code == 200
    body = impact.json()
    assert body["target"] == "Gujarat"

    by_symbol = {row["symbol"]: row for row in body["per_holding_impact"]}
    # RELIANCE and TATAMOTORS are both really exposed to Gujarat (Jamnagar
    # refinery, Sanand plant) — both get a real, non-zero, decayed impact.
    assert by_symbol["RELIANCE"]["basis"].startswith("indirect via knowledge graph")
    assert by_symbol["RELIANCE"]["impact"] != 0.0
    assert by_symbol["TATAMOTORS"]["basis"].startswith("indirect via knowledge graph")
    assert by_symbol["TATAMOTORS"]["impact"] != 0.0
    # TCS has no known Gujarat exposure — correctly unaffected.
    assert by_symbol["TCS"]["basis"] == "unaffected"
    assert by_symbol["TCS"]["impact"] == 0.0


async def test_coal_event_propagates_to_ntpc(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "Coal Test", "kind": "long_term"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]
    await client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"symbol": "NTPC", "quantity": 100, "avg_price": 300.0},
        headers=auth_headers,
    )

    events = await client.get("/api/v1/events")
    coal_id = next(e for e in events.json() if "Coal supply" in e["headline"])["id"]

    impact = await client.get(
        f"/api/v1/events/{coal_id}/impact", params={"portfolio_id": portfolio_id}, headers=auth_headers
    )
    assert impact.status_code == 200
    body = impact.json()
    assert body["target"] == "coal"
    assert body["per_holding_impact"][0]["symbol"] == "NTPC"
    assert body["per_holding_impact"][0]["impact"] != 0.0


# ── Stress test with a graph-resolved target (not just events) ──────────


async def test_stress_test_tool_accepts_a_location_target(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "Stress Graph Test", "kind": "long_term"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]
    await client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"symbol": "RELIANCE", "quantity": 10, "avg_price": 2500.0},
        headers=auth_headers,
    )

    response = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/stress-test",
        json={"target": "Gujarat", "shock_pct": -20},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["per_holding_impact"][0]["basis"].startswith("indirect via knowledge graph")


# ── AI Terminal integration (mock provider) ─────────────────────────────


async def test_ai_chat_graph_exposure_intent(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "GraphAIP", "kind": "trading"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "who is exposed to Gujarat"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "get_graph_exposure"
    assert body["tool_calls"][0]["result"]["kind"] == "location"
