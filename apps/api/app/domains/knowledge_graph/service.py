"""Financial knowledge graph — event propagation beyond a single target
(Tier 1). See seed_data.py for the sourcing basis and explicit scope
limits (one hop, consumption-side commodities only, no fabricated
supplier edges).

`LOCATION_PASS_THROUGH`/`COMMODITY_PASS_THROUGH` are the same kind of
honest, illustrative, non-calibrated assumption as
domains/events/impact.py's SEVERITY_MAGNITUDE_PCT — no historical data
exists to empirically derive a real pass-through rate for "a company
headquartered in a state affected by a regional event," so a real but
simple constant is used and disclosed, not fabricated precision.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.knowledge_graph.seed_data import COMMODITIES, LOCATIONS, SECURITY_COMMODITIES, SECURITY_LOCATIONS
from app.domains.market_data.service import get_security_by_symbol
from app.models.knowledge_graph import Commodity, Location, SecurityCommodityLink, SecurityLocationLink
from app.models.security import Security

# An indirect (graph-propagated) hit is real but a company headquartered
# in or depending on the affected location/commodity is realistically not
# hit anywhere near as hard as a company the event is directly about —
# these are deliberately conservative, disclosed assumptions.
LOCATION_PASS_THROUGH = 0.4
COMMODITY_PASS_THROUGH = 0.5


async def seed_if_needed(db: AsyncSession) -> None:
    """Idempotent — same pattern as every other domain. A dedicated,
    brand-new set of tables (kg_locations/kg_commodities/...), so there's
    no cross-domain seeding-order hazard the way historical-universe
    seeding had with corporate_actions (Tier 1 Session 8)."""
    count = await db.scalar(select(func.count()).select_from(Location))
    if count and count > 0:
        return

    location_ids: dict[str, object] = {}
    for name, region_type in LOCATIONS:
        location = Location(name=name, region_type=region_type)
        db.add(location)
        await db.flush()
        location_ids[name] = location.id

    commodity_ids: dict[str, object] = {}
    for code, name in COMMODITIES:
        commodity = Commodity(code=code, name=name)
        db.add(commodity)
        await db.flush()
        commodity_ids[code] = commodity.id

    for symbol, location_name, relationship_type in SECURITY_LOCATIONS:
        security = await get_security_by_symbol(db, symbol)
        if security is None:
            continue  # defensive — every symbol here is expected to exist in the seeded universe
        db.add(
            SecurityLocationLink(
                security_id=security.id, location_id=location_ids[location_name], relationship_type=relationship_type
            )
        )

    for symbol, commodity_code, relationship_type in SECURITY_COMMODITIES:
        security = await get_security_by_symbol(db, symbol)
        if security is None:
            continue
        db.add(
            SecurityCommodityLink(
                security_id=security.id,
                commodity_id=commodity_ids[commodity_code],
                relationship_type=relationship_type,
            )
        )

    await db.commit()


async def get_location_by_name(db: AsyncSession, name: str) -> Location | None:
    result = await db.execute(select(Location).where(func.lower(Location.name) == name.strip().lower()))
    return result.scalar_one_or_none()


async def get_commodity_by_code_or_name(db: AsyncSession, value: str) -> Commodity | None:
    normalized = value.strip().lower()
    result = await db.execute(
        select(Commodity).where(or_(func.lower(Commodity.code) == normalized, func.lower(Commodity.name) == normalized))
    )
    return result.scalar_one_or_none()


async def get_securities_for_location(db: AsyncSession, location_id) -> list[tuple[Security, str]]:
    result = await db.execute(
        select(Security, SecurityLocationLink.relationship_type)
        .join(SecurityLocationLink, SecurityLocationLink.security_id == Security.id)
        .where(SecurityLocationLink.location_id == location_id)
    )
    return list(result.all())


async def get_securities_for_commodity(db: AsyncSession, commodity_id) -> list[tuple[Security, str]]:
    result = await db.execute(
        select(Security, SecurityCommodityLink.relationship_type)
        .join(SecurityCommodityLink, SecurityCommodityLink.security_id == Security.id)
        .where(SecurityCommodityLink.commodity_id == commodity_id)
    )
    return list(result.all())


async def resolve_graph_exposure(db: AsyncSession, target: str) -> dict | None:
    """Returns None if `target` doesn't match any known location or
    commodity — the caller's existing direct-symbol/sector/benchmark logic
    still applies in that case, unaffected. Otherwise a real, queryable
    description of who's exposed and why, not just a bare multiplier."""
    location = await get_location_by_name(db, target)
    if location is not None:
        rows = await get_securities_for_location(db, location.id)
        return {
            "kind": "location",
            "name": location.name,
            "pass_through_pct": LOCATION_PASS_THROUGH * 100,
            "affected": [{"symbol": security.symbol, "relationship": rel} for security, rel in rows],
        }

    commodity = await get_commodity_by_code_or_name(db, target)
    if commodity is not None:
        rows = await get_securities_for_commodity(db, commodity.id)
        return {
            "kind": "commodity",
            "name": commodity.name,
            "pass_through_pct": COMMODITY_PASS_THROUGH * 100,
            "affected": [{"symbol": security.symbol, "relationship": rel} for security, rel in rows],
        }

    return None


def exposure_multipliers(resolved: dict | None) -> dict[str, float]:
    """Flattens resolve_graph_exposure()'s descriptive result into the
    plain {symbol: multiplier} shape apply_shock() (a pure, DB-free
    function) actually needs."""
    if not resolved:
        return {}
    pass_through = resolved["pass_through_pct"] / 100
    return {row["symbol"]: pass_through for row in resolved["affected"]}
