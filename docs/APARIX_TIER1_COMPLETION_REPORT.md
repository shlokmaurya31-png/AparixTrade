# Aparix — Tier 1 Infrastructure, Session 1: Completion Report

Written against `docs/APARIX_TIER1_AUDIT.md` (the pre-implementation
audit) and the Tier 1 infrastructure request's own 64 sections. Honest
percentages, not aspirational ones — see §61's own instruction not to
claim 100% unless something genuinely is.

## What "Session 1" means

The Tier 1 request describes ~14 major subsystems — real fundamentals,
macro vintage tracking, news ingestion, a financial knowledge graph, RAG,
corporate actions, event propagation, a historical analogue engine, and
more. That's realistically months of work, and the request's own
instructions are explicit that Tier 1 should be built incrementally and
that nothing should be built as hollow scaffolding with no real logic
behind it. This session scoped to the pieces that are genuinely
foundational, fully real (not stubs), and fix two concrete risks the
codebase was already carrying: schema drift (`create_all()` can't add
columns — bit this codebase twice already) and RBAC being a bare email
allowlist.

## Implemented (real, tested, verified against the running app)

| Item | Where | Verification |
|---|---|---|
| Data provenance model | `core/provenance.py`, attached to market quotes and macro indicators | `tests/test_provenance.py` (3 tests); real staleness detection, not a hardcoded field |
| `DataQualityService` | `domains/admin/data_quality.py`, `GET /admin/data-quality` | `tests/test_data_quality.py` (9 tests) — each check verified against both its GOOD state and a manufactured real defect (stale timestamp, negative-price candle, deleted macro indicator) |
| `MacroDataProvider` interface | `domains/macro/provider.py` | `tests/test_macro_provider.py` (5 tests) — confirms the refactor changes nothing about the data returned |
| RBAC foundation | `core/roles.py`, `core/deps.py::require_role()`, `models/user.py::User.role` | `tests/test_rbac.py` (6 tests) — stored roles, ADMIN_EMAILS backward compatibility, non-admin roles correctly denied |
| Instrument master fields | `models/security.py` (isin/segment/asset_class/lot_size/tick_size) | Schema-level only this session — no provider populates real values yet (see Missing) |
| Real Alembic migrations | `core/migrations.py`, `alembic/versions/f8025ac717b0_baseline_schema.py` | `tests/test_migrations.py` (3 tests: fresh DB, idempotent re-run, pre-Alembic reconciliation) **and** run live against this repo's actual local dev database — 26 real users, all preserved, verified via direct SQL query, not just a test fixture |
| Admin "Data Quality" UI card | `apps/web/app/(dashboard)/admin/page.tsx` | Built, typechecked, linted, and live-verified via Playwright against the real running dev servers (logged in as the existing `demo@aparix.dev` admin account) — 3 real findings rendered (22 fresh quotes, 5,742 candle rows checked, 7/7 macro indicators present), zero console errors |
| Bug fix: `models/__init__.py` missing `BrokerConnection` import | `apps/api/app/models/__init__.py` | Found while generating the baseline migration — autogenerate would have silently produced an incomplete schema without this fix |
| Tier 1 audit | `docs/APARIX_TIER1_AUDIT.md` | Written before implementation, checked against actual code |
| Data licensing framework | `docs/DATA_LICENSING.md` | Classifies every current source — all `MOCK` today except Zerodha (`COMMERCIAL_LICENSE_REQUIRED`, user's own credentials) |
| Database migration doc | `docs/DATABASE_MIGRATION.md` | Documents the adoption path actually used, not a hypothetical one |

Test count: **139 passing** (was 114 before this session; +25 new tests,
0 regressions).

## Partially implemented

- **Provenance** only covers 2 of the many data shapes this app serves
  (market quotes, macro indicators). Portfolio/risk/simulation numbers are
  *derived*, not independently sourced, so they don't carry their own
  `Provenance` object — the AI layer's `ai_tool_calls` persistence already
  gives every AI-cited number an equivalent trace, just via a different,
  unrelated mechanism. Unifying the two is real future work, not done.
- **Instrument master** — the columns exist and are exposed in the API,
  but nothing populates real ISIN/lot-size/tick-size values, because no
  real instrument-data provider exists yet. This is schema readiness, not
  a working feature.
- **RBAC** — the role column and guard exist; there's no UI to assign
  roles (deliberately, per the request's own "don't overcomplicate the UI
  yet" instruction), so today the only way to set `compliance`/`analyst`/
  `support`/`super_admin` is a direct DB write. `admin` still also works
  via the email allowlist as before.

## Explicitly missing (not attempted this session — see the audit for why each is a real, separate effort)

- Fundamentals engine (income statement/balance sheet/ratios/valuation) —
  no data model, no provider, nothing.
- Macro time-series / vintage / revision tracking — the new
  `MacroDataProvider` wraps the existing single-current-value model
  as-is; a real vintage table is its own project.
- Corporate actions engine (splits/bonuses/dividends/mergers) and the
  adjusted-price utilities that depend on it.
- Survivorship-bias protection / point-in-time security universe.
- Real news ingestion pipeline (fetch/normalize/dedupe/classify/extract).
- Event propagation beyond one target (no location → industry → company →
  supply-chain → commodity → macro chain).
- Financial knowledge graph (entities + typed relationships), and its API.
- Document intelligence / RAG (no document model, no embeddings, no
  vector store — the `researcher` AI mode still honestly declines).
- Historical analogue engine.
- Portfolio exposure beyond sector (company/industry/geographic/commodity/
  factor).
- Admin data-control-center additions beyond the one new Data Quality
  card (no ingestion-job monitoring, because no ingestion jobs exist).
- Frontend event-impact panel, portfolio exposure graph, AI evidence
  drawer (§51–53) — none of these exist.
- **Point-in-time no-look-ahead-bias test suite (§49)** — deliberately not
  written. Nothing in this codebase has an announcement-date/
  effective-date split yet (that needs real fundamentals or macro vintage
  data first); writing this suite now would be an empty shell asserting
  nothing meaningful, which is its own kind of the fake functionality this
  request explicitly prohibits. Write it alongside whichever of
  fundamentals/macro-vintage ships first.
- Open-source research review (§46 — FinRL, PyKiteConnect, indian-market-mcp,
  kite-algo, Fenix, and broader quant/RAG/graph/time-series tooling) —
  **not done this session**. This report will not fabricate an assessment
  of repositories that weren't actually reviewed; that review is real,
  separate work for whenever a specific subsystem (e.g. RAG, or a
  broker-adapter rewrite) makes evaluating a specific candidate concrete
  rather than speculative.
- Rate limiting, request-ID middleware, sanitized error responses (§42) —
  still missing, unchanged from the audit.
- Kafka/Redpanda event bus, background worker process (§41, §57) — still
  just the one in-process asyncio tick loop.

## Architecture decisions

- **Provenance stayed narrow rather than universal.** Attaching it to
  every response shape in the app this session would have meant either
  fabricating provenance for derived numbers (dishonest — a computed
  portfolio value doesn't have a "source" the way a quote does) or a much
  larger refactor. Attached only where it's genuinely meaningful.
- **`FundamentalsProvider`/`NewsProvider`/`DocumentProvider` interfaces
  were *not* created this session**, even though §5–6 asks for them,
  because there is no real data behind them yet — an interface with only
  an empty or trivially-fake Mock implementation is exactly the "fake
  functionality" §55 prohibits. `MacroDataProvider` was built instead,
  because the macro domain already has real (if mock) data to wrap.
- **RBAC kept `ADMIN_EMAILS` rather than migrating everyone to the new
  `role` column immediately.** A silent migration risked locking out
  whoever is currently relying on the allowlist; the OR-condition design
  (`require_role` accepts either) is a deliberate backward-compatibility
  choice, not an oversight — see `core/deps.py`.
- **The pre-Alembic reconciliation logic is intentionally narrow** (a
  hardcoded list of the exact columns this session's own migration added),
  not a generic schema-diffing engine — see `core/migrations.py`'s
  docstring for why that scope is correct rather than a shortcut.

## Data sources (see `docs/DATA_LICENSING.md` for the full table)

Every data source in this codebase remains `MOCK` (synthetic/seeded)
except Zerodha Kite Connect, which is `COMMERCIAL_LICENSE_REQUIRED` and
gated behind each user's own credentials — this session added no new
external data source and changed no licensing posture.

## Security concerns

- Rate limiting, request-ID middleware, and sanitized error responses are
  still missing — flagged in the audit, not addressed this session (RBAC
  was prioritized as the higher-leverage piece).
- RBAC has no role-editing UI or audit trail specifically for role
  changes yet (a direct DB write to change a role isn't logged via
  `log_action()` the way an in-app action would be) — a real gap for
  whenever a role-management endpoint is built.
- The pre-Alembic reconciliation path executes raw `ALTER TABLE` SQL
  built from a hardcoded table/column list (not user input) — not an
  injection risk, but worth noting since it's one of the only places in
  this codebase that constructs SQL via string formatting rather than the
  ORM/parameterized queries.

## Known limitations

- `check_candle_integrity()` (`domains/admin/data_quality.py`) does a full
  table scan — fine at today's data volume (~20 securities × ~1 trading
  year), documented in its own docstring as needing batching/pagination
  before a real, much larger historical dataset makes that slow.
- PostgreSQL migration path is documented (`docs/DATABASE_MIGRATION.md`)
  but never actually run against a real Postgres instance in this
  environment — SQLite-only verification, same limitation the codebase
  already carried before this session.

## Next recommended features

In rough dependency order, matching what actually unblocks the most:

1. **Fundamentals engine + point-in-time enforcement** — the biggest
   single MISSING item with the most downstream value (unblocks real
   ratios/valuation, and is a prerequisite for the point-in-time test
   suite this session explicitly deferred).
2. **Corporate actions engine** — needed before any real historical price
   series can be trusted for backtesting/risk math beyond mock data.
3. **News ingestion (dev/RSS-tier source) → real event extraction** — the
   event engine's single biggest limitation today is that events are
   hand-seeded, not derived from anything.
4. **RAG foundation** — now genuinely unblocked (a real LLM exists since
   Phase 3.5) but still needs an actual document corpus decision before
   the pipeline is worth building.
5. **RBAC role-management UI + audit trail** — the natural follow-up to
   this session's backend-only RBAC landing.

## Production readiness score

**Not production-ready as an Indian financial intelligence platform** —
this remains, honestly, a well-architected prototype with real (not fake)
quant/risk/options math and a real AI tool-grounding discipline, sitting
on top of entirely synthetic data. Scored by area, against what §61 asks
for:

| Area | Readiness | Why |
|---|---|---|
| Core architecture (domain structure, provider pattern, testing discipline) | **~75%** | Genuinely solid and now includes real migrations + RBAC; still missing rate limiting, request IDs, and a background-worker/event-bus abstraction |
| Data integrity infrastructure (provenance, quality, migrations) | **~40%** | Real but narrow — 2 of many data shapes have provenance, quality checks cover 3 of many possible failure modes, no point-in-time enforcement anywhere yet |
| Actual financial data (market/fundamentals/macro/news/corporate actions) | **~5%** | Everything is synthetic; zero real data sources integrated |
| Knowledge graph / event intelligence / RAG | **0%** | Not started beyond the narrow one-target event-impact calculation that already existed pre-Tier-1 |
| Security (RBAC, encryption, rate limiting, audit) | **~35%** | RBAC and credential encryption are real; rate limiting, request IDs, and error sanitization are entirely absent |
| Regulatory posture | **~50%** | The education/analytics/advisory/execution boundary is genuinely maintained in product copy and this doc set — but that discipline has never been reviewed by an actual compliance professional, which the request itself says is required before anything resembling real advice or execution ships |

**Overall: this session moved the foundation meaningfully forward
(schema-drift risk fixed, real RBAC, a real provenance/quality seam
proven end-to-end) without adding a single line of fake functionality —
but "Aparix, the financial intelligence operating system for India" is
still, honestly, mostly ahead of this codebase, not behind it.**
