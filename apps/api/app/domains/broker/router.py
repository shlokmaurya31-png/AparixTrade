from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import EncryptionNotConfiguredError
from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.broker import service
from app.domains.broker.adapter import BrokerConnectError
from app.models.user import User
from app.schemas.broker import (
    BrokerOrderResultOut,
    BrokerPortfolioOut,
    BrokerStatusOut,
    ConnectRequest,
    LoginUrlOut,
    PlaceBrokerOrderRequest,
    SyncResultOut,
)

router = APIRouter(prefix="/broker", tags=["broker"])


def _status_out(connection) -> dict:
    settings = get_settings()
    if connection is None:
        return {
            "connected": False,
            "broker": None,
            "status": None,
            "broker_user_id": None,
            "connected_at": None,
            "last_synced_at": None,
            "live_trading_enabled": settings.broker_live_trading_enabled,
        }
    return {
        "connected": connection.status == "connected",
        "broker": connection.broker,
        "status": connection.status,
        "broker_user_id": connection.broker_user_id,
        "connected_at": connection.connected_at,
        "last_synced_at": connection.last_synced_at,
        "live_trading_enabled": settings.broker_live_trading_enabled,
    }


@router.get("/status", response_model=BrokerStatusOut)
async def get_status(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    connection = await service.get_status(db, current_user.id)
    return _status_out(connection)


@router.get("/login-url", response_model=LoginUrlOut)
async def login_url(current_user: User = Depends(get_current_user)) -> dict:
    try:
        url = service.get_login_url(current_user.id)
    except BrokerConnectError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"broker": service.get_broker_adapter().name, "login_url": url}


@router.post("/connect", response_model=BrokerStatusOut)
async def connect(
    payload: ConnectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        connection = await service.connect(db, current_user.id, request_token=payload.request_token)
    except EncryptionNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except BrokerConnectError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _status_out(connection)


@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    await service.disconnect(db, current_user.id)


@router.post("/sync", response_model=SyncResultOut)
async def sync(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    try:
        _portfolio, synced_count, skipped = await service.sync_holdings(db, current_user.id)
    except service.BrokerNotConnectedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except BrokerConnectError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return {"synced_holdings": synced_count, "skipped_symbols": skipped, "synced_at": datetime.now(timezone.utc)}


@router.get("/portfolio", response_model=BrokerPortfolioOut)
async def get_portfolio(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    portfolio = await service.get_or_create_broker_portfolio(db, current_user.id)
    holdings = await service.get_broker_holdings_view(db, portfolio)
    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "holdings": holdings,
        "total_value": round(sum(h["market_value"] for h in holdings), 2),
        "is_mock": service.get_broker_adapter().name == "mock",
    }


@router.post("/orders", response_model=BrokerOrderResultOut)
async def place_order(
    payload: PlaceBrokerOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await service.place_live_order(
            db, current_user.id, symbol=payload.symbol.upper(), side=payload.side, quantity=payload.quantity
        )
    except service.LiveTradingDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except service.BrokerNotConnectedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except BrokerConnectError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return {
        "broker_order_id": result.broker_order_id,
        "status": result.status,
        "fill_price": result.fill_price,
        "message": result.message,
    }
