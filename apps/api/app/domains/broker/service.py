import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.domains.audit.service import log_action
from app.domains.broker.adapter import (
    BrokerAdapter,
    BrokerConnectError,
    BrokerCredentials,
    BrokerOrderResult,
    MockBrokerAdapter,
)
from app.domains.market_data.service import get_security_by_symbol
from app.domains.portfolios.service import get_holdings_with_quotes
from app.domains.portfolios.service import get_portfolio as get_portfolio_with_holdings
from app.models.broker import BrokerConnection
from app.models.portfolio import Holding, Portfolio


class BrokerNotConnectedError(Exception):
    pass


class LiveTradingDisabledError(Exception):
    pass


def get_broker_adapter() -> BrokerAdapter:
    # Deferred import, same reason as get_model_provider() in
    # domains/ai/provider.py: avoids importing httpx/zerodha_adapter at
    # module load for the (default) mock-only path.
    if get_settings().broker_provider == "zerodha":
        from app.domains.broker.zerodha_adapter import ZerodhaKiteAdapter

        return ZerodhaKiteAdapter()
    return MockBrokerAdapter()


async def _find_connection(db: AsyncSession, user_id: uuid.UUID, broker: str) -> BrokerConnection | None:
    result = await db.execute(
        select(BrokerConnection).where(BrokerConnection.user_id == user_id, BrokerConnection.broker == broker)
    )
    return result.scalar_one_or_none()


async def get_status(db: AsyncSession, user_id: uuid.UUID) -> BrokerConnection | None:
    adapter = get_broker_adapter()
    return await _find_connection(db, user_id, adapter.name)


def get_login_url(user_id: uuid.UUID) -> str:
    adapter = get_broker_adapter()
    settings = get_settings()
    api_key = settings.zerodha_api_key if adapter.name == "zerodha" else None
    return adapter.get_login_url(api_key=api_key)


async def connect(db: AsyncSession, user_id: uuid.UUID, *, request_token: str | None) -> BrokerConnection:
    adapter = get_broker_adapter()
    settings = get_settings()
    api_key = settings.zerodha_api_key if adapter.name == "zerodha" else None
    api_secret = settings.zerodha_api_secret if adapter.name == "zerodha" else None

    login_result = await adapter.complete_login(api_key=api_key, api_secret=api_secret, request_token=request_token)

    connection = await _find_connection(db, user_id, adapter.name)
    if connection is None:
        connection = BrokerConnection(user_id=user_id, broker=adapter.name)
        db.add(connection)

    connection.status = "connected"
    connection.encrypted_api_key = encrypt_secret(api_key) if api_key else None
    connection.encrypted_api_secret = encrypt_secret(api_secret) if api_secret else None
    connection.encrypted_access_token = encrypt_secret(login_result.access_token)
    connection.token_expires_at = login_result.expires_at
    connection.broker_user_id = login_result.broker_user_id
    connection.connected_at = datetime.now(timezone.utc)

    await log_action(db, user_id=user_id, action="broker.connect", input_data={"broker": adapter.name})
    await db.commit()
    await db.refresh(connection)
    return connection


async def disconnect(db: AsyncSession, user_id: uuid.UUID) -> None:
    adapter = get_broker_adapter()
    connection = await _find_connection(db, user_id, adapter.name)
    if connection is None:
        return
    # Deletes the row (and its encrypted credentials) outright rather than
    # flagging status="disconnected" — a revoked connection shouldn't leave
    # a decryptable access token sitting in the database.
    await db.delete(connection)
    await log_action(db, user_id=user_id, action="broker.disconnect", input_data={"broker": adapter.name})
    await db.commit()


def _credentials_from_connection(connection: BrokerConnection) -> BrokerCredentials:
    return BrokerCredentials(
        api_key=decrypt_secret(connection.encrypted_api_key) if connection.encrypted_api_key else None,
        api_secret=decrypt_secret(connection.encrypted_api_secret) if connection.encrypted_api_secret else None,
        access_token=decrypt_secret(connection.encrypted_access_token)
        if connection.encrypted_access_token
        else None,
    )


async def _find_broker_portfolio_id(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    result = await db.execute(
        select(Portfolio.id)
        .where(Portfolio.user_id == user_id, Portfolio.kind == "broker")
        .order_by(Portfolio.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_or_create_broker_portfolio(db: AsyncSession, user_id: uuid.UUID) -> Portfolio:
    existing_id = await _find_broker_portfolio_id(db, user_id)

    if existing_id is None:
        portfolio = Portfolio(user_id=user_id, name="Broker Account", kind="broker")
        db.add(portfolio)
        try:
            await log_action(db, user_id=user_id, action="broker.create_portfolio")
            await db.commit()
            existing_id = portfolio.id
        except IntegrityError:
            # Same race as get_or_create_paper_portfolio (domains/paper_trading)
            # — the DB-level unique index catches it, this re-reads the winner.
            await db.rollback()
            existing_id = await _find_broker_portfolio_id(db, user_id)

    return await get_portfolio_with_holdings(db, portfolio_id=existing_id, user_id=user_id)


async def sync_holdings(db: AsyncSession, user_id: uuid.UUID) -> tuple[Portfolio, int, list[str]]:
    adapter = get_broker_adapter()
    connection = await _find_connection(db, user_id, adapter.name)
    if connection is None or connection.status != "connected":
        raise BrokerNotConnectedError(f"No connected {adapter.name} broker account.")

    credentials = _credentials_from_connection(connection)
    try:
        broker_holdings = await adapter.get_holdings(credentials)
    except BrokerConnectError:
        connection.status = "expired"
        await db.commit()
        raise

    portfolio = await get_or_create_broker_portfolio(db, user_id)

    existing_by_security_id = {h.security_id: h for h in portfolio.holdings}
    seen_security_ids: set[uuid.UUID] = set()
    skipped_symbols: list[str] = []

    for bh in broker_holdings:
        security = await get_security_by_symbol(db, bh.symbol)
        if security is None:
            # A real broker account can legitimately hold instruments
            # outside this app's seeded NIFTY-subset universe — those
            # can't be priced/analyzed here, so they're reported as
            # skipped rather than silently dropped or fabricated a price
            # for. See docs/ARCHITECTURE.md Phase 5 trade-offs.
            skipped_symbols.append(bh.symbol)
            continue

        seen_security_ids.add(security.id)
        existing = existing_by_security_id.get(security.id)
        if existing is not None:
            existing.quantity = bh.quantity
            existing.avg_price = bh.avg_price
        else:
            db.add(Holding(portfolio_id=portfolio.id, security_id=security.id, quantity=bh.quantity, avg_price=bh.avg_price))

    # A broker portfolio must mirror the broker's truth exactly — a
    # position closed at the broker has to disappear here too, not linger
    # as a stale local row.
    for security_id, holding in existing_by_security_id.items():
        if security_id not in seen_security_ids:
            await db.delete(holding)

    connection.last_synced_at = datetime.now(timezone.utc)
    await log_action(
        db,
        user_id=user_id,
        action="broker.sync_holdings",
        input_data={"broker": adapter.name},
        output_data={"synced": len(seen_security_ids), "skipped": skipped_symbols},
    )
    await db.commit()

    portfolio = await get_or_create_broker_portfolio(db, user_id)
    return portfolio, len(seen_security_ids), skipped_symbols


async def get_broker_holdings_view(db: AsyncSession, portfolio: Portfolio) -> list[dict]:
    """Shared by the router and the AI tool — real quantity/avg_price from
    the broker sync, priced against this app's own simulated live market
    data (the only live pricing feed that exists here, not Zerodha's real
    quotes) — see docs/ARCHITECTURE.md Phase 5 trade-offs."""
    rows = await get_holdings_with_quotes(db, portfolio)
    return [
        {
            "symbol": r["security"].symbol,
            "name": r["security"].name,
            "sector": r["security"].sector,
            "quantity": r["metrics"].quantity,
            "avg_price": r["metrics"].avg_price,
            "last_price": r["metrics"].last_price,
            "market_value": r["metrics"].market_value,
            "unrealized_pnl": r["metrics"].unrealized_pnl,
            "unrealized_pnl_pct": r["metrics"].unrealized_pnl_pct,
        }
        for r in rows
    ]


async def place_live_order(
    db: AsyncSession, user_id: uuid.UUID, *, symbol: str, side: str, quantity: float
) -> BrokerOrderResult:
    settings = get_settings()
    if not settings.broker_live_trading_enabled:
        raise LiveTradingDisabledError(
            "Live broker trading is disabled (BROKER_LIVE_TRADING_ENABLED=false). "
            "This is a deliberate default, not a bug — see docs/ARCHITECTURE.md Phase 5 trade-offs."
        )

    adapter = get_broker_adapter()
    connection = await _find_connection(db, user_id, adapter.name)
    if connection is None or connection.status != "connected":
        raise BrokerNotConnectedError(f"No connected {adapter.name} broker account.")

    credentials = _credentials_from_connection(connection)
    result = await adapter.place_order(credentials, symbol=symbol.upper(), side=side, quantity=quantity)

    # Deliberately does NOT touch local Holding rows — Kite order execution
    # is asynchronous (see zerodha_adapter.py), so the real fill isn't known
    # yet. The next explicit "Sync holdings" call is what reflects it,
    # rather than this guessing a fill price.
    await log_action(
        db,
        user_id=user_id,
        action="broker.place_live_order",
        input_data={"broker": adapter.name, "symbol": symbol, "side": side, "quantity": quantity},
        output_data={"broker_order_id": result.broker_order_id, "status": result.status},
        result=result.status,
    )
    await db.commit()
    return result
