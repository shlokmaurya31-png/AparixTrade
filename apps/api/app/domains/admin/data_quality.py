"""DataQualityService (Tier 1) — real checks against real (mock) data, not
placeholder findings. See docs/APARIX_TIER1_AUDIT.md §8.

Every check here can genuinely fail today if the underlying mock data is
manipulated to be bad (see tests/test_data_quality.py) — this isn't a set
of checks that always report GOOD by construction.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.provenance import STALE_AFTER_SECONDS
from app.domains.macro.seed_data import SEED_INDICATORS
from app.domains.market_data.service import live_market_state
from app.models.macro import MacroIndicator
from app.models.security import Candle


@dataclass
class QualityFinding:
    check: str
    status: str  # "GOOD" | "WARNING" | "STALE" | "INVALID" | "UNKNOWN"
    detail: str


def check_market_data_freshness() -> list[QualityFinding]:
    quotes = live_market_state.all_quotes()
    if not quotes:
        return [
            QualityFinding(
                check="market_data_freshness", status="UNKNOWN", detail="No live quotes available yet."
            )
        ]
    now = datetime.now(timezone.utc)
    stale = [q for q in quotes if (now - q["as_of"]).total_seconds() > STALE_AFTER_SECONDS]
    if stale:
        symbols = ", ".join(q["symbol"] for q in stale[:5])
        return [
            QualityFinding(
                check="market_data_freshness",
                status="STALE",
                detail=f"{len(stale)} symbol(s) older than {STALE_AFTER_SECONDS}s (e.g. {symbols}).",
            )
        ]
    return [
        QualityFinding(
            check="market_data_freshness",
            status="GOOD",
            detail=f"All {len(quotes)} live quotes are fresh (< {STALE_AFTER_SECONDS}s old).",
        )
    ]


async def check_candle_integrity(db: AsyncSession) -> list[QualityFinding]:
    """Full scan, not a sample — fine at today's data volume (~20
    securities x ~1 trading year). A real historical dataset spanning
    decades would need this batched/paginated rather than loaded whole;
    documented as a known limitation, not solved here."""
    result = await db.execute(select(Candle))
    candles = list(result.scalars().all())
    invalid: list[str] = []
    for c in candles:
        o, h, l, cl, vol = float(c.open), float(c.high), float(c.low), float(c.close), c.volume
        if o <= 0 or h <= 0 or l <= 0 or cl <= 0:
            invalid.append("non-positive price")
        elif h < l:
            invalid.append("high < low")
        elif not (l <= o <= h and l <= cl <= h):
            invalid.append("open/close outside high-low range")
        elif vol < 0:
            invalid.append("negative volume")
    if invalid:
        return [
            QualityFinding(
                check="candle_integrity",
                status="INVALID",
                detail=f"{len(invalid)} of {len(candles)} candle row(s) failed an integrity check (e.g. {invalid[0]}).",
            )
        ]
    return [
        QualityFinding(
            check="candle_integrity",
            status="GOOD",
            detail=f"{len(candles)} candle rows checked (price/volume/OHLC-ordering), no issues found.",
        )
    ]


async def check_macro_coverage(db: AsyncSession) -> list[QualityFinding]:
    expected_codes = {code for code, *_ in SEED_INDICATORS}
    result = await db.execute(select(MacroIndicator.code))
    existing_codes = {row[0] for row in result.all()}
    missing = expected_codes - existing_codes
    if missing:
        return [
            QualityFinding(
                check="macro_coverage",
                status="WARNING",
                detail=f"Missing indicator(s): {', '.join(sorted(missing))}.",
            )
        ]
    return [
        QualityFinding(
            check="macro_coverage",
            status="GOOD",
            detail=f"All {len(expected_codes)} expected macro indicators present.",
        )
    ]


async def run_all_checks(db: AsyncSession) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    findings += check_market_data_freshness()
    findings += await check_candle_integrity(db)
    findings += await check_macro_coverage(db)
    return findings
