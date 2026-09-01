# Aparix — Tier 1 Infrastructure Audit

Written before any Tier 1 implementation work, per the Tier 1 build request.
Statuses: **IMPLEMENTED**, **PARTIAL**, **MOCK**, **MISSING**, **BROKEN**,
**DEPRECATED**. Nothing below is inferred — every row was checked against
the actual code as of commit `eae354a` (Phase 6 complete), not remembered
from a spec.

## How to read this

"MOCK" here does not mean "bad" — every mock in this codebase is a
deliberate, documented placeholder behind a real interface (`ModelProvider`,
`MarketDataProvider`, `BrokerAdapter`), built specifically so a real
provider can be swapped in later without touching the code above it. That
pattern is the single biggest asset Tier 1 has to build on — see
`docs/ARCHITECTURE.md` §9 for the full trade-off history behind every one
of these decisions.

## Frontend

| Area | Status | Files | Notes |
|---|---|---|---|
| App shell / nav / command bar | IMPLEMENTED | `apps/web/app/(dashboard)/layout.tsx`, `components/aparix/AparixCommandBar.tsx` | ⌘K command palette, role-gated Admin nav item |
| Design system | IMPLEMENTED | `components/aparix/Aparix{Card,Metric,Badge,Table,Heatmap,...}.tsx` | Consistent, dark-first, no gradients — every screen built from these |
| Auth flows (register/login/onboarding) | IMPLEMENTED | `app/(login,register,onboarding)/page.tsx` | JWT stored in `localStorage`, no refresh-token rotation UI yet |
| Portfolio page + multi-portfolio switcher | IMPLEMENTED | `app/(dashboard)/portfolio/page.tsx`, `components/aparix/PortfolioSwitcher.tsx` | Aggregate "All portfolios" view added Phase 6 |
| Risk & simulation UI | IMPLEMENTED | `app/(dashboard)/risk/page.tsx` | VaR/CVaR, correlation heatmap, Monte Carlo, stress test, backtest |
| Options UI | IMPLEMENTED | `app/(dashboard)/options/page.tsx` | Chain table + IV smile chart, analysis only |
| Paper trading UI | IMPLEMENTED | `app/(dashboard)/paper/page.tsx` | Order ticket, preview-before-commit, history |
| Broker UI | IMPLEMENTED | `app/(dashboard)/broker/page.tsx` | Connect/sync/disconnect, mock adapter live-tested, Zerodha adapter untested |
| Events UI | PARTIAL | `app/(dashboard)/events/page.tsx` | Lists seeded events + one-target impact; no propagation graph, no evidence drawer, no confidence score |
| AI Terminal | IMPLEMENTED | `app/(dashboard)/ai/page.tsx` | 7 real modes + 1 honest-decline mode, "View data source" per answer |
| Admin dashboard | PARTIAL | `app/(dashboard)/admin/page.tsx` | 4 read-only views (users, audit log, AI usage, system health) — no data-provider/ingestion/lineage panels |
| Data freshness/source/confidence indicators | MOCK-ONLY | `components/aparix/AparixBadge.tsx` `DemoDataBadge` | A single binary "Demo data" badge everywhere — no LIVE/STALE/UNKNOWN distinction, no per-record confidence |
| Event impact panel, exposure graph, AI evidence drawer | MISSING | — | None of §51–53's signature UI components exist |

## Authentication & Users

| Area | Status | Files | Notes |
|---|---|---|---|
| Email+password auth | IMPLEMENTED | `domains/auth/`, `core/security.py` | bcrypt (direct, not via `passlib` — see Phase 1 fix), JWT access (30m) + refresh (14d) |
| OAuth / MFA / device mgmt | MISSING | — | Documented as deferred since Phase 1 |
| RBAC | MOCK | `core/config.py::is_admin_email`, `core/deps.py::get_current_admin_user` | A comma-separated email allowlist checked dynamically, not a stored role. No `SUPER_ADMIN/ADMIN/COMPLIANCE/ANALYST/SUPPORT` distinction — binary admin/not-admin only |
| User preferences / complexity system | IMPLEMENTED | `models/user.py::UserPreferences` | `complexity_level` 1–5, `ai_detail_level` 1–5, `ai_mode` enum — but only 2 of the spec's 5 named complexity tiers (SIMPLE/INFORMED/ADVANCED/QUANT/INSTITUTIONAL) map cleanly; the numeric levels drive the same UI, not distinct named tiers yet |

## Portfolio

| Area | Status | Files | Notes |
|---|---|---|---|
| Portfolio CRUD, multi-portfolio | IMPLEMENTED | `domains/portfolios/` | `GET/POST /portfolios` supported >1 portfolio per user since Phase 1; frontend switcher added Phase 6 |
| Holdings, manual entry | IMPLEMENTED | `domains/portfolios/service.py::add_holding` | |
| Portfolio analytics (value, P&L, sector exposure, concentration, vol, beta) | IMPLEMENTED | `domains/portfolios/analytics.py` | Pure, fixture-tested |
| Company/industry/geographic/commodity/factor exposure | MISSING | — | Only sector exposure exists (§30 wants 7 more exposure dimensions) |
| Portfolio Digital Twin (unified object: positions+transactions+cash+risk+factors+events+macro sensitivity) | MISSING | — | No such object; risk/events/macro are each computed independently on demand, not merged into one context object |
| Paper trading (virtual capital, slippage, brokerage) | IMPLEMENTED | `domains/paper_trading/` | Concurrency-safe (`get_or_create_paper_portfolio`), fixture + HTTP tested |
| Broker sync (Zerodha) | PARTIAL | `domains/broker/` | Mock adapter fully live-tested; `ZerodhaKiteAdapter` built to the documented Kite Connect v3 contract but never exercised against a real account (no paid dev subscription available) |

## Market Data

| Area | Status | Files | Notes |
|---|---|---|---|
| `MarketDataProvider` interface | IMPLEMENTED | `domains/market_data/provider.py` | Abstract base + `MockMarketDataProvider` — exactly the pattern §5 asks Tier 1 to generalize to every other data domain |
| Real market data provider | MISSING | — | No `DevelopmentMarketDataProvider`/`ProductionMarketDataProvider` exists; only Mock |
| Instrument/security master | PARTIAL | `models/security.py::Security` | Has symbol/name/sector/exchange (hardcoded `"NSE"` default)/`instrument_type`/`is_index` — no ISIN, no segment, no lot size, no tick size, no BSE/MCX support, no options/futures contract fields |
| Historical candles | MOCK | `models/security.py::Candle` | ~365 calendar days of seeded random-walk OHLCV per security, deterministic. No real historical data, no decades of history, no raw/normalized/adjusted/derived separation |
| Corporate actions (splits, bonuses, dividends, mergers) | MISSING | — | No model, no adjustment logic. Historical prices are NOT adjusted for anything, because nothing has ever needed adjusting (all mock data) |
| Survivorship-bias protection / point-in-time universe | MISSING | — | The seeded universe (`seed_data.py`, ~20 names) is static and timeless; there is no concept of "what existed on date X" |
| Live tick simulation + WebSocket | IMPLEMENTED | `domains/market_data/websocket.py`, `LiveMarketState` | In-memory, not DB-persisted, ticks every few seconds |

## Fundamentals

| Area | Status | Files | Notes |
|---|---|---|---|
| Income statement / balance sheet / cash flow / ratios / valuation | MISSING | — | No `FundamentalsProvider`, no models, nothing. This is a from-scratch build |
| Point-in-time fundamentals (announcement vs. effective date enforcement) | MISSING | — | Cannot exist before fundamentals data exists |

## Macro

| Area | Status | Files | Notes |
|---|---|---|---|
| Macro indicators | MOCK | `domains/macro/`, `models/macro.py::MacroIndicator` | 7 seeded indicators (repo rate, CPI, GDP, INR/USD, crude, gold, 10Y G-Sec) as single current values |
| Time series / vintage / revision tracking | MISSING | — | Each indicator is exactly one row (current value only) — no history, no release-date/revision/vintage model at all (§17 requires this) |
| `MacroDataProvider` interface | MISSING | — | `domains/macro/service.py` calls the DB directly; no provider abstraction exists yet to swap in a real RBI/MOSPI feed later |

## News & Events

| Area | Status | Files | Notes |
|---|---|---|---|
| News ingestion pipeline (fetch/normalize/dedupe/classify/extract) | MISSING | — | No news domain exists at all. "Events" (below) are hand-seeded, not derived from any news source |
| Event model | PARTIAL | `models/event.py::Event`, `domains/events/` | Has headline/summary/event_type/severity/direction/`primary_target`/`secondary_tags`/region — but `primary_target` is a single string (one sector, symbol, or `"NIFTY50"`), not a graph of typed entities/relationships |
| Event impact calculation | IMPLEMENTED (narrow) | `domains/events/service.py::compute_impact_for_portfolio` | Reuses the stress-test engine (`apply_shock`) for a single target — real math, but one hop only |
| Event propagation (location → industry → company → supply chain → commodity → macro → market → portfolio) | MISSING | — | §21's whole multi-hop chain does not exist; every event maps to exactly one target |
| Financial knowledge graph (entities + typed relationships: SUPPLIES/COMPETES_WITH/DEPENDS_ON/etc.) | MISSING | — | No graph model, no graph API, no Neo4j evaluation done |
| Event confidence scoring | MISSING | — | Every impact number is deterministic (severity → fixed %), no probabilistic/confidence output |

## Document Intelligence / RAG

| Area | Status | Files | Notes |
|---|---|---|---|
| Document ingestion, chunking, embeddings, vector store | MISSING | — | No document model, no `DocumentProvider`, no pgvector/Qdrant, nothing. Explicitly named "unblocked but not built" in `ARCHITECTURE.md` since Phase 3.5 |
| RAG-backed AI answers with citations | MISSING | — | The `researcher` AI mode exists as a persona slot and honestly declines every question — this is the one AI mode intentionally never implemented, for exactly this reason |

## Quant / Risk / Simulation

| Area | Status | Files | Notes |
|---|---|---|---|
| VaR/CVaR (historical simulation), Sharpe, Sortino, max drawdown | IMPLEMENTED | `domains/risk/analytics.py` | Pure, fixture-tested, `MIN_SAMPLE_SIZE=20` guard against noisy small-sample stats |
| Correlation / covariance matrices | IMPLEMENTED | `domains/risk/analytics.py` | |
| Monte Carlo (GBM + historical bootstrap) | IMPLEMENTED | `domains/simulation/monte_carlo.py` | Portfolio-level only, not multi-asset correlated |
| Stress testing (custom shocks) | IMPLEMENTED | `domains/simulation/stress_test.py` | Synthetic shocks only — no real historical crisis scenario library (2008/2020/etc. are `COMING SOON` in the UI) |
| Backtesting | IMPLEMENTED | `domains/simulation/backtest.py` | Buy-and-hold of current weights only, no strategy DSL, no transaction costs |
| Options pricing/Greeks | IMPLEMENTED | `domains/options/pricing.py`, `service.py` | Closed-form Black-Scholes, fixture-tested against a published reference + exact identities; synthetic chain, assumed IV, not persisted |
| Factor risk / liquidity risk / event risk / macro risk decomposition | MISSING | — | Risk score today is a simple concentration+vol+beta composite (1–5), not decomposed by risk type |
| Historical analogue engine ("have we seen this before?") | MISSING | — | No regime/similarity matching exists |

## AI

| Area | Status | Files | Notes |
|---|---|---|---|
| `ModelProvider` interface + Mock + Ollama implementations | IMPLEMENTED | `domains/ai/provider.py`, `ollama_provider.py` | The exact pattern §5 wants generalized to every other data domain — proven across 2 real implementations |
| Tool registry (16 tools) | IMPLEMENTED | `domains/ai/tools.py`, `tool_schemas.py` | Self-consistency-checked at import time (`assert_schemas_match_registry`) |
| Tool-grounded answers, `ai_tool_calls` provenance | IMPLEMENTED | — | Every AI-cited number traces to a persisted tool-call row — this **is** a working, narrow version of §7's provenance requirement, just not generalized past AI answers to every data record |
| AI context engine (merge portfolio+market+events+news+fundamentals+risk+macro+documents into one context object) | PARTIAL | — | Each tool call fetches one slice; there's no unified context-builder object — the LLM assembles context itself by choosing which tools to call, which is weaker and slower than a pre-built context bundle |
| 6-mode + options_specialist real personas, researcher honest decline | IMPLEMENTED | `domains/ai/ollama_provider.py::MODE_INSTRUCTIONS` | |
| New tools from §28 (`search_news`, `get_company`, `get_fundamentals`, `search_documents`, `get_entity_relationships`, `get_data_provenance`, `get_historical_analogue`) | MISSING | — | None of these exist because the underlying data domains don't exist yet |

## Admin / Data Ops

| Area | Status | Files | Notes |
|---|---|---|---|
| Read-only admin views (users, audit log, AI usage, system health) | IMPLEMENTED | `domains/admin/` | |
| Data provider status / freshness / ingestion job monitoring | MISSING | — | No ingestion jobs exist to monitor |
| Data lineage UI (metric → derived from → raw → provider → timestamp) | MISSING | — | No provenance model to visualize yet |
| `DataQualityService` | MISSING | — | No systematic staleness/invalid-price/duplicate detection exists anywhere |

## Database & Infrastructure

| Area | Status | Files | Notes |
|---|---|---|---|
| SQLite (dev) | IMPLEMENTED | `core/db.py` | Zero-install local dev, `create_all()`-based (no Alembic migrations actually run — see known risk below) |
| PostgreSQL (prod target) | PARTIAL | `docker-compose.yml` | Container defined, connection string documented as a swap, never actually run against in this environment |
| Alembic | SCAFFOLDED, UNUSED | `alembic.ini` (if present) / `pyproject.toml` dep | Listed as a dependency; the app has never actually generated or run a migration — every schema change to date used either `create_all()` (new tables) or a manual one-off `ALTER TABLE` script (new columns on existing tables). This is a real gap, not a style choice |
| Time-series optimized storage (TimescaleDB/ClickHouse) | MISSING | — | Not evaluated yet — market data volume (365 days × ~20 securities) has never been large enough to need it |
| Event bus / internal event contracts | MISSING | — | No `MarketPriceUpdated`/`EventDetected`/etc. formal event contracts; state changes happen via direct function calls and DB writes, not an event abstraction |
| Background workers | MISSING | — | The one background task is the in-process `run_tick_loop()` asyncio task (`domains/market_data/websocket.py`) — no worker process, no queue, no Kafka/Redpanda |

## Security

| Area | Status | Files | Notes |
|---|---|---|---|
| Password hashing | IMPLEMENTED | `core/security.py` | Direct `bcrypt`, not `passlib` (fixed a real Phase 1 incompatibility) |
| JWT signing | IMPLEMENTED | `core/security.py` | HS256, configurable secret |
| Secret/credential encryption at rest | IMPLEMENTED (narrow) | `core/crypto.py` | Fernet, `BROKER_ENCRYPTION_KEY` — only broker credentials use this today; no general secrets-management layer |
| Rate limiting | MISSING | — | No rate limiting anywhere in the API |
| CORS | IMPLEMENTED | `app/main.py` | `CORSMiddleware`, configurable origins |
| Request IDs / structured error sanitization | MISSING | — | FastAPI's default exception handling; no request-ID middleware, no sanitized-error-response layer |
| Audit logging | IMPLEMENTED (narrow) | `domains/audit/service.py::log_action` | Called from every auth/portfolio/paper/broker/AI mutation — actor, action, input, output, timestamp. No IP/device/user-agent capture, no separate AI-specific fields (model, version, token usage) |
| RBAC (permission-based, not email-allowlist) | MISSING | — | See Users section above |

## Testing

| Area | Status | Files | Notes |
|---|---|---|---|
| Backend test suite | IMPLEMENTED | `apps/api/tests/` | 114 tests, all passing, covering every domain above with real fixture tests (not smoke tests) |
| Point-in-time / no-look-ahead-bias tests | MISSING | — | Cannot meaningfully exist yet — there's no fundamentals or macro-vintage data with an announcement/effective-date distinction to test against. Writing this test suite now would just be an empty shell around data that doesn't exist |
| Data-quality / provenance / corporate-action tests | MISSING | — | Same reason — the subsystems don't exist yet |
| Frontend automated tests | MISSING | — | Every phase has been verified via live Playwright browser sessions instead (see `ARCHITECTURE.md` §11), never committed as an automated suite |

## Documentation

| Area | Status | Files | Notes |
|---|---|---|---|
| `ARCHITECTURE.md` | IMPLEMENTED | `docs/ARCHITECTURE.md` | Kept current through every phase — 11 sections, a growing trade-offs table, a known-risks list |
| `README.md` | IMPLEMENTED | `README.md` | Setup + feature tour, updated every phase |
| Data licensing, data architecture, database migration, event intelligence, knowledge graph, RAG architecture, AI architecture, security docs | MISSING | — | None of §54's other named documents exist yet — there was nothing to document until the underlying systems existed |

## Summary: what Tier 1 actually needs to build vs. what it can build on

**Real, load-bearing foundation already in place** (this is not nothing —
it's the hardest part to retrofit later): a proven provider-interface
pattern (3 independent implementations of "abstract interface + Mock +
real"), a working tool-grounded AI answer pipeline with per-answer
provenance, a modular-monolith domain structure that's held up cleanly
across 6 phases, a real (if narrow) audit log, and a disciplined
"never fake data, always label DEMO/MOCK" culture enforced in every prior
phase.

**Genuinely missing, not just incomplete**: every data domain outside
market data and AI (fundamentals, real macro time-series, news, documents,
corporate actions, a knowledge graph), RBAC beyond a binary admin flag,
systematic data quality/provenance as a first-class concept (vs. AI's
narrow version of it), and an actual database migration discipline
(Alembic is a listed dependency, not a used one).

See `docs/APARIX_TIER1_COMPLETION_REPORT.md` (written after this session's
implementation work) for what was actually built against this audit, and
what remains explicitly deferred.
