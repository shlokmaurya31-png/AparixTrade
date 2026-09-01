import datetime

from httpx import AsyncClient

from app.core.db import AsyncSessionLocal
from app.domains.macro.service import get_latest_known_reading_as_of, get_releases_as_of

# ── Seeding / service ────────────────────────────────────────────────────


async def test_seed_populated_cpi_vintage_history(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        releases = await get_releases_as_of(db, "cpi_inflation", as_of=datetime.date.today())
    assert len(releases) > 0
    assert any(r.revision_number > 0 for r in releases)


async def test_non_revised_indicators_have_no_vintage_history(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        releases = await get_releases_as_of(db, "repo_rate", as_of=datetime.date.today())
    assert releases == []


async def test_point_in_time_history_never_leaks_a_future_release(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        far_past = await get_releases_as_of(db, "cpi_inflation", as_of=datetime.date(2000, 1, 1))
    assert far_past == []


async def test_latest_known_reading_never_uses_a_later_revision(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        all_releases = await get_releases_as_of(db, "cpi_inflation", as_of=datetime.date.today())
        # Pick a release_date partway through the history and confirm the
        # "latest known" resolver never returns anything published after it.
        mid_release_date = sorted({r.release_date for r in all_releases})[len(all_releases) // 2]
        latest_as_of_mid = await get_latest_known_reading_as_of(db, "cpi_inflation", as_of=mid_release_date)

    assert latest_as_of_mid is not None
    assert latest_as_of_mid.release_date <= mid_release_date


# ── HTTP endpoint ────────────────────────────────────────────────────────


async def test_get_indicator_history_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/macro/indicators/cpi_inflation/history")
    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    assert body[0]["provenance"]["source"] == "aparix-mock-macro-vintage"


async def test_get_indicator_history_endpoint_404_for_non_revised_indicator(client: AsyncClient):
    response = await client.get("/api/v1/macro/indicators/repo_rate/history")
    assert response.status_code == 404


async def test_get_indicator_history_endpoint_respects_as_of(client: AsyncClient):
    response = await client.get(
        "/api/v1/macro/indicators/cpi_inflation/history", params={"as_of": "2000-01-01"}
    )
    assert response.status_code == 404  # nothing was published that far back


# ── AI Terminal integration (mock provider) ─────────────────────────────


async def test_ai_chat_macro_history_intent(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "MacroP", "kind": "trading"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "has CPI inflation been revised recently"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "get_macro_history"
    assert body["tool_calls"][0]["result"]["code"] == "cpi_inflation"
