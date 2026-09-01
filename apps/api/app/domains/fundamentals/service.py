"""Point-in-time fundamentals service (Tier 1 §15 — mandatory per the Tier 1
request). The one rule every function here must never violate:

    A query "as of" a date must never return a statement whose
    effective_date is after that date — even if its period_end already
    passed. A company's FY2025 earnings cannot be used in an analysis
    dated before those earnings were publicly available, regardless of
    when the fiscal year itself ended.

See tests/test_point_in_time_integrity.py for the regression suite this
guarantee is checked against, including the exact leak scenario (a period
that has ended but not yet been announced).
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.fundamentals import analytics
from app.domains.fundamentals.provider import get_fundamentals_provider
from app.domains.market_data.service import get_candles, get_security_by_symbol, live_market_state
from app.models.fundamentals import FinancialStatement
from app.models.security import Security


class UnknownSymbolError(Exception):
    pass


async def seed_if_needed(db: AsyncSession) -> None:
    """Idempotent, same pattern as market_data/macro/events seeding —
    generates statements once per security, not on every request (a real
    filing doesn't change on every read the way a live quote does)."""
    count = await db.scalar(select(func.count()).select_from(FinancialStatement))
    if count and count > 0:
        return

    provider = get_fundamentals_provider()
    today = datetime.now(timezone.utc).date()
    # is_tradable excludes the 2 dedicated historical-only securities
    # (Tier 1 survivorship-bias work) — they get exactly one deliberate
    # corporate action (their delisting/merger record), not also a random
    # fundamentals history a mock company that no longer trades wouldn't
    # plausibly keep filing.
    result = await db.execute(select(Security).where(Security.is_index.is_(False), Security.is_tradable.is_(True)))
    securities = list(result.scalars().all())

    for security in securities:
        quote = live_market_state.get_quote(security.symbol)
        # Falls back to the seeded starting price if live_market_state
        # somehow isn't populated yet — app.main's lifespan always seeds
        # market data before fundamentals, so this is defensive, not the
        # normal path.
        spot_price = quote["last_price"] if quote else 1000.0
        for row in provider.generate(security.symbol, today, spot_price):
            db.add(FinancialStatement(security_id=security.id, is_mock=True, **row))
    await db.commit()


async def get_latest_statement_as_of(
    db: AsyncSession, security_id: uuid.UUID, *, as_of: date, period_type: str = "annual"
) -> FinancialStatement | None:
    """THE point-in-time query. Filters on effective_date, not period_end —
    see the module docstring."""
    result = await db.execute(
        select(FinancialStatement)
        .where(
            FinancialStatement.security_id == security_id,
            FinancialStatement.period_type == period_type,
            FinancialStatement.effective_date <= as_of,
        )
        .order_by(FinancialStatement.period_end.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_statements_as_of(
    db: AsyncSession, security_id: uuid.UUID, *, as_of: date, period_type: str = "annual"
) -> list[FinancialStatement]:
    result = await db.execute(
        select(FinancialStatement)
        .where(
            FinancialStatement.security_id == security_id,
            FinancialStatement.period_type == period_type,
            FinancialStatement.effective_date <= as_of,
        )
        .order_by(FinancialStatement.period_end.asc())
    )
    return list(result.scalars().all())


async def get_point_in_time_price(db: AsyncSession, security: Security, *, as_of: date) -> float | None:
    """Live spot for today; the nearest available historical close on or
    before `as_of` for a past date — the same point-in-time discipline
    applied to the price side of a ratio, not just the fundamentals side."""
    today = datetime.now(timezone.utc).date()
    if as_of >= today:
        quote = live_market_state.get_quote(security.symbol)
        return quote["last_price"] if quote else None

    candles = await get_candles(db, security.id, limit=400)
    eligible = [c for c in candles if c.trade_date <= as_of]
    if not eligible:
        return None
    return float(max(eligible, key=lambda c: c.trade_date).close)


def statement_to_dict(security: Security, statement: FinancialStatement) -> dict:
    return {
        "symbol": security.symbol,
        "period_end": statement.period_end,
        "period_type": statement.period_type,
        "fiscal_year": statement.fiscal_year,
        "announcement_date": statement.announcement_date,
        "effective_date": statement.effective_date,
        "is_restated": statement.is_restated,
        "currency": statement.currency,
        "unit": statement.unit,
        "shares_outstanding": float(statement.shares_outstanding) if statement.shares_outstanding else None,
        "revenue": float(statement.revenue),
        "gross_profit": float(statement.gross_profit),
        "ebitda": float(statement.ebitda),
        "ebit": float(statement.ebit),
        "pbt": float(statement.pbt),
        "pat": float(statement.pat),
        "eps": float(statement.eps),
        "total_assets": float(statement.total_assets),
        "total_liabilities": float(statement.total_liabilities),
        "total_equity": float(statement.total_equity),
        "cash_and_equivalents": float(statement.cash_and_equivalents),
        "total_debt": float(statement.total_debt),
        "current_assets": float(statement.current_assets),
        "current_liabilities": float(statement.current_liabilities),
        "interest_expense": float(statement.interest_expense),
        "cfo": float(statement.cfo),
        "cfi": float(statement.cfi),
        "cff": float(statement.cff),
        "free_cash_flow": float(statement.free_cash_flow),
        "is_mock": statement.is_mock,
        "provenance": statement.provenance,
    }


async def resolve_security(db: AsyncSession, symbol: str) -> Security:
    security = await get_security_by_symbol(db, symbol)
    if security is None:
        raise UnknownSymbolError(symbol)
    return security


async def compute_ratios(
    db: AsyncSession, security: Security, statement: FinancialStatement, *, as_of: date
) -> dict:
    price = await get_point_in_time_price(db, security, as_of=as_of)
    price_as_of = min(as_of, datetime.now(timezone.utc).date())
    shares = float(statement.shares_outstanding) if statement.shares_outstanding is not None else None

    # A quarterly statement's PAT/EBITDA/revenue/EPS are one quarter's flow,
    # not a year's — comparing them directly to a price (an annual-earnings-
    # power concept) understates a quarterly P/E's denominator ~4x and
    # inflates the ratio to the same degree. Annualize flow figures (x4,
    # not a true trailing-twelve-month sum) before using them against price
    # or a balance-sheet figure — the standard "run-rate" approximation,
    # stated explicitly in `assumptions` below, not hidden.
    annualization = 4.0 if statement.period_type == "quarterly" else 1.0
    annual_pat = float(statement.pat) * annualization
    annual_ebit = float(statement.ebit) * annualization
    annual_ebitda = float(statement.ebitda) * annualization
    annual_revenue = float(statement.revenue) * annualization
    annual_eps = float(statement.eps) * annualization
    annual_fcf = float(statement.free_cash_flow) * annualization

    mcap = analytics.market_cap(price, shares) if price is not None else None
    ev = analytics.enterprise_value(mcap, float(statement.total_debt), float(statement.cash_and_equivalents))

    return {
        "symbol": security.symbol,
        "as_of": as_of,
        "period_end": statement.period_end,
        "price_used": price,
        "price_as_of": price_as_of if price is not None else None,
        "roe_pct": analytics.roe_pct(annual_pat, float(statement.total_equity)),
        "roce_pct": analytics.roce_pct(
            annual_ebit, float(statement.total_assets), float(statement.current_liabilities)
        ),
        "roa_pct": analytics.roa_pct(annual_pat, float(statement.total_assets)),
        "debt_to_equity": analytics.debt_to_equity(float(statement.total_debt), float(statement.total_equity)),
        "interest_coverage": analytics.interest_coverage(
            float(statement.ebit), float(statement.interest_expense)
        ),
        "current_ratio": analytics.current_ratio(
            float(statement.current_assets), float(statement.current_liabilities)
        ),
        "asset_turnover": analytics.asset_turnover(annual_revenue, float(statement.total_assets)),
        "market_cap": mcap,
        "pe_ratio": analytics.pe_ratio(price, annual_eps) if price is not None else None,
        "pb_ratio": analytics.pb_ratio(price, float(statement.total_equity), shares) if price is not None else None,
        "enterprise_value": ev,
        "ev_to_ebitda": analytics.ev_to_ebitda(ev, annual_ebitda),
        "ev_to_sales": analytics.ev_to_sales(ev, annual_revenue),
        "fcf_yield_pct": analytics.fcf_yield_pct(annual_fcf, mcap),
        "assumptions": (
            f"Ratios use the {statement.period_type} statement for FY{statement.fiscal_year} "
            f"(period ended {statement.period_end}, announced {statement.announcement_date}) — the latest one "
            f"actually available as of {as_of}, not necessarily the most recent fiscal period. "
            + (
                "Flow figures (PAT/EBITDA/revenue/EPS/FCF) are annualized (x4 run-rate, not a true "
                "trailing-twelve-month sum) since this is a single quarter. "
                if statement.period_type == "quarterly"
                else ""
            )
            + "Price is the "
            f"{'live simulated quote' if price_as_of == datetime.now(timezone.utc).date() else 'historical close nearest ' + str(price_as_of)}."
        ),
        "is_mock": True,
    }
