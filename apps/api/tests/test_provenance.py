from httpx import AsyncClient


async def test_market_quote_carries_provenance(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/market/quotes/RELIANCE", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["provenance"]["source"] == "aparix-mock-market-data"
    assert body["provenance"]["provider"] == "MockMarketDataProvider"
    assert body["provenance"]["quality"] in ("good", "stale")
    assert body["provenance"]["retrieved_at"] is not None
    assert body["provenance"]["source_timestamp"] is not None


async def test_all_quotes_each_carry_provenance(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/market/quotes", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    assert all("provenance" in q for q in body)


async def test_macro_indicator_carries_provenance(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/macro/indicators", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    for indicator in body:
        assert indicator["provenance"]["source"] == "aparix-mock-macro-data"
        assert indicator["provenance"]["provider"] == "mock"
        assert indicator["provenance"]["quality"] == "good"
