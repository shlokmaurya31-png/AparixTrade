import datetime

from httpx import AsyncClient

from app.core.db import AsyncSessionLocal
from app.domains.market_data.historical_seed_data import DELISTED_SECURITY, MERGED_SECURITY
from app.domains.market_data.service import (
    get_security_by_symbol,
    list_securities,
    list_securities_as_of,
)

DELISTED_SYMBOL = DELISTED_SECURITY[0]
DELISTED_LISTED_DATE = DELISTED_SECURITY[4]
DELISTED_DATE = DELISTED_SECURITY[5]
MERGED_SYMBOL = MERGED_SECURITY[0]
MERGED_DATE = MERGED_SECURITY[5]

# ── Seeding ──────────────────────────────────────────────────────────────


async def test_historical_securities_are_seeded(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        delisted = await get_security_by_symbol(db, DELISTED_SYMBOL)
        merged = await get_security_by_symbol(db, MERGED_SYMBOL)
    assert delisted is not None
    assert delisted.is_tradable is False
    assert delisted.delisted_date == DELISTED_DATE
    assert merged is not None
    assert merged.is_tradable is False
    assert merged.delisted_date == MERGED_DATE


async def test_historical_securities_have_candle_history_ending_at_delisting(client: AsyncClient):
    from sqlalchemy import select

    from app.models.security import Candle

    async with AsyncSessionLocal() as db:
        security = await get_security_by_symbol(db, DELISTED_SYMBOL)
        result = await db.execute(
            select(Candle).where(Candle.security_id == security.id).order_by(Candle.trade_date.desc()).limit(1)
        )
        latest_candle = result.scalar_one()
    assert latest_candle.trade_date < DELISTED_DATE


async def test_delisted_security_has_exactly_one_corporate_action(client: AsyncClient, auth_headers: dict):
    response = await client.get(f"/api/v1/corporate-actions/{DELISTED_SYMBOL}", headers=auth_headers)
    assert response.status_code == 200
    actions = response.json()
    assert len(actions) == 1
    assert actions[0]["action_type"] == "delisting"


async def test_merged_security_has_a_merger_action_pointing_at_the_target(client: AsyncClient):
    from app.domains.corporate_actions.service import list_actions_as_of

    async with AsyncSessionLocal() as db:
        merged = await get_security_by_symbol(db, MERGED_SYMBOL)
        target = await get_security_by_symbol(db, "HDFCBANK")
        actions = await list_actions_as_of(db, merged.id, as_of=datetime.date.today())
    assert len(actions) == 1
    assert actions[0].action_type == "merger"
    assert actions[0].new_security_id == target.id


async def test_historical_securities_have_no_fundamentals(client: AsyncClient, auth_headers: dict):
    response = await client.get(f"/api/v1/fundamentals/{DELISTED_SYMBOL}", headers=auth_headers)
    assert response.status_code == 404


# ── Live universe exclusion (never disrupts the tradable universe) ──────


async def test_live_universe_excludes_historical_securities(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        securities = await list_securities(db)
    symbols = {s.symbol for s in securities}
    assert DELISTED_SYMBOL not in symbols
    assert MERGED_SYMBOL not in symbols


async def test_include_delisted_flag_shows_them(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        securities = await list_securities(db, include_delisted=True)
    symbols = {s.symbol for s in securities}
    assert DELISTED_SYMBOL in symbols
    assert MERGED_SYMBOL in symbols


async def test_get_securities_endpoint_excludes_historical_securities(client: AsyncClient):
    response = await client.get("/api/v1/market/securities")
    assert response.status_code == 200
    symbols = {s["symbol"] for s in response.json()}
    assert DELISTED_SYMBOL not in symbols


async def test_cannot_place_a_paper_order_against_a_delisted_security(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/paper/portfolio/orders",
        json={"symbol": DELISTED_SYMBOL, "side": "buy", "quantity": 1},
        headers=auth_headers,
    )
    assert response.status_code == 404


# ── Point-in-time universe query — the actual survivorship-bias fix ─────


async def test_universe_as_of_before_delisting_includes_the_security(client: AsyncClient):
    just_before = DELISTED_DATE - datetime.timedelta(days=1)
    async with AsyncSessionLocal() as db:
        universe = await list_securities_as_of(db, just_before)
    assert DELISTED_SYMBOL in {s.symbol for s in universe}


async def test_universe_as_of_after_delisting_excludes_the_security(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        universe = await list_securities_as_of(db, datetime.date.today())
    assert DELISTED_SYMBOL not in {s.symbol for s in universe}


async def test_universe_as_of_before_listing_excludes_the_security(client: AsyncClient):
    listed_date = DELISTED_SECURITY[4]
    before_listing = listed_date - datetime.timedelta(days=1)
    async with AsyncSessionLocal() as db:
        universe = await list_securities_as_of(db, before_listing)
    assert DELISTED_SYMBOL not in {s.symbol for s in universe}


async def test_universe_as_of_never_excludes_a_security_with_no_known_listing_dates(client: AsyncClient):
    """Regular seeded securities (RELIANCE etc.) have null listed/delisted
    dates — meaning "no known constraint," not a false claim of always
    having existed. A far-past or far-future as_of must still include
    them, since there is no real basis to exclude them at any date."""
    async with AsyncSessionLocal() as db:
        far_past = await list_securities_as_of(db, datetime.date(2000, 1, 1))
        far_future = await list_securities_as_of(db, datetime.date(2099, 1, 1))
    assert "RELIANCE" in {s.symbol for s in far_past}
    assert "RELIANCE" in {s.symbol for s in far_future}


async def test_universe_as_of_http_endpoint(client: AsyncClient):
    just_before = (DELISTED_DATE - datetime.timedelta(days=1)).isoformat()
    just_after = DELISTED_DATE.isoformat()

    before_response = await client.get("/api/v1/market/securities/universe", params={"as_of": just_before})
    after_response = await client.get("/api/v1/market/securities/universe", params={"as_of": just_after})

    assert before_response.status_code == 200
    assert after_response.status_code == 200
    assert DELISTED_SYMBOL in {s["symbol"] for s in before_response.json()}
    assert DELISTED_SYMBOL not in {s["symbol"] for s in after_response.json()}


async def test_universe_as_of_defaults_to_today(client: AsyncClient):
    response = await client.get("/api/v1/market/securities/universe")
    assert response.status_code == 200
    assert DELISTED_SYMBOL not in {s["symbol"] for s in response.json()}
