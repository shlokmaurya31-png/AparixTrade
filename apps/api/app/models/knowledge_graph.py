import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class Location(Base, UUIDPrimaryKeyMixin):
    """A real Indian state/UT where a seeded security has a real,
    well-known headquarters or major facility — see
    domains/knowledge_graph/seed_data.py for the sourcing basis. Not a
    general-purpose geography table (no cities, no districts) — scoped to
    exactly what the seeded security links actually reference."""

    __tablename__ = "kg_locations"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)  # e.g. "Gujarat"
    region_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "state" | "union_territory"


class Commodity(Base, UUIDPrimaryKeyMixin):
    """A real commodity a seeded security has a well-known consumption-side
    dependency on (crude oil, coal, steel, palm oil, ...) — see
    domains/knowledge_graph/seed_data.py. Deliberately consumption-side
    only: a producer's opposite-signed exposure (e.g. ONGC benefiting from
    higher crude prices) is not modeled — see that module's docstring."""

    __tablename__ = "kg_commodities"

    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)  # "crude_oil"
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Crude Oil"


class SecurityLocationLink(Base, UUIDPrimaryKeyMixin):
    """One real fact: this security has a headquarters or major facility in
    this location. A security can have more than one (e.g. a head office in
    one state, a major plant in another) — both real, both kept."""

    __tablename__ = "kg_security_locations"
    __table_args__ = (Index("ix_kg_sec_loc_unique", "security_id", "location_id", unique=True),)

    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kg_locations.id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "headquarters" | "major_facility"


class SecurityCommodityLink(Base, UUIDPrimaryKeyMixin):
    """One real fact: this security's business has a well-known
    consumption-side dependency on this commodity."""

    __tablename__ = "kg_security_commodities"
    __table_args__ = (Index("ix_kg_sec_comm_unique", "security_id", "commodity_id", unique=True),)

    security_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities.id"), nullable=False)
    commodity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kg_commodities.id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "depends_on"
