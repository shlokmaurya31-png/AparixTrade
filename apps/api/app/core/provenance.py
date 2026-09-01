"""Data provenance (Tier 1) — a shared, real answer to "where did this
number come from?" attached to actual API responses, not just declared as
a future feature. See docs/APARIX_TIER1_AUDIT.md §7.

Deliberately narrow this session: attached to the two response shapes that
serve genuinely-sourced data today (a market quote, a macro indicator).
Portfolio/risk/simulation numbers are *derived* (computed from those, plus
holdings) rather than sourced, so they don't carry their own Provenance —
the AI layer's `ai_tool_calls` persistence already gives every AI-cited
number an equivalent trace, just not via this shared model. Unifying those
two provenance mechanisms is future work, noted in
docs/APARIX_TIER1_COMPLETION_REPORT.md, not done here.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

Quality = Literal["good", "stale", "unknown"]

# How old a quote/indicator can be before it's reported "stale" rather than
# "good" — used by DataQualityService too (domains/admin/data_quality.py),
# not duplicated as a second threshold.
STALE_AFTER_SECONDS = 120


class Provenance(BaseModel):
    source: str
    provider: str
    retrieved_at: datetime
    source_timestamp: datetime | None
    effective_timestamp: datetime | None
    data_version: str = "1"
    quality: Quality = "good"


def quote_provenance(*, provider_name: str, as_of: datetime) -> Provenance:
    now = datetime.now(timezone.utc)
    age_seconds = (now - as_of).total_seconds() if as_of.tzinfo else float("inf")
    quality: Quality = "stale" if age_seconds > STALE_AFTER_SECONDS else "good"
    return Provenance(
        source="aparix-mock-market-data",
        provider=provider_name,
        retrieved_at=now,
        source_timestamp=as_of,
        effective_timestamp=as_of,
        quality=quality,
    )


def statement_provenance(
    *, provider_name: str, announcement_date, effective_date, source: str = "aparix-mock-fundamentals"
) -> Provenance:
    # announcement_date/effective_date are `date` (not `datetime`) on
    # FinancialStatement/CorporateAction — a filing/action has no
    # meaningful time-of-day, only a date. Combined with midnight UTC so
    # they fit Provenance's shared datetime fields rather than adding a
    # third, date-only variant. `source` defaults to the original
    # (fundamentals) caller for backward compatibility; corporate actions
    # passes its own.
    to_dt = lambda d: datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)  # noqa: E731
    return Provenance(
        source=source,
        provider=provider_name,
        retrieved_at=datetime.now(timezone.utc),
        source_timestamp=to_dt(announcement_date),
        effective_timestamp=to_dt(effective_date),
        quality="good",
    )


def macro_provenance(*, provider_name: str, updated_at: datetime | None) -> Provenance:
    now = datetime.now(timezone.utc)
    quality: Quality = "good" if updated_at is not None else "unknown"
    return Provenance(
        source="aparix-mock-macro-data",
        provider=provider_name,
        retrieved_at=now,
        source_timestamp=updated_at,
        effective_timestamp=updated_at,
        quality=quality,
    )
