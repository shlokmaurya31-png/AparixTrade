# Database Migration

How schema changes work in this codebase as of Tier 1, and the path from
today's SQLite dev setup to a production PostgreSQL deployment.

## What changed

Before Tier 1, this codebase created its schema via
`Base.metadata.create_all()` (`core/db.py::init_models()`) — fine for
brand-new tables, but it silently does nothing for a column added to an
*existing* table. That gap caused two real incidents (Phase 4's
`cash_balance`/`order_id` columns, requiring a one-off manual
`ALTER TABLE` script — see `docs/ARCHITECTURE.md` §11). Alembic was listed
as a dependency and had a scaffolded `alembic/env.py` since Phase 1, but
nothing ever actually ran a migration through it.

As of Tier 1, `app.main`'s `lifespan()` calls
`core/migrations.py::run_migrations()` instead of `init_models()`. Every
future schema change should be a real Alembic revision from here forward.

## How `run_migrations()` decides what to do

1. **Database already has an `alembic_version` table** — the normal case
   from here forward. Runs `alembic upgrade head`; a no-op if already
   current.
2. **Truly empty database** — `alembic upgrade head` creates the full
   schema from the baseline migration
   (`alembic/versions/f8025ac717b0_baseline_schema.py`).
3. **A pre-Tier-1 database** — has application tables (from the old
   `create_all()` path) but no `alembic_version`. This is a one-time
   transition state, not a general-purpose schema-diffing engine: the code
   adds the *specific* columns Tier 1's baseline migration introduced
   beyond the pre-Tier-1 schema (`securities.isin/segment/asset_class/
   lot_size/tick_size`, `users.role`), then `alembic stamp head` — marking
   the database as caught up without replaying history no migration ever
   recorded. Verified against this repo's own real local dev database (26
   existing users, all preserved) before being trusted, not just a
   fixture-only claim.

## Writing a new migration going forward

```bash
cd apps/api
# after changing a model:
uv run alembic revision --autogenerate -m "add whatever_column to whatever_table"
# review the generated file in alembic/versions/ — autogenerate is a
# starting point, not a guarantee (it won't detect every kind of change,
# e.g. some check constraints, some renames)
uv run alembic upgrade head
```

Commit the generated migration file alongside the model change, in the
same PR/commit — never ship a model change without its migration.

## `init_models()` — kept as a manual fallback only

`core/db.py::init_models()` (bare `create_all()`) still exists but is no
longer called by the running app. It's a local-scratch-script convenience
only — e.g. a throwaway test harness that wants a schema without an
`alembic_version` table. Never rely on it for anything that needs to
survive a later model change; use a migration.

## SQLite → PostgreSQL

Local dev stays SQLite (`aiosqlite`) — zero install, matches this
project's "no paid/external dependencies for local dev" default. The
schema is written with portable SQLAlchemy types specifically so this is a
connection-string change, not a rewrite:

```
DATABASE_URL=postgresql+asyncpg://aparix:aparix@localhost:5432/aparix
```

`docker-compose.yml` already provides a local Postgres container. **This
path has now genuinely been run against a real instance (Tier 1 Session
11)** — PostgreSQL 16 via Homebrew (Docker wasn't available in that
verification environment; the compose file's credentials were mirrored
for consistency, not used directly). All 5 steps below were actually
executed, not just described, and two real bugs were found and fixed as
a direct result — see `docs/ARCHITECTURE.md` §12, Session 11, for the
full account. Steps 1-5 remain the real procedure for a fresh target
instance:

1. Point `DATABASE_URL` at the target Postgres instance.
2. Run `alembic upgrade head` against it directly (not through the app's
   lifespan, for a controlled first deploy) — this creates the full schema
   from the same migration used for SQLite, since the model definitions
   are database-agnostic. **Confirmed**: every migration this build has
   ever generated (10 revisions, spanning every Tier 1 session) applied
   cleanly to a real empty Postgres 16 database in one run.
3. `alembic/env.py` uses `async_engine_from_config` (an async engine,
   matching the app's own runtime), so — unlike a lot of Alembic setups —
   no separate synchronous driver (e.g. `psycopg2`) needs to be installed
   alongside `asyncpg` just to run migrations. Worth re-checking only if
   `env.py` is ever rewritten to be synchronous.
4. Verify `apps/api/pyproject.toml`'s `asyncpg` dependency version is
   compatible with the target Postgres server version. **Confirmed**:
   `asyncpg>=0.30` (0.31.0 installed) against Postgres 16.
5. Re-run the full backend test suite against a real Postgres instance
   before trusting it — SQLite does not enforce the same
   concurrency/constraint behavior as Postgres (see `docs/ARCHITECTURE.md`
   §11); every DB-level unique-index-plus-retry pattern in this codebase
   (paper portfolios, broker portfolios) was only ever exercised against
   SQLite. **Confirmed, and this step is exactly what caught the two real
   bugs**: point `DATABASE_URL` at a real Postgres database before
   importing `tests/conftest.py` (it uses `os.environ.setdefault`, not an
   unconditional assignment, specifically so this works —
   `DATABASE_URL=postgresql+asyncpg://aparix:aparix@localhost:5432/aparix_test uv run pytest`).
   All 311 tests pass identically against both backends as of this
   session.

## Time-series storage beyond PostgreSQL

Not evaluated this session — current data volume (≈20 securities × ≈1
trading year of candles) has never been large enough to need
TimescaleDB/ClickHouse. Revisit once real, decades-deep historical data
ingestion (still MISSING per `docs/APARIX_TIER1_AUDIT.md`) makes plain
Postgres row-scans a real bottleneck, not before.
