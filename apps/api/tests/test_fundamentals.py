from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.domains.fundamentals.provider import MockFundamentalsProvider, generate_statements
from app.domains.fundamentals.service import (
    UnknownSymbolError,
    get_latest_statement_as_of,
    resolve_security,
)
from app.models.security import Security

# ── Provider ──────────────────────────────────────────────────────────────


def test_generate_statements_is_deterministic_for_the_same_symbol_and_price():
    import datetime

    today = datetime.date(2026, 9, 1)
    a = generate_statements("RELIANCE", today, 2950.0)
    b = generate_statements("RELIANCE", today, 2950.0)
    assert a == b


def test_generate_statements_covers_annual_and_quarterly_periods():
    import datetime

    rows = generate_statements("TCS", datetime.date(2026, 9, 1), 4150.0)
    annual = [r for r in rows if r["period_type"] == "annual"]
    quarterly = [r for r in rows if r["period_type"] == "quarterly"]
    assert len(annual) == 3
    assert len(quarterly) == 4


def test_generate_statements_effective_date_is_after_period_end():
    import datetime

    for row in generate_statements("INFY", datetime.date(2026, 9, 1), 1850.0):
        assert row["effective_date"] > row["period_end"]


def test_generate_statements_produce_a_plausible_pe_ratio_for_the_latest_year():
    # Regression test for a real bug: an earlier version generated revenue/PAT
    # independently of price and produced a P/E of ~1667 for a ~₹3000 stock.
    import datetime

    spot_price = 2950.0
    rows = generate_statements("RELIANCE", datetime.date(2026, 9, 1), spot_price)
    latest_annual = max((r for r in rows if r["period_type"] == "annual"), key=lambda r: r["period_end"])
    pe = spot_price / latest_annual["eps"]
    assert 10.0 <= pe <= 45.0, f"implausible P/E: {pe}"


def test_mock_provider_name():
    assert MockFundamentalsProvider().name == "mock"


# ── Service / seeding ────────────────────────────────────────────────────


async def test_seed_if_needed_populated_the_seeded_universe(client: AsyncClient):
    # app.main's lifespan already ran seed_if_needed by the time `client`
    # resolves — this asserts it actually did something, not just that it
    # didn't crash.
    async with AsyncSessionLocal() as db:
        security = (await db.execute(select(Security).where(Security.symbol == "RELIANCE"))).scalar_one()
        statement = await get_latest_statement_as_of(db, security.id, as_of=__import__("datetime").date.today())
    assert statement is not None
    assert statement.revenue > 0


async def test_resolve_security_raises_for_unknown_symbol(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        try:
            await resolve_security(db, "NOTASYMBOL")
            assert False, "expected UnknownSymbolError"
        except UnknownSymbolError:
            pass


# ── HTTP endpoints ───────────────────────────────────────────────────────


async def test_get_fundamentals_endpoint(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/fundamentals/RELIANCE", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "RELIANCE"
    assert body["revenue"] > 0
    assert body["provenance"]["source"] == "aparix-mock-fundamentals"


async def test_get_fundamentals_unknown_symbol_is_404(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/fundamentals/NOPE", headers=auth_headers)
    assert response.status_code == 404


async def test_get_fundamentals_history_endpoint(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/fundamentals/TCS/history", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3  # 3 annual periods
    assert [b["fiscal_year"] for b in body] == sorted(b["fiscal_year"] for b in body)


async def test_get_fundamentals_ratios_endpoint(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/fundamentals/INFY/ratios", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "INFY"
    assert body["roe_pct"] is not None
    assert body["price_used"] is not None


async def test_ratios_before_any_statement_exists_is_404(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/v1/fundamentals/RELIANCE/ratios", params={"as_of": "1999-01-01"}, headers=auth_headers
    )
    assert response.status_code == 404


# ── AI Terminal integration (mock provider) ─────────────────────────────


async def test_ai_chat_fundamentals_intent(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "FundP", "kind": "trading"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "what's RELIANCE's ROE and P/E ratio"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "get_fundamentals"
    assert body["tool_calls"][0]["result"]["symbol"] == "RELIANCE"
    assert "ratios" in body["tool_calls"][0]["result"]
