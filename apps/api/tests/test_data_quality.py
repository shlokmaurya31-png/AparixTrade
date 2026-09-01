import uuid
from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.db import AsyncSessionLocal
from app.domains.admin.data_quality import (
    check_candle_integrity,
    check_macro_coverage,
    check_market_data_freshness,
)
from app.domains.market_data.service import live_market_state
from app.models.macro import MacroIndicator
from app.models.security import Candle, Security

# Each check here is exercised both in its default (GOOD) state and after
# manufacturing a real defect — a check that can only ever report GOOD
# isn't actually testing anything (see docs/APARIX_TIER1_AUDIT.md §8).


async def test_market_data_freshness_is_good_right_after_startup(client: AsyncClient):
    findings = check_market_data_freshness()
    assert any(f.check == "market_data_freshness" and f.status == "GOOD" for f in findings)


async def test_market_data_freshness_flags_a_manufactured_stale_quote(client: AsyncClient):
    symbol = next(iter(live_market_state._prices))
    original = live_market_state._updated_at[symbol]
    live_market_state._updated_at[symbol] = datetime.now(timezone.utc) - timedelta(hours=1)
    try:
        findings = check_market_data_freshness()
        assert any(f.check == "market_data_freshness" and f.status == "STALE" for f in findings)
    finally:
        live_market_state._updated_at[symbol] = original


async def test_candle_integrity_is_good_for_seeded_mock_data(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        findings = await check_candle_integrity(db)
    assert any(f.check == "candle_integrity" and f.status == "GOOD" for f in findings)


async def test_candle_integrity_flags_a_manufactured_negative_price(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        security = (await db.execute(select(Security).limit(1))).scalars().first()
        bad_candle = Candle(
            security_id=security.id,
            trade_date=datetime.now(timezone.utc).date(),
            open=-10.0,
            high=5.0,
            low=1.0,
            close=2.0,
            volume=1000,
            is_mock=True,
        )
        db.add(bad_candle)
        await db.commit()
        bad_id = bad_candle.id

        findings = await check_candle_integrity(db)
        assert any(f.check == "candle_integrity" and f.status == "INVALID" for f in findings)

        await db.execute(delete(Candle).where(Candle.id == bad_id))
        await db.commit()


async def test_macro_coverage_is_good_by_default(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        findings = await check_macro_coverage(db)
    assert any(f.check == "macro_coverage" and f.status == "GOOD" for f in findings)


async def test_macro_coverage_flags_a_manufactured_missing_indicator(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        removed = (await db.execute(select(MacroIndicator).where(MacroIndicator.code == "repo_rate"))).scalar_one()
        await db.delete(removed)
        await db.commit()

        findings = await check_macro_coverage(db)
        assert any(f.check == "macro_coverage" and f.status == "WARNING" and "repo_rate" in f.detail for f in findings)

        db.add(MacroIndicator(code="repo_rate", name=removed.name, value=removed.value, unit=removed.unit, is_mock=True))
        await db.commit()


async def test_admin_data_quality_route_requires_admin(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/admin/data-quality", headers=auth_headers)
    assert response.status_code == 403


async def test_admin_data_quality_route_returns_real_findings(client: AsyncClient, monkeypatch):
    from app.core import config

    admin_email = f"dq-admin-{uuid.uuid4().hex}@example.com"
    monkeypatch.setenv("ADMIN_EMAILS", admin_email)
    config.get_settings.cache_clear()
    try:
        register = await client.post(
            "/api/v1/auth/register",
            json={"email": admin_email, "password": "correct-horse-battery", "full_name": "DQ Admin"},
        )
        headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

        response = await client.get("/api/v1/admin/data-quality", headers=headers)
        assert response.status_code == 200
        body = response.json()
        checks = {f["check"] for f in body}
        assert checks == {"market_data_freshness", "candle_integrity", "macro_coverage"}
    finally:
        config.get_settings.cache_clear()
