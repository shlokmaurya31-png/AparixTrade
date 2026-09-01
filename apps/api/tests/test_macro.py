from httpx import AsyncClient

from app.domains.macro.seed_data import SEED_INDICATORS


async def test_macro_indicators_are_seeded_and_reachable(client: AsyncClient):
    response = await client.get("/api/v1/macro/indicators")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == len(SEED_INDICATORS)

    gsec = next(i for i in body if i["code"] == "gsec_10y")
    assert gsec["value"] == 6.5
    assert gsec["is_mock"] is True


async def test_risk_profile_risk_free_rate_matches_macro_gsec(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "Macro Test", "kind": "long_term"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    risk = await client.get(f"/api/v1/portfolios/{portfolio_id}/risk", headers=auth_headers)
    assert risk.status_code == 200
    # No holdings yet, but the rate itself should already reflect the macro
    # indicator, not the bare fallback constant diverging from it.
    assert risk.json()["risk_free_rate_annual_pct"] == 6.5
