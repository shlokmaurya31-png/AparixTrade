"""Tier 1 §49 — the deferred point-in-time / no-look-ahead-bias suite from
Session 1, now buildable now that domains/fundamentals exists.

The rule under test: a query "as of" a date must never return a financial
statement whose effective_date is after that date — even if the
statement's period_end has already passed. See
domains/fundamentals/service.py's module docstring.
"""

import datetime
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.domains.fundamentals.service import (
    get_latest_statement_as_of,
    get_point_in_time_price,
    list_statements_as_of,
)
from app.models.fundamentals import FinancialStatement
from app.models.security import Candle, Security

# FY2024: period ended 2024-03-31, announced 2024-05-20.
# FY2025: period ended 2025-03-31, announced 2025-05-20.
# The gap between 2025-03-31 and 2025-05-20 is the exact leak window: the
# period has ended, but the results aren't public yet.
FY2024_PERIOD_END = datetime.date(2024, 3, 31)
FY2024_ANNOUNCED = datetime.date(2024, 5, 20)
FY2025_PERIOD_END = datetime.date(2025, 3, 31)
FY2025_ANNOUNCED = datetime.date(2025, 5, 20)


async def _seed_two_year_history(db) -> Security:
    # A dedicated, test-only security — not one of the seeded universe's
    # ~20 names, which already have their own auto-generated fundamentals
    # from app.main's startup seeding (same fiscal years, same unique
    # index) and would collide with these hand-picked fixture rows.
    security = Security(
        symbol=f"PIT{uuid.uuid4().hex[:8].upper()}",
        name="Point-in-Time Test Co",
        sector="Testing",
        is_index=False,
        is_mock=True,
    )
    db.add(security)
    await db.flush()

    def _row(period_end, announced, fiscal_year, pat):
        return FinancialStatement(
            security_id=security.id,
            period_end=period_end,
            period_type="annual",
            fiscal_year=fiscal_year,
            announcement_date=announced,
            effective_date=announced,
            currency="INR",
            unit="crore",
            shares_outstanding=100.0,
            is_mock=True,
            revenue=1000.0 + fiscal_year,  # distinguishable per row
            gross_profit=500.0,
            ebitda=300.0,
            ebit=250.0,
            pbt=200.0,
            pat=pat,
            eps=pat / 100.0,
            total_assets=2000.0,
            total_liabilities=800.0,
            total_equity=1200.0,
            cash_and_equivalents=100.0,
            total_debt=500.0,
            current_assets=600.0,
            current_liabilities=300.0,
            interest_expense=50.0,
            cfo=250.0,
            cfi=-100.0,
            cff=-50.0,
            free_cash_flow=150.0,
        )

    fy2024 = _row(FY2024_PERIOD_END, FY2024_ANNOUNCED, 2024, pat=180.0)
    fy2025 = _row(FY2025_PERIOD_END, FY2025_ANNOUNCED, 2025, pat=220.0)
    db.add_all([fy2024, fy2025])
    await db.commit()
    return security


async def test_query_before_any_statement_announced_returns_none(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        security = await _seed_two_year_history(db)
        result = await get_latest_statement_as_of(db, security.id, as_of=datetime.date(2024, 1, 1))
    assert result is None


async def test_query_after_fy2024_but_before_fy2025_returns_only_fy2024(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        security = await _seed_two_year_history(db)
        result = await get_latest_statement_as_of(db, security.id, as_of=datetime.date(2024, 6, 1))
    assert result is not None
    assert result.fiscal_year == 2024


async def test_the_leak_scenario_period_ended_but_not_yet_announced(client: AsyncClient):
    """The scenario the spec explicitly calls out: FY2025's period_end
    (2025-03-31) has passed by 2025-04-15, but it wasn't announced until
    2025-05-20. A query as of 2025-04-15 MUST still resolve to FY2024 — a
    naive `period_end <= as_of` implementation would wrongly return FY2025
    here, since 2025-03-31 <= 2025-04-15."""
    as_of = datetime.date(2025, 4, 15)
    assert FY2025_PERIOD_END <= as_of < FY2025_ANNOUNCED  # sanity-check the fixture itself sits in the gap

    async with AsyncSessionLocal() as db:
        security = await _seed_two_year_history(db)
        result = await get_latest_statement_as_of(db, security.id, as_of=as_of)

    assert result is not None
    assert result.fiscal_year == 2024, (
        "Point-in-time query leaked an unannounced future statement — "
        f"got FY{result.fiscal_year}, expected FY2024"
    )


async def test_query_after_fy2025_announced_returns_fy2025(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        security = await _seed_two_year_history(db)
        result = await get_latest_statement_as_of(db, security.id, as_of=datetime.date(2025, 6, 1))
    assert result is not None
    assert result.fiscal_year == 2025


async def test_list_statements_as_of_also_respects_the_point_in_time_boundary(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        security = await _seed_two_year_history(db)
        mid_gap = await list_statements_as_of(db, security.id, as_of=datetime.date(2025, 4, 15))
        after_both = await list_statements_as_of(db, security.id, as_of=datetime.date(2025, 6, 1))

    assert [s.fiscal_year for s in mid_gap] == [2024]
    assert [s.fiscal_year for s in after_both] == [2024, 2025]


async def test_http_endpoint_respects_the_leak_scenario(client: AsyncClient, auth_headers: dict):
    async with AsyncSessionLocal() as db:
        security = await _seed_two_year_history(db)
        symbol = security.symbol

    response = await client.get(
        f"/api/v1/fundamentals/{symbol}",
        params={"as_of": "2025-04-15"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["fiscal_year"] == 2024


async def test_point_in_time_price_uses_historical_close_not_live_spot(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        security = (await db.execute(select(Security).limit(1))).scalars().first()
        # Insert a distinctive historical candle far in the past, price-wise
        # unmistakably different from anything the live mock generator would
        # currently be quoting.
        past_date = datetime.date(2020, 1, 2)
        db.add(
            Candle(
                security_id=security.id,
                trade_date=past_date,
                open=1.23,
                high=1.25,
                low=1.20,
                close=1.23,
                volume=1000,
                is_mock=True,
            )
        )
        await db.commit()

        price = await get_point_in_time_price(db, security, as_of=past_date)

    assert price == 1.23


async def test_point_in_time_price_with_no_history_before_as_of_returns_none(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        security = (await db.execute(select(Security).limit(1))).scalars().first()
        price = await get_point_in_time_price(db, security, as_of=datetime.date(1990, 1, 1))
    assert price is None
