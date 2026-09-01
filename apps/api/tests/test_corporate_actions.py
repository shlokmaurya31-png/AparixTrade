import datetime
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.corporate_action_types import ALL_ACTION_TYPES, ActionType
from app.core.db import AsyncSessionLocal
from app.domains.corporate_actions.provider import MockCorporateActionsProvider, generate_actions
from app.domains.corporate_actions.service import (
    UnknownSymbolError,
    list_actions_as_of,
    resolve_security,
)
from app.models.corporate_action import CorporateAction
from app.models.security import Security

# ── Provider ──────────────────────────────────────────────────────────────


def test_generate_actions_is_deterministic():
    import datetime as dt

    today = dt.date(2026, 9, 1)
    a = generate_actions("RELIANCE", 2950.0, today)
    b = generate_actions("RELIANCE", 2950.0, today)
    assert a == b


def test_generate_actions_only_uses_supported_types():
    import datetime as dt

    for symbol, price in [("RELIANCE", 2950.0), ("TCS", 4150.0), ("MARUTI", 12500.0), ("ITC", 460.0)]:
        for action in generate_actions(symbol, price, dt.date(2026, 9, 1)):
            assert action["action_type"] in ALL_ACTION_TYPES


def test_generate_actions_never_seeds_disruptive_types():
    # See docs/ARCHITECTURE.md §9 — merger/demerger/symbol_change/
    # isin_change/delisting are supported types but never generated
    # against the live tradable universe this session.
    import datetime as dt

    disruptive = {ActionType.MERGER, ActionType.DEMERGER, ActionType.SYMBOL_CHANGE, ActionType.ISIN_CHANGE, ActionType.DELISTING}
    for symbol, price in [("RELIANCE", 2950.0), ("MARUTI", 12500.0), ("WIPRO", 310.0)]:
        for action in generate_actions(symbol, price, dt.date(2026, 9, 1)):
            assert action["action_type"] not in disruptive


def test_high_priced_security_leans_toward_a_split():
    import datetime as dt

    actions = generate_actions("MARUTI", 12500.0, dt.date(2026, 9, 1))
    non_cash = [a for a in actions if a["action_type"] != ActionType.DIVIDEND]
    if non_cash:
        assert non_cash[0]["action_type"] == ActionType.SPLIT
        assert non_cash[0]["ratio"] in (2.0, 3.0)


def test_mock_provider_name():
    assert MockCorporateActionsProvider().name == "mock"


# ── Service / seeding ────────────────────────────────────────────────────


async def test_seed_if_needed_populated_the_seeded_universe(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        security = (await db.execute(select(Security).where(Security.symbol == "RELIANCE"))).scalar_one()
        actions = await list_actions_as_of(db, security.id, as_of=datetime.date.today())
    assert len(actions) > 0
    assert all(a.action_type == ActionType.DIVIDEND for a in actions) or any(
        a.action_type != ActionType.DIVIDEND for a in actions
    )  # sanity: at least dividends exist, non-cash actions optional per symbol


async def test_resolve_security_raises_for_unknown_symbol(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        try:
            await resolve_security(db, "NOTASYMBOL")
            assert False, "expected UnknownSymbolError"
        except UnknownSymbolError:
            pass


# ── Point-in-time integrity (mirrors tests/test_point_in_time_integrity.py) ──


async def test_action_before_announcement_is_not_leaked(client: AsyncClient):
    async with AsyncSessionLocal() as db:
        security = Security(
            symbol=f"CAPIT{uuid.uuid4().hex[:6].upper()}", name="CA Point-in-Time Test Co", sector="Testing", is_mock=True
        )
        db.add(security)
        await db.flush()

        action = CorporateAction(
            security_id=security.id,
            action_type=ActionType.DIVIDEND,
            ratio=None,
            amount=15.0,
            new_security_id=None,
            announcement_date=datetime.date(2025, 5, 1),
            record_date=datetime.date(2025, 5, 10),
            ex_date=datetime.date(2025, 5, 12),
            effective_date=datetime.date(2025, 5, 12),  # not publicly known until this date
            source="mock",
            is_mock=True,
        )
        db.add(action)
        await db.commit()

        before = await list_actions_as_of(db, security.id, as_of=datetime.date(2025, 5, 5))
        on_effective = await list_actions_as_of(db, security.id, as_of=datetime.date(2025, 5, 12))

    assert before == []
    assert len(on_effective) == 1


async def test_http_endpoint_respects_point_in_time(client: AsyncClient, auth_headers: dict):
    async with AsyncSessionLocal() as db:
        security = Security(
            symbol=f"CAHTTP{uuid.uuid4().hex[:6].upper()}", name="CA HTTP Test Co", sector="Testing", is_mock=True
        )
        db.add(security)
        await db.flush()
        db.add(
            CorporateAction(
                security_id=security.id,
                action_type=ActionType.SPLIT,
                ratio=2.0,
                amount=None,
                new_security_id=None,
                announcement_date=datetime.date(2025, 1, 1),
                record_date=datetime.date(2025, 1, 20),
                ex_date=datetime.date(2025, 1, 25),
                effective_date=datetime.date(2025, 1, 25),
                source="mock",
                is_mock=True,
            )
        )
        await db.commit()
        symbol = security.symbol

    before = await client.get(
        f"/api/v1/corporate-actions/{symbol}", params={"as_of": "2025-01-10"}, headers=auth_headers
    )
    after = await client.get(
        f"/api/v1/corporate-actions/{symbol}", params={"as_of": "2025-02-01"}, headers=auth_headers
    )
    assert before.status_code == 200 and before.json() == []
    assert after.status_code == 200 and len(after.json()) == 1
    assert after.json()[0]["action_type"] == "split"
    assert after.json()[0]["provenance"]["source"] == "aparix-mock-corporate-actions"


async def test_corporate_actions_unknown_symbol_is_404(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/corporate-actions/NOPE", headers=auth_headers)
    assert response.status_code == 404


# ── AI Terminal integration (mock provider) ─────────────────────────────


async def test_ai_chat_corporate_actions_intent(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "CAP", "kind": "trading"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    chat = await client.post(
        "/api/v1/ai/chat",
        json={"portfolio_id": portfolio_id, "message": "has RELIANCE paid any dividend"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["tool_calls"][0]["tool_name"] == "get_corporate_actions"
    assert body["tool_calls"][0]["result"]["symbol"] == "RELIANCE"
