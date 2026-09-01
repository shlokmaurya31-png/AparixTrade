from httpx import AsyncClient

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.domains.macro.provider import MockMacroDataProvider, get_macro_provider
from app.domains.macro.seed_data import SEED_INDICATORS
from app.domains.macro.service import get_indicator, list_indicators


async def test_get_macro_provider_returns_mock_by_default(client: AsyncClient):
    assert get_settings().macro_provider == "mock"
    provider = get_macro_provider()
    assert isinstance(provider, MockMacroDataProvider)
    assert provider.name == "mock"


async def test_provider_get_latest_matches_seed_data(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        indicators = await MockMacroDataProvider().get_latest(db)
    assert {i.code for i in indicators} == {code for code, *_ in SEED_INDICATORS}


async def test_service_layer_is_a_thin_pass_through_to_the_provider(client: AsyncClient):
    # Refactor guarantee: domains/macro/service.py now calls through
    # provider.py, but must return the exact same data as before.
    async with AsyncSessionLocal() as db:
        via_service = await list_indicators(db)
        via_provider = await MockMacroDataProvider().get_latest(db)
    assert [i.code for i in via_service] == [i.code for i in via_provider]


async def test_get_indicator_still_resolves_a_single_code(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        indicator = await get_indicator(db, "gsec_10y")
    assert indicator is not None
    assert indicator.code == "gsec_10y"


async def test_get_series_returns_the_single_available_point_not_a_fabricated_history(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        series = await MockMacroDataProvider().get_series(db, "gsec_10y")
    assert len(series) == 1  # no vintage/time-series tracking yet — see docs/APARIX_TIER1_AUDIT.md
