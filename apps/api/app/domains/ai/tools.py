"""AI tool registry.

Every tool here returns real, computed data — never a value invented by a
model. AI responses are only allowed to cite numbers that came out of one of
these calls, and each call is persisted as an AIToolCall row so any claim in
a chat message is traceable back to its source. This is the structural
guardrail against hallucinated financial figures (see docs/ARCHITECTURE.md §7-8).
"""

import uuid
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.events import service as events_service
from app.domains.macro.service import list_indicators
from app.domains.market_data.service import get_security_by_symbol, live_market_state
from app.domains.paper_trading import service as paper_trading_service
from app.domains.portfolios.service import compute_portfolio_analytics, get_holdings_with_quotes
from app.domains.risk.service import compute_risk_profile
from app.domains.simulation import service as simulation_service
from app.models.portfolio import Portfolio

ToolFunc = Callable[..., Awaitable[dict[str, Any]]]


async def get_portfolio_tool(db: AsyncSession, portfolio: Portfolio, **_: Any) -> dict:
    return await compute_portfolio_analytics(db, portfolio)


async def get_holdings_tool(db: AsyncSession, portfolio: Portfolio, **_: Any) -> dict:
    rows = await get_holdings_with_quotes(db, portfolio)
    return {
        "holdings": [
            {
                "symbol": r["security"].symbol,
                "sector": r["security"].sector,
                "market_value": r["metrics"].market_value,
                "unrealized_pnl": r["metrics"].unrealized_pnl,
                "day_pnl": r["metrics"].day_pnl,
            }
            for r in rows
        ]
    }


async def get_sector_exposure_tool(db: AsyncSession, portfolio: Portfolio, **_: Any) -> dict:
    analytics = await compute_portfolio_analytics(db, portfolio)
    return {"sector_exposure": analytics["sector_exposure"]}


async def get_market_data_tool(db: AsyncSession, portfolio: Portfolio, symbol: str = "NIFTY50", **_: Any) -> dict:
    security = await get_security_by_symbol(db, symbol)
    if security is None:
        return {"error": f"unknown symbol: {symbol}"}
    quote = live_market_state.get_quote(security.symbol)
    return {"quote": quote}


async def get_risk_profile_tool(db: AsyncSession, portfolio: Portfolio, **_: Any) -> dict:
    return await compute_risk_profile(db, portfolio)


async def run_stress_test_tool(
    db: AsyncSession, portfolio: Portfolio, target: str = "NIFTY50", shock_pct: float = -15.0, **_: Any
) -> dict:
    try:
        return await simulation_service.run_stress_test(db, portfolio, target=target, shock_pct=shock_pct)
    except simulation_service.InsufficientHistoryError as exc:
        return {"error": str(exc)}


async def run_monte_carlo_tool(
    db: AsyncSession, portfolio: Portfolio, method: str = "bootstrap", horizon_days: int = 30, **_: Any
) -> dict:
    try:
        return await simulation_service.run_monte_carlo(
            db, portfolio, method=method, horizon_days=horizon_days, num_paths=1000
        )
    except simulation_service.InsufficientHistoryError as exc:
        return {"error": str(exc)}


async def run_backtest_tool(db: AsyncSession, portfolio: Portfolio, **_: Any) -> dict:
    # persist=False: an AI-triggered question shouldn't silently clutter the
    # user's saved backtest-run history — only explicit runs from /portfolio
    # (or wherever a "run backtest" action lives) are saved.
    try:
        return await simulation_service.run_backtest(db, portfolio, initial_value=100_000.0, persist=False)
    except simulation_service.InsufficientHistoryError as exc:
        return {"error": str(exc)}


async def get_events_tool(db: AsyncSession, portfolio: Portfolio, limit: int = 5, **_: Any) -> dict:
    events = await events_service.list_events(db, limit=limit)
    return {
        "events": [
            {
                "id": str(e.id),
                "headline": e.headline,
                "event_type": e.event_type,
                "severity": e.severity,
                "direction": e.direction,
                "primary_target": e.primary_target,
                "published_at": e.published_at.isoformat(),
            }
            for e in events
        ]
    }


async def get_event_impact_tool(db: AsyncSession, portfolio: Portfolio, event_id: str | None = None, **_: Any) -> dict:
    # No event_id parsed out of free text yet (the router is keyword-based,
    # not a real LLM) — defaults to the most recent medium/high-severity
    # event, same pattern as run_stress_test_tool's NIFTY50 -15% default.
    event = None
    if event_id:
        try:
            event = await events_service.get_event(db, uuid.UUID(event_id))
        except ValueError:
            event = None
    if event is None:
        event = await events_service.get_most_recent_significant_event(db)
    if event is None:
        return {"error": "No events available."}

    try:
        return await events_service.compute_impact_for_portfolio(db, event, portfolio)
    except events_service.NoHoldingsError as exc:
        return {"error": str(exc)}


async def get_macro_indicators_tool(db: AsyncSession, portfolio: Portfolio, **_: Any) -> dict:
    indicators = await list_indicators(db)
    return {"indicators": [{"code": i.code, "name": i.name, "value": i.value, "unit": i.unit} for i in indicators]}


async def preview_trade_tool(
    db: AsyncSession, portfolio: Portfolio, symbol: str = "RELIANCE", side: str = "buy", quantity: float = 1, **_: Any
) -> dict:
    # Ignores which portfolio the AI Terminal session is currently on and
    # previews against the user's paper trading account specifically —
    # that's the only account real buy/sell execution happens against in
    # this app. `portfolio.user_id` resolves it regardless of which
    # portfolio is active.
    paper_portfolio = await paper_trading_service.get_or_create_paper_portfolio(db, portfolio.user_id)
    try:
        return await paper_trading_service.preview_trade(
            db, paper_portfolio, symbol=symbol, side=side, quantity=quantity
        )
    except paper_trading_service.UnknownSymbolError as exc:
        return {"error": f"unknown symbol: {exc}"}


async def evaluate_order_tool(db: AsyncSession, portfolio: Portfolio, order_id: str | None = None, **_: Any) -> dict:
    paper_portfolio = await paper_trading_service.get_or_create_paper_portfolio(db, portfolio.user_id)
    order = None
    if order_id:
        try:
            order = await paper_trading_service.get_order(db, uuid.UUID(order_id), paper_portfolio.id)
        except ValueError:
            order = None
    if order is None:
        # No order_id parsed from free text (keyword router) or not given —
        # default to the most recent paper trade, same "sensible default,
        # state it" pattern as run_stress_test_tool's NIFTY50 -15%.
        recent = await paper_trading_service.list_orders(db, paper_portfolio.id, limit=1)
        order = recent[0] if recent else None
    if order is None:
        return {"error": "No paper trading orders exist yet."}
    return await paper_trading_service.evaluate_order(db, order)


TOOL_REGISTRY: dict[str, ToolFunc] = {
    "get_portfolio": get_portfolio_tool,
    "get_holdings": get_holdings_tool,
    "get_sector_exposure": get_sector_exposure_tool,
    "get_market_data": get_market_data_tool,
    "get_risk_profile": get_risk_profile_tool,
    "run_stress_test": run_stress_test_tool,
    "run_monte_carlo": run_monte_carlo_tool,
    "run_backtest": run_backtest_tool,
    "get_events": get_events_tool,
    "get_event_impact": get_event_impact_tool,
    "get_macro_indicators": get_macro_indicators_tool,
    "preview_trade": preview_trade_tool,
    "evaluate_order": evaluate_order_tool,
}


async def call_tool(name: str, db: AsyncSession, portfolio: Portfolio, **kwargs: Any) -> dict:
    tool = TOOL_REGISTRY[name]
    return await tool(db, portfolio, **kwargs)
