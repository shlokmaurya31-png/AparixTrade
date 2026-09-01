"""make timestamp columns timezone-aware

Revision ID: c099f67b53ef
Revises: a556075a526d
Create Date: 2026-09-02 01:47:13.505300

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c099f67b53ef'
down_revision = 'a556075a526d'
branch_labels = None
depends_on = None


COLUMNS = [
    ("transactions", "executed_at"),
    ("broker_connections", "token_expires_at"),
    ("broker_connections", "connected_at"),
    ("broker_connections", "last_synced_at"),
]


def upgrade() -> None:
    # Autogenerate produced an empty diff here — SQLite doesn't model
    # timezone-awareness distinctly at the storage level, so there's
    # nothing to actually migrate for it (existing rows and any future
    # SQLite-written row remain valid either way). Real for Postgres only:
    # these 4 columns were declared tz-naive but always received a
    # tz-aware Python datetime.now(timezone.utc) value — SQLite silently
    # tolerated the mismatch, Postgres correctly rejected it ("can't
    # subtract offset-naive and offset-aware datetimes"), caught by
    # actually running this app's real test suite against a real Postgres
    # instance (Tier 1 §5 verification), not assumed safe from the
    # SQLite-only test history every prior session's own verification had.
    if op.get_bind().dialect.name == "postgresql":
        for table, column in COLUMNS:
            op.alter_column(table, column, type_=sa.DateTime(timezone=True))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table, column in COLUMNS:
            op.alter_column(table, column, type_=sa.DateTime(timezone=False))
