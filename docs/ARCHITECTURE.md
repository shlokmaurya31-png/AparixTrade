# Aparix — Architecture

Aparix is an AI-native Indian financial intelligence platform. This document
describes the system as built (Phase 1 + 2 + 3 + 3.5 + 4 + 5 + 6, scoped) —
every phase on the original roadmap is now done, scoped as documented below.
It is intentionally condensed — the full product spec this was derived from
runs to ~80 sections; this document captures the decisions that matter for
engineers picking up the codebase.

## 1. Product shape

Aparix is not a trading app with an AI chatbot bolted on. The intended data
flow, which the module boundaries below are organized around, is:

```
EVENT → DATA → ENTITY RECOGNITION → EXPOSURE GRAPH → MARKET IMPACT
      → PORTFOLIO EXPOSURE → RISK ENGINE → SCENARIO ENGINE
      → QUANTITATIVE ANALYSIS → AI INTERPRETATION → USER DECISION
      → OPTIONAL EXECUTION
```

The LLM sits at "AI INTERPRETATION" only. It explains and converses; it does
not compute. Every number an AI response cites must come from a deterministic
tool call against real (or, in Phase 1, clearly-labeled mock) data — never
from the model's own generation. This is enforced structurally: the
`ai_tool_calls` table records exactly which tool ran and what it returned for
every AI message, so any claim is traceable — and as of Phase 3.5, that
guarantee holds for a *real* model, not just the keyword-templated mock one.

Phase 1 implemented the portfolio → basic risk → AI explanation slice. Phase 2
added the risk and simulation engines — historical VaR/CVaR, Sharpe/Sortino,
correlation/covariance, Monte Carlo, custom stress testing, and buy-and-hold
backtesting. Phase 3 is the first slice that actually spans the whole
pipeline: seeded mock **events** map to sectors/companies (the "ENTITY
RECOGNITION"/"EXPOSURE GRAPH" steps, simplified — see §9), propagate through
the exact same shock math the risk engine already had (`apply_shock()`), and
land in an AI-citable, portfolio-specific impact number — plus a mock macro
domain and a read-only admin dashboard. Phase 3.5 (this update) replaces
`MockModelProvider`'s keyword router with a real local LLM
(`OllamaModelProvider`, `llama3.1` via Ollama) that actually understands
free-form questions and calls the *same* `TOOL_REGISTRY` tools — the
"AI INTERPRETATION" step in the diagram above is now genuinely doing
interpretation, not template-filling. Still no real ingestion, no RAG, no
execution. See §10 Roadmap.

## 2. Complexity levels (the core UX device)

Every user has a `complexity_level` (1–5) and `ai_detail_level` (1–5) in
`user_preferences`. The frontend does not just hide/show metrics at higher
levels — it changes language, chart density, and terminology.

- **Levels 1–2** (Simple/Informed): value, P&L, sector exposure,
  concentration, simple volatility, simple beta — the Phase 1 portfolio
  engine.
- **Level 3** (Advanced): VaR, CVaR, Sharpe, Sortino, max drawdown, holding
  correlation matrix — now real (Phase 2, `domains/risk`), shown on `/home`
  and the dedicated `/risk` workspace.
- **Level 4** (Quant): Monte Carlo (GBM + historical bootstrap), covariance
  matrix, backtest diagnostics — now real (Phase 2, `domains/simulation`).
- **Still `COMING SOON`**: factor models (value/growth/momentum — needs a
  fundamentals data domain that doesn't exist yet), regime detection,
  historical crisis scenarios (2008/COVID/2022 — no real historical data
  exists to replay, see §9), option Greeks/vol surfaces (needs an options
  domain, Phase 6). Faking any of these is explicitly against the product's
  safety principles (see §8) — they stay visibly unimplemented rather than
  approximated.

## 3. Repository layout

```
apps/
  web/     Next.js 16 (App Router), TypeScript strict, Tailwind v4
  api/     FastAPI, modular monolith, uv-managed
docs/      This file
docker-compose.yml   Optional Postgres (+ Redis, commented out) for those with Docker
```

Domain modules inside `apps/api/app/domains/`: `auth`, `users`, `portfolios`,
`market_data`, `risk`, `simulation`, `events`, `macro`, `admin`,
`paper_trading`, `broker`, `options`, `fundamentals`, `corporate_actions`,
`news`, `ai`, `audit`. Each is self-contained
(models it owns, its own service layer, its own router) so it can be
extracted into a separate service later without a rewrite — but this stays a
single deployable FastAPI app (spec's own guidance: don't create
microservices before you need them).

## 4. Backend architecture

- **FastAPI** app, async throughout (SQLAlchemy 2.0 async ORM).
- **Auth**: email+password, bcrypt hashing (`passlib`), JWT access (30 min)
  + refresh (14 day) tokens (`python-jose`). No OAuth/MFA/device management in
  Phase 1 — flagged as Phase 2+ security hardening, not skipped by oversight.
- **`MarketDataProvider`** interface (`domains/market_data/provider.py`) with
  a `MockMarketDataProvider` implementation: seeded, deterministic random-walk
  daily candles for a ~20-name NIFTY subset + two indices, all rows tagged
  `is_mock=True`. A background asyncio task ticks last-traded price every few
  seconds and broadcasts over a `market.price` WebSocket channel. Swapping in
  a real provider (NSE-licensed feed, broker API) later means implementing the
  same interface — nothing above it changes.
- **Portfolio engine** (`domains/portfolios/analytics.py`): pure functions,
  no I/O, unit-testable with fixed input → expected-output fixtures. Computes
  total value, day/total P&L, sector weights, an HHI-based concentration
  score, simple annualized volatility and beta against the mock NIFTY series.
  These are the only numbers Phase 1 is allowed to show — nothing is
  extrapolated beyond what's actually computed.
- **`ModelProvider`** interface (`domains/ai/provider.py`) with
  `MockModelProvider` (keyword-routed templates) and, since Phase 3.5,
  `OllamaModelProvider` (a real local LLM running an actual tool-calling
  loop) implementing the identical interface — see §7 for the detail.
- **Audit log**: `log_action()` is called from every auth and portfolio
  mutation and every AI tool call, writing to `audit_logs` (actor, action,
  input, output, timestamp). Not exhaustive (no IP/device capture yet — no
  auth middleware surfaces that in Phase 1), but the table and call sites
  exist so later hardening extends rather than retrofits it.
- **Risk engine** (`domains/risk/analytics.py` + `service.py`): historical-
  simulation VaR/CVaR, Sharpe/Sortino, max drawdown, correlation/covariance
  matrices — pure functions, fixture-tested exactly like the portfolio
  engine. Shares `compute_portfolio_return_series()`
  (`domains/portfolios/service.py`) with the portfolio engine so both use
  the identical weighting methodology.
- **Simulation engine** (`domains/simulation/`): `monte_carlo.py` (GBM +
  historical bootstrap), `stress_test.py` (custom shock propagation via
  beta), `backtest.py` (buy-and-hold walk-forward, no look-ahead). Backtest
  runs persist to `backtests`; Monte Carlo/stress-test results are stateless
  (see §9 for why).
- **Event engine** (`domains/events/`): seeded mock news events
  (`is_mock=True`, same discipline as market data), each tagged with a
  single `primary_target` (a sector, a security symbol, or `"NIFTY50"`) plus
  descriptive-only `secondary_tags`. `impact.py` is a thin wrapper —
  severity/direction map to a shock magnitude, then it calls
  `simulation.stress_test.apply_shock()` directly. There is exactly one
  shock-propagation implementation in the codebase; an event's impact *is* a
  stress test with the parameters derived instead of typed in.
- **Macro domain** (`domains/macro/`): a handful of seeded indicators (GDP,
  CPI, repo rate, 10Y G-Sec, INR/USD, crude, gold) as single current values,
  not a time series — nothing reads more than "the current value" (e.g. the
  risk engine's risk-free rate, `domains/risk/service.py::get_risk_free_rate_annual()`).
- **Admin domain** (`domains/admin/`): four read-only aggregate views (users,
  audit logs, AI tool-call usage, system health) behind
  `core/deps.py::get_current_admin_user` — an email allowlist
  (`ADMIN_EMAILS`), not a real roles/permissions system (see §9).
- **Paper trading engine** (`domains/paper_trading/`, Phase 4): market-order
  execution against a per-user virtual-capital account (`kind="paper"`),
  with realistic slippage (`pricing.py::apply_slippage`) and Zerodha-style
  brokerage (`compute_brokerage`). Reuses the existing `Holding`/
  `Transaction` models rather than inventing new ones — an order is just a
  cash-constrained, priced buy/sell against the same tables Phase 1's manual
  "Add holding" already writes to. `get_or_create_paper_portfolio()` is
  concurrency-safe: a real TOCTOU race (two requests both seeing "no account
  yet" and both inserting) was caught live during Phase 4 browser
  verification, fixed with a DB-level unique partial index
  (`ix_portfolios_one_paper_per_user`) plus an insert/catch/re-read pattern
  — see §9 and §11.
- **`BrokerAdapter`** interface (`domains/broker/adapter.py`, Phase 5) —
  mirrors the `ModelProvider` pattern: `MockBrokerAdapter` (checked-in
  default, simulates a connected account with a fixed seeded holdings set,
  zero external deps) and `ZerodhaKiteAdapter`
  (`domains/broker/zerodha_adapter.py`) implementing the real Kite Connect
  v3 OAuth handshake and REST calls against `https://api.kite.trade`,
  selected by `BROKER_PROVIDER`. Credentials/tokens are encrypted at rest
  (`core/crypto.py`, Fernet, `BROKER_ENCRYPTION_KEY`) — the first time this
  codebase encrypts anything beyond one-way password hashing. A connected
  broker's holdings sync into a per-user `kind="broker"` portfolio
  (`domains/broker/service.py::sync_holdings`) that exactly mirrors the
  broker's truth (upsert + delete stale rows) and is read-only in-app — see
  §9. Real order placement through a connected broker is gated behind
  `BROKER_LIVE_TRADING_ENABLED` (default `false`), independent of whether
  real credentials are configured.
- **Options pricing/Greeks engine** (`domains/options/`, Phase 6):
  closed-form Black-Scholes (`pricing.py`) — pure functions, fixture-tested
  against a published textbook reference value and exact algebraic
  identities (put-call parity, `delta_call - delta_put == 1`), not just
  eyeballed numbers. `service.py` generates a synthetic options chain
  on request (not persisted — see §9): a strike ladder around the live
  simulated spot price, an assumed volatility skew, and per-contract
  premium/Greeks priced off that. Deterministic per symbol+expiry (seeded
  RNG, same approach as `MockMarketDataProvider`). Read-only analysis
  only — no options positions, no paper trading of contracts, this phase.

## 5. Database

Dev default is **SQLite** (`aiosqlite`), zero install required. Production
target is **PostgreSQL** (`docker-compose.yml` provides it locally for anyone
with Docker). The schema is written using portable SQLAlchemy types
specifically so this swap is a connection-string change plus an Alembic
migration, not a rewrite — see the Trade-offs note below.

Tables: `users`, `user_preferences`, `portfolios` (now with a nullable
`cash_balance`, only used by `kind="paper"`, and unique partial indexes
enforcing one `paper` and one `broker` portfolio per user), `securities`,
`candles`, `holdings`, `transactions` (now with a nullable `order_id`),
`ai_sessions`, `ai_messages`, `ai_tool_calls`, `audit_logs`, `backtests`,
`events`, `macro_indicators`, `orders`, `broker_connections` (Phase 5 —
encrypted credential/token columns, never plaintext), `financial_statements`
(Tier 1 Session 2 — the point-in-time anchor is
`announcement_date`/`effective_date`, not `created_at`),
`corporate_actions` (Tier 1 Session 3 — same point-in-time anchor pattern),
`news_articles` (Tier 1 Session 4 — `content_hash` is the real dedup key,
`event_id` nullable FK set only when the classifier judged it market-moving),
`macro_indicator_releases` (Tier 1 Session 5 — additive alongside
`macro_indicators`, one row per (code, period, revision_number), point-in-time
anchor is `release_date`).
No speculative columns for unbuilt features (e.g.
no `broker_account_id` sitting unused on `portfolios`) — those get added
when the feature they support gets built. Phase 6 adds **no new table**:
options chains are computed on request, not stored — see §9.

## 6. Frontend architecture

- Next.js 16 App Router (Turbopack, React 19), TypeScript strict mode,
  Tailwind CSS v4.
- Design language: dark-first (and light-mode correct), data-dense, no
  gradients/glassmorphism/rounded gimmicks — closer to a terminal than a
  consumer SaaS dashboard.
- Design system components (`components/aparix/`): `AparixCard`,
  `AparixMetric`, `AparixBadge`, `AparixTable`, `AparixRiskIndicator`,
  `AparixComplexityControl`, `AparixCommandBar`, `AparixAIMessage`,
  `AparixHeatmap` (correlation/covariance matrices, Phase 2). Every screen is
  built from these, not one-off markup. `AparixCard`'s content wrapper is
  itself a flex column so a card can host a fixed-height scrollable region
  (the AI Terminal, e.g.) just by passing `className="flex flex-1 flex-col"`
  — but this means a lone non-form element (a bare `<button>`) inside a card
  will stretch to full width unless given `self-start`; a real bug from this
  surfaced once during Phase 2 (`/risk`'s "Run backtest" button) and was
  fixed rather than worked around.
- State: TanStack Query for all server state (portfolio, market data, AI
  sessions); a small Zustand store for local UI state (complexity level
  mirror, command bar open/closed, AI mode, and — Phase 6 — the selected
  portfolio for the header `PortfolioSwitcher`).
- **Multi-portfolio** (Phase 6): `GET /portfolios` already returned every
  portfolio a user owns since Phase 1 (no backend work needed) — the gap was
  the frontend hard-locking to `portfolios.data[0]`. `usePrimaryPortfolio()`
  (`lib/use-portfolio.ts`) now resolves the switcher's selection instead,
  falling back to the first portfolio if nothing's chosen (or the selection
  no longer exists). Paper trading and broker accounts are excluded from the
  switcher (`isSwitchablePortfolio()`) — they have their own dedicated pages
  and a different account shape (cash-based / broker-synced), not something
  to "switch into" alongside a user's own long_term/trading/options/
  experimental portfolios.
- Every value sourced from mock data carries a visible "DEMO DATA" /
  "SIMULATED" tag in the UI — non-negotiable per the product's anti-faking
  principle (§8).

## 7. AI architecture detail

`get_model_provider()` (`domains/ai/provider.py`) branches on
`settings.ai_provider` — `"mock"` (checked-in default) → `MockModelProvider`,
`"ollama"` → `OllamaModelProvider`. Everything above that branch (the router,
session/message persistence, `ai_tool_calls`, the frontend) is identical
either way.

```
User message → /api/v1/ai/chat
             → get_model_provider().respond()
                 mock:   keyword matching resolves intent, fills a template
                 ollama: real agentic tool-calling loop against Ollama's
                         /api/chat "tools" API (domains/ai/ollama_provider.py)
                 → tool executes against real DB-backed portfolio/market data
                 → ai_tool_calls row persisted (tool name, args, result)
                 → response text — templated (mock) or model-generated (ollama)
             → ai_messages row persisted (role, content, linked tool calls)
             → response returned to client
```

**Tool registry** (`domains/ai/tools.py`, 16 tools): `get_portfolio`,
`get_holdings`, `get_sector_exposure`, `get_market_data` (Phase 1);
`get_risk_profile`, `run_stress_test`, `run_monte_carlo`, `run_backtest`
(Phase 2); `get_events`, `get_event_impact`, `get_macro_indicators`
(Phase 3); `preview_trade`, `evaluate_order` (Phase 4 — the AI trading
coach); `get_broker_holdings` (Phase 5); `get_options_chain`, `price_option`
(Phase 6). Both providers call the exact same functions — one JSON-schema
description per tool for the LLM (`domains/ai/tool_schemas.py`), checked
against `TOOL_REGISTRY` at import time (`assert_schemas_match_registry()`)
so a tool added to one without the other fails loudly at startup, not
silently at runtime. `preview_trade`/`evaluate_order`/`get_broker_holdings`
all deliberately ignore which portfolio the AI Terminal session is scoped
to and resolve the user's paper trading or broker account instead (via the
active portfolio's `user_id`) — those are the only accounts real/simulated
orders and real broker holdings resolve against, regardless of which
portfolio the conversation happens to be discussing. `get_broker_holdings`
returns an honest error (not a fabricated empty list) when no broker is
connected. `get_options_chain` truncates to the 10 strikes nearest the
money and says so (`note` field) — a full chain (17 strikes × 2 types) is
more than a model needs for a typical question, the same "sensible default,
state it" pattern `get_macro_indicators_tool` already used.

**`OllamaModelProvider`** (`domains/ai/ollama_provider.py`, Phase 3.5): a
real agentic loop, capped at `MAX_TOOL_ROUNDS=4` — model returns tool_calls,
each executes for real, results feed back as `role: "tool"` messages, repeat
until the model returns plain text. A mode-specific system prompt
(`MODE_INSTRUCTIONS`) makes `simple/quant/analyst/risk_officer/
portfolio_manager/macro_economist/options_specialist` genuinely different
response styles from one model, not hand-written templates — Phase 6 moved
`options_specialist` from the honest-decline fallback into this real list
now that `get_options_chain`/`price_option` exist. `researcher` is now the
only mode still declining (no RAG/document store exists to back cited
research). `GET /api/v1/ai/config` exposes which provider/modes are
actually live so the frontend's mode switcher never overclaims what a
given provider can do — the `options_specialist` badge automatically
stopped showing "Coming soon" the moment the backend registered it, no
frontend change needed.

The **mock router** stays exactly as simple as before (keyword matching, a
handful of supported questions, sensible stated defaults for tool
parameters it can't parse from free text) — it's not being extended, per
§11's original note; it exists so the repo runs with zero external services.

**AI-triggered backtests** are computed but not saved to `backtests`
(`persist=False`) regardless of provider, so idle questions don't clutter
the user's saved run history; explicit runs from `/risk` are saved.

## 8. Financial AI safety

- No guaranteed/certain/risk-free language anywhere in copy or templates.
- Every AI-stated number must trace to an `ai_tool_calls` row.
- Mock data is never presented as live. Unimplemented features say
  `COMING SOON`, not a fabricated result.
- The product performs analytics/education, simulated paper trading, and
  read-only options analysis (Phase 6 — chain/Greeks only, no options
  positions or trading) — no real broker connection or real order execution
  exists (Phase 4's "orders" execute against a virtual-capital account,
  never real money), so no execution-related compliance surface exists yet.
  This is a deliberate
  regulatory boundary, not a gap: broker integration (Phase 5) is the point
  where compliance/legal review becomes required before anything resembling
  real advice or execution ships.

## 9. Trade-offs made explicit

| Decision | Choice | Why | Consequence |
|---|---|---|---|
| Dev database | SQLite for local dev | No Docker/Postgres available in the build environment; spec requires the app to run with zero paid/external deps | Prod uses Postgres; schema kept portable; Alembic migration documents the swap |
| Monorepo tooling | npm workspaces, no Turborepo/pnpm | pnpm not installed; avoids adding infra before it's needed | Two dev commands instead of one; documented in README |
| Redis / Kafka | Deferred | Nothing built so far needs caching or a message bus | `docker-compose.yml` has Redis commented out |
| AI provider (checked-in default) | Mock, behind `ModelProvider` interface | No paid LLM dependency for local dev/demo out of the box | `OllamaModelProvider` (Phase 3.5) proved the interface — an `AnthropicModelProvider` would be the same shape, one new file |
| Charting | Recharts only | Candlestick charts belong to a future Markets page; Phase 6's options page uses a 2D IV-vs-strike line chart, not a 3D vol surface, for the same reason (see the Phase 6 row below) | No TradingView-class library pulled in yet |
| VaR/CVaR method (Phase 2) | Historical simulation (empirical percentile of actual returns), not parametric | No distributional assumption — consistent with never faking numbers | Needs real sample size; below 20 observations the API returns `null`, not a number computed from noise — surfaced in the UI as an explicit "not enough history" state |
| Risk-free rate | Sourced from the mock `macro_indicators.gsec_10y` row (Phase 3), falling back to the 6.5% constant | Phase 3 added the macro domain, giving this a proper home | Still the same 6.5% mock value, still not RBI-fetched — a structural improvement, not a data-freshness one (documented in the UI, not oversold) |
| Monte Carlo method (Phase 2) | GBM and historical bootstrap, both portfolio-level (not multi-asset correlated) | Simplest two defensible methods; a covariance-aware multi-asset simulator is a bigger build | Every result states which method and its assumptions; correlation/covariance *are* computed and shown separately on `/risk`, just not fed into the simulator yet |
| Backtesting scope (Phase 2) | Buy-and-hold of current weights only, no strategy DSL, no costs modeled | No strategy/signal engine exists; building one is its own project | Framed as "how would today's portfolio have performed," not a trading-strategy backtester |
| Stress testing scope (Phase 2) | Synthetic/custom shocks only (target + %), propagated via beta or direct match | No real historical crisis data exists in this system — fabricating "2008 GFC" numbers would violate §8 | Historical scenario buttons are visibly `COMING SOON` on `/risk` until real historical data ingestion exists (Phase 3+) |
| Event → entity mapping (Phase 3) | Tag-based (`primary_target`: one sector, symbol, or `"NIFTY50"`) instead of a graph DB | A full Company/Sector/Commodity/Country graph with typed multi-hop edges (per the original spec) is a much bigger build than one event → one quantified impact needs | Impact math reuses `apply_shock()` — one target, one shock, no multi-hop propagation. Not the "financial knowledge graph" vision, and not presented as such |
| Event impact magnitude (Phase 3) | `severity` (low/med/high → ±3/±7/±15%) × `direction` (sign) | No historical calibration data exists to derive real magnitudes | Every response states this is a severity-based estimate, not a calibrated forecast |
| Event content (Phase 3) | Negative/high-severity events stay impersonal (sector-wide, macro, weather-on-operations); no fabricated misconduct/fraud tied to a real named company | Demo data implying wrongdoing by a real company (RELIANCE, HDFCBANK, etc.) risks real reputational harm if taken out of context, even clearly labeled | The one company-specific negative event mirrors the product spec's own Jamnagar-flooding example — weather disrupting operations, not an accusation |
| RAG / document retrieval | Still not built | RAG's value is entirely LLM-consumed retrieval + generation; building a document store nothing calls yet is speculative work ahead of need | Now that a real model exists (Phase 3.5), this is unblocked whenever it's actually wanted — see roadmap |
| Admin access control (Phase 3) | Email allowlist (`ADMIN_EMAILS`), checked dynamically via `User.is_admin` property — no stored role/permission model | No RBAC system exists; four read-only views don't need one yet | A real roles/permissions system is still a future security-hardening item, not solved here |
| LLM provider choice (Phase 3.5) | Local Ollama (`llama3.1`), not the Anthropic API | User's explicit choice — already installed, zero cost, fully private, matches this project's "no paid dependencies" default | Meaningfully weaker tool-calling reliability than a frontier model (see next two rows) — a real, known cost of this choice, not hidden |
| Checked-in AI default (Phase 3.5) | Stays `AI_PROVIDER=mock` in `.env.example` | The repo must still run with zero external services for anyone who clones it without Ollama installed | This developer's local `apps/api/.env` (gitignored) sets `AI_PROVIDER=ollama` — a per-environment choice |
| Hallucination guardrail (Phase 3.5) | Zero-tool-calls-but-response-has-numbers → append a caveat. Not a full per-number cross-check | A real per-number matcher has to tolerate reformatting (84398.4 vs "84,398") and would false-positive on nearly every response — worse than no guardrail | Best-effort, not exhaustive — documented as such. "View data source" (unchanged) is the actual verification path: the real tool JSON is always visible |
| Described-tool-call repair (Phase 3.5) | Detect when the model writes a tool call as JSON-ish text instead of using Ollama's native mechanism, nudge it once to actually call the tool | Observed live during Phase 3.5 verification: `llama3.1` did this on a compound two-part question — not hypothetical | Costs one of the 4 tool-call rounds; if it happens twice in one conversation the second attempt still degrades to an honest message, never fabricated data |
| Slippage model (Phase 4) | Randomized 0.05–0.15% spread applied at fill time, always unfavorable (buys fill above quote, sells below) | No real order book exists to derive slippage from; a simple, directionally-honest approximation | Every order/preview response states the exact slippage applied in ₹ and %, never hidden inside the fill price |
| Brokerage model (Phase 4) | Zerodha-style: ₹20 flat or 0.03% of order value, whichever is lower, per executed order | A recognizable, realistic Indian discount-broker convention, kept as a named constant (`domains/paper_trading/pricing.py`) rather than an unexplained magic number | Documented as illustrative, not a claim about this app's real pricing — it's a paper account |
| Manual "Add holding" vs. paper orders (Phase 4) | Two separate flows stay separate: Phase 1's manual entry is unchanged and still used by `long_term`/`trading` portfolios; `domains/paper_trading` owns cash-constrained buy/sell for `kind="paper"` portfolios only | Different semantics — manual entry is "declare what I already own," an order is "simulate executing a trade right now"; conflating them would blur what's being tested | A `paper` portfolio can't use "Add holding," and a non-paper portfolio has no `cash_balance` and can't place orders — enforced in each router |
| Paper portfolio creation (Phase 4) | Lazily created (seeded with ₹10L virtual capital) the first time `get_or_create_paper_portfolio()` is called, not at onboarding | Avoids cluttering onboarding with a decision most users won't touch immediately | First `/paper` visit (or first AI coach question about a trade) silently provisions the account — no separate "set up paper trading" step |
| Post-trade coach scope (Phase 4) | Immediate entry-quality evaluation only — fill price vs. the last 30 trading days' range, not "how did this trade turn out" | No scheduled/delayed re-evaluation mechanism exists in this codebase | `evaluate_order`'s response explicitly states it isn't judging the eventual outcome — the spec's fuller delayed-review vision is future work, not faked with a placeholder number |
| Paper-portfolio concurrency fix (Phase 4) | DB-level partial unique index (`ix_portfolios_one_paper_per_user`) plus catch-`IntegrityError`-and-re-read in `get_or_create_paper_portfolio()`, instead of relying on application-level locking | A real race was hit live during Phase 4 browser verification: `/paper`'s `portfolio` and `orders` queries both call the same "get or create" function independently on page mount, and without synchronization both could see "none exists" and both insert, corrupting the account into two rows and crashing later lookups with `MultipleResultsFound` | Any future "get or create" style idempotent operation in this codebase should use the same pattern (unique constraint + catch + re-read), not assume a single caller — see §11 |
| Broker Kite Connect testing (Phase 5) | `ZerodhaKiteAdapter` built to the documented Kite Connect v3 API contract (httpx calls, no vendor SDK), but never exercised against a live account | Kite Connect requires a paid (₹2000/mo) developer subscription and a registered app — not available in this build environment | Treat it as "implemented to spec, unverified" — wire in real `ZERODHA_API_KEY`/`ZERODHA_API_SECRET` and do a real connect + holdings sync before trusting it in production |
| Broker credential encryption (Phase 5) | Application-layer Fernet symmetric encryption (`core/crypto.py`, `BROKER_ENCRYPTION_KEY`), not DB-level encryption | SQLite has no column-level encryption, and this needs to behave identically once Postgres is swapped in — encrypting in Python before the value ever reaches the DB works the same either way | A `/broker/connect` call fails loudly (`EncryptionNotConfiguredError`) rather than silently storing a plaintext credential if the key isn't set |
| Live broker trading gate (Phase 5) | `BROKER_LIVE_TRADING_ENABLED` defaults to `false`, independent of whether real Zerodha credentials are configured | Real order placement through a connected broker is real money — the spec itself calls out that broker integration is where compliance/legal review becomes required before anything ships live; having valid API credentials shouldn't be the only gate | The mock adapter's `place_order()` always returns "rejected" too — there is no path in this codebase today that executes a real trade without a second, explicit environment flag flip |
| Broker holdings pricing (Phase 5) | A synced broker holding's live price/P&L still comes from this app's own simulated market data, not Zerodha's real quotes | Phase 1's mock market data is the only live pricing feed that exists in this codebase — Kite Connect's own quote/streaming API isn't wired in this phase | A broker-synced position's *quantity and average price* are real (from the broker), but its *current price and P&L* are simulated — stated in the UI via the Demo Data badge, not conflated as fully real |
| Broker holdings outside the seeded universe (Phase 5) | A real broker holding in a symbol outside this app's seeded NIFTY-subset securities is skipped during sync, reported back as `skipped_symbols`, not fabricated a price for | This app can only price/analyze the ~20 seeded securities (see §11) | A real Zerodha account holding e.g. a small-cap or ETF outside that set will show fewer synced positions than the real account has — an honest, visible limitation, not silently wrong totals |
| Broker portfolio is read-only in-app (Phase 5) | No "Add holding" equivalent for `kind="broker"` portfolios — the only way its holdings change is a Sync | A broker portfolio's whole purpose is mirroring an external source of truth; a manually-edited row would silently drift from what the broker actually shows | Same restriction pattern as `kind="paper"` (Phase 4) applied consistently to the new kind |
| Options data model (Phase 6) | Not persisted — chains/Greeks computed on request from the live simulated spot price and an assumed IV, using closed-form Black-Scholes | A chain is combinatorial (strikes × expiries × 2 types) and fully derived; persisting it would misrepresent computed numbers as an independently observed feed | Deterministic per symbol+expiry (seeded RNG) but there's no "options candle history" table — honest, since none is fabricated |
| Options volatility surface (Phase 6) | A synthetic, deterministic skew — higher IV for strikes below spot — as a function of moneyness; assumed, not solved from real prices | No real options market exists to calibrate against; "implied" vol computed from nothing would be circular | Every contract states `iv_pct` is assumed, mirroring how the mock risk-free rate is already labeled (§9 above) |
| Options expiry calendar (Phase 6) | A small synthetic set of near-term Thursdays (`list_expiries()`), not NSE's real weekly/monthly expiry rules (holiday adjustments, index-vs-stock differences) | Reproducing NSE's actual calendar is a data-ingestion problem, not a pricing one | Plausible dates, not guaranteed to match a real NSE expiry |
| Options trading scope (Phase 6) | Read-only chain/Greeks analysis only — no options positions, no options paper trading, no exercise/assignment mechanics | The equities-only paper trading engine (Phase 4) has no concept of options margin, exercise, or expiry settlement — building that is a project of its own | The `kind="options"` portfolio value (present in the schema since Phase 1) stays unused; the AI's `options_specialist` mode is explicitly instructed never to imply the user holds a position |
| Vol surface visualization (Phase 6) | A 2D IV-vs-strike line chart (Recharts), not a 3D strike × expiry × IV surface | Recharts doesn't support 3D, and pulling in a second charting library conflicts with the standing "Recharts only" decision (§9 above) | "Vol surfaces" in the roadmap description ships as this 2D analog, not the literal 3D chart |
| Institutional dashboards (Phase 6) | Scoped down to multi-portfolio (still single-user) instead of true multi-client | "Institutional" in the original spec implies an advisor managing multiple *clients'* accounts, which needs a Client/Advisor relationship model that doesn't exist anywhere in this codebase; building one is a separate, bigger project | What shipped instead: a header portfolio switcher plus an "All portfolios" aggregate view (`/portfolio`) — real value for one user with several portfolios, not the full institutional/family-office vision |
| Public APIs and billing tiers (Phase 6) | Deferred entirely, not stubbed | No external API consumer or tier-gated feature exists yet to justify either; an unused `tier` column or API-key auth surface would be speculative work ahead of need (the same reasoning RAG was deferred under until Phase 3.5 gave it a consumer) | JWT-only auth remains the only auth mechanism; revisit if/when there's an actual external caller or a concrete feature to gate |
| Fundamentals statement shape (Tier 1 S2) | One wide `financial_statements` row per (security, period_end, period_type) with explicit named columns, not a normalized line-item table | Matches the spec's own enumerated field list directly; avoids pivot-query complexity for a dataset this size | Reconsider only if the line-item set needs to grow dynamically later |
| Fundamentals generation anchored to price (Tier 1 S2) | Revenue/PAT/equity derived backward from the security's actual mock price via a target P/E and target ROE, not generated independently | An earlier version generated financials independent of price and produced a P/E of ~1667 for a ~₹3000 stock — internally consistent (every ratio traced correctly) but implausible on sight, a real bug caught during live verification, not a hypothetical | Every ratio lands in a believable band by construction; a quarterly statement's balance-sheet items are sized off *annualized* revenue (equity is a snapshot, not a flow that shrinks to a quarter's size), and valuation ratios annualize flow figures (×4 run-rate) before comparing them to price |
| Fundamentals announcement lag (Tier 1 S2) | `effective_date` = `announcement_date` ≈ `period_end` + 45–60 days (annual), + 30–45 days (quarterly) | Approximates real Indian corporate reporting timelines without claiming to model any specific company's actual filing calendar | Creates a real, testable gap between "period ended" and "publicly known" — the exact window `tests/test_point_in_time_integrity.py` checks isn't leaked |
| Point-in-time price (Tier 1 S2) | Historical `Candle` close nearest `as_of` for a past date; live spot only when `as_of` is today/omitted | Consistent point-in-time discipline on both sides of every ratio, not just the fundamentals half | A ratio computed for a past `as_of` never mixes a historical statement with today's price |
| `Candle.close` convention (Tier 1 S3) | Treated as already-adjusted; corporate actions are historical records, not retroactive price rewrites | Matches how most real market-data feeds present "Close" by default; avoids corrupting existing portfolios/risk/backtest results for currently-tradable mock securities | The mock series correctly shows no artificial discontinuity around a seeded split/bonus — that absence *is* the adjustment, not a gap |
| Corporate action adjustment scope (Tier 1 S3) | `adjust_price_series()` built and fixture-tested against a synthetic constructed series (a real embedded split discontinuity), not applied to the live seeded universe | Proves the algorithm correct without touching real (if mock) non-disposable local data other features already depend on | Applying it live to this dataset is future work |
| Disruptive corporate action types (Tier 1 S3) | `merger`/`demerger`/`symbol_change`/`isin_change`/`delisting` supported as schema + adjustment logic, tested via synthetic fixtures only — never seeded against a currently-tradable security | Seeding these against the live universe would break existing paper trading/portfolio/backtest flows for no real benefit | Full survivorship-bias/point-in-time security universe support remains separate future work |
| News source choice (Tier 1 S4) | RBI's official press-release RSS feed, not Google News RSS | Google News' own feed copyright explicitly forbids anything beyond "personal, non-commercial" feed-reading — checked directly by fetching it, not assumed. RBI's feed reserves copyright too, but press releases from a financial regulator are issued for public dissemination/news reporting, a materially different posture — see `docs/DATA_LICENSING.md` | Classified `REQUIRES_ATTRIBUTION`, not `PUBLIC` — every article stores/shows a real publisher attribution and links back to RBI's own page, never reproduces full release text |
| News classification (Tier 1 S4) | A small deterministic keyword-rule table (`domains/news/classifier.py`), not an ML/LLM classifier | Transparent and testable against exact fixture inputs; an LLM-based classifier's output can't be fixture-tested the same way and would be a second, less explainable path to "what counts as a market event," alongside the already-existing hand-seeded `SEED_EVENTS` | Real, live RBI content on a given day is very often entirely routine (VRRR auctions, forex reserve reports) and correctly produces zero classified events — verified live, not assumed; the classifier doesn't force significance onto routine content |
| Real ingestion gated off by default (Tier 1 S4) | `NEWS_PROVIDER=mock` checked in; `=rss` (real, live, opt-in) also activates a periodic background fetch loop | Matches every other provider in this codebase (`AI_PROVIDER`, `BROKER_PROVIDER`, `MACRO_PROVIDER`, `FUNDAMENTALS_PROVIDER`, `CORPORATE_ACTIONS_PROVIDER`) — zero external dependency for a fresh clone, real capability one setting away | A cold fresh clone never contacts RBI's servers unless a developer explicitly opts in |
| Macro vintage scope (Tier 1 S5) | Real revision/vintage history generated only for `cpi_inflation` and `gdp_growth` — the other 5 seeded indicators (repo rate, 10Y G-Sec, INR/USD, Brent crude, gold) get none | These 5 are continuously market-quoted rates/prices, not periodically-revised government statistics — India's MOSPI genuinely does revise CPI and GDP (advance → provisional → final); fabricating a "revision history" for a live-quoted FX rate would be precision that data doesn't have | `GET /macro/indicators/{code}/history` returns 404 (not an empty fake list) for a non-revised indicator, naming exactly which two codes do have history |
| `MacroIndicator` left untouched (Tier 1 S5) | New `macro_indicator_releases` table added alongside the existing single-current-value `MacroIndicator` table, not a replacement | Every existing caller (risk-free rate lookups, the AI's `get_macro_indicators` tool, `/home`'s macro card) keeps working unchanged; the vintage table is purely additive | Two tables now answer related but different questions — "what's the reading right now" (`MacroIndicator`) vs. "what would a query dated X have known, including which figures were later revised" (`MacroIndicatorRelease`) |
| RAG corpus scope (Tier 1 S6) | Indexed corpus is ingested news articles only — no document-upload model, no PDF/filing ingestion, no broader knowledge-graph corpus | News ingestion (S4) is the one genuinely real, not fabricated, document domain this codebase has; inventing a larger synthetic corpus just to make RAG "look" more complete would itself be exactly the kind of fake functionality this project's discipline prohibits | `search_knowledge_base` and the `researcher` AI mode are honest about the limitation — both the tool description and the mode's system-prompt instruction state the corpus is news-only |
| Embedding provider default (Tier 1 S6) | `EMBEDDING_PROVIDER=hashing` (feature-hashing bag-of-words, zero external dependency) checked in; `=ollama` (real dense embeddings via a locally running `nomic-embed-text`) opt-in | Same "mock/zero-dependency default, real opt-in upgrade" pattern as every other provider in this codebase; unlike most "mock" defaults, hashing is a real algorithm over real ingested text, not fabricated/random — see `domains/rag/embeddings.py` | Weaker than a dense embedding at synonyms/paraphrases (exact shared vocabulary drives the score) — documented directly in the `researcher` mode's system-prompt instruction, not silently assumed to be equivalent |
| No ANN vector index (Tier 1 S6) | Full-scan cosine similarity over all indexed documents (`domains/rag/analytics.py`), no FAISS/pgvector/etc | Genuinely correct at the current corpus size (tens of rows) — an ANN index would be complexity with no benefit yet, same reasoning as `check_candle_integrity()`'s documented full-table-scan limitation | Explicitly flagged in `domains/rag/analytics.py`'s docstring as real future work before a much larger corpus makes a full scan slow, not silently left unscoped |
| Guardrail widened to cover failed tool calls (Tier 1 S6) | `_apply_guardrail()` (`domains/ai/ollama_provider.py`) now treats an attempted-and-failed tool call the same as no tool call at all, not just "any tool call was attempted" | Caught live during this session's own verification: a malformed `top_k` argument crashed `search_knowledge_base` twice, and llama3.1 answered anyway with three entirely invented publisher names/titles/scores — the old guardrail didn't flag it because *a* tool call existed, even though none succeeded | `tests/test_ollama_provider.py::test_guardrail_flags_a_response_built_on_only_failed_tool_calls` is a regression test for this exact scenario, not a hypothetical one |
| Self-role-change blocked entirely (Tier 1 S7) | `PATCH /admin/users/{id}/role` rejects a target `user_id` equal to the caller's own, for every role, not just a downgrade | A compromised or careless admin session changing its own role (accidental self-lockout, or a compromised token self-escalating) is a real risk a second admin's involvement removes | `tests/test_role_management.py::test_cannot_change_own_role`; the frontend also disables the control on the admin's own row, though the server check is the actual guard |
| Only super_admin can touch super_admin (Tier 1 S7) | A plain `admin` can grant/revoke any role except `super_admin`, and cannot change an existing `super_admin`'s role at all | Letting a lower-privileged admin mint or strip the platform's highest privilege would defeat having tiers at all | `tests/test_role_management.py::test_plain_admin_cannot_grant_super_admin`, `test_plain_admin_cannot_change_an_existing_super_admins_role` |
| Fictitious historical securities (Tier 1 S8) | The 2 seeded historical-only securities (`ORIONINFRA`, `VELOCFIN`) are invented companies, not real ones | A delisting/merger is a specific, checkable real-world fact; asserting a real Indian company was delisted/merged on a synthetic date this app invented would be a factual claim with no basis — every other seeded security uses a real company's identity, but only for synthetic *price* data, never a synthetic *corporate event* |  |
| `list_securities()` default excludes non-tradable (Tier 1 S8) | Every existing caller (frontend dropdowns, live tick seeding, fundamentals/corporate-actions' own seeding queries) keeps returning only the live tradable universe by default; `include_delisted=True` is opt-in | Adding historical-only securities must never silently change what "all securities" means to code written before they existed — live-verified via Playwright that `/portfolio`/`/options`/`/fundamentals` dropdowns are unaffected | `tests/test_survivorship_bias.py::test_live_universe_excludes_historical_securities`, `test_get_securities_endpoint_excludes_historical_securities` |
| Hand-rolled rate limiter, not a package (Tier 1 S9) | `FixedWindowRateLimiter` — a plain in-memory dict, no `slowapi`/Redis dependency | Small enough to own directly and correctly, same reasoning as every hand-rolled point-in-time query in this codebase; a real dependency would also imply a shared/multi-process store this app doesn't have | Real, live-verified 429s with a real `Retry-After` — not a stub; documented as single-process-only, matching this app's actual (single-process) architecture |
| Exception handler sets its own `X-Request-ID` header (Tier 1 S9) | `unhandled_exception_handler()` sets the header directly rather than relying on `RequestIDMiddleware` | A handler registered for the bare `Exception` type runs in Starlette's `ServerErrorMiddleware`, outside `RequestIDMiddleware` — a response built there never passes back through that middleware's own header-attachment line | Caught by a genuine failing test (`KeyError: 'x-request-id'`), not predicted — `tests/test_middleware.py::test_unhandled_exception_returns_a_sanitized_response_with_the_request_id` |

## 10. Roadmap

**Phase 1 — Foundation** (done): auth, adaptive dashboard, portfolio engine,
mock market data, AI Terminal with tool-calling.

**Phase 2 — Quant** (done, scoped — see §9 trade-offs for what's deliberately
left out): historical VaR/CVaR, Sharpe/Sortino, max drawdown, correlation/
covariance matrices (`domains/risk`); Monte Carlo (GBM + bootstrap), custom
stress testing, buy-and-hold backtesting (`domains/simulation`); all four
wired into the AI tool registry and the `/risk` workspace. Deliberately not
built: factor models, regime detection, a historical crisis scenario
library, multi-asset correlated Monte Carlo, a strategy DSL for backtesting
— each needs a data source or engine this phase doesn't have (see §9).

**Phase 3 — Event Intelligence** (done, scoped — see §9): seeded mock events
mapped to sectors/symbols/NIFTY, portfolio-impact calculation reusing the
Phase 2 stress-test engine (`domains/events`); a mock macro domain now backs
the risk-free rate (`domains/macro`); a read-only admin dashboard
(`domains/admin`) — users, audit logs, AI tool usage, system health. Three
new AI tools registered. Deliberately not built this phase: RAG over
filings/announcements (no LLM to consume it yet at the time), a full
entity/relationship graph (tag-based mapping used instead), real news
ingestion (no API key — seeded mock data instead), real RBAC (an email
allowlist stands in for it).

**Phase 3.5 — Wire the LLM** (done): `OllamaModelProvider`
(`domains/ai/ollama_provider.py`) — a real agentic tool-calling loop against
local `llama3.1`, using the identical `TOOL_REGISTRY` every prior phase
built and tested. Six AI modes were now real style variants from one model
(`simple/quant/analyst/risk_officer/portfolio_manager/macro_economist`);
`options_specialist`/`researcher` still honestly declined at the time —
`options_specialist` became real in Phase 6 once options tools existed to
back it; `researcher` still honestly declines (see Phase 6 below). A best-effort
hallucination guardrail and a described-tool-call repair loop (found live
during verification — see §9) harden it against the specific ways an 8B
open model is less reliable than a frontier one. `MockModelProvider` is
unchanged and stays the checked-in default. Not done: RAG (now unblocked —
a real model exists to consume it, just not built yet), the Anthropic
provider (same interface, not implemented).

**Phase 4 — Paper trading** (done, scoped — see §9): a real order-execution
simulator (`domains/paper_trading`) — market-order-only buy/sell against the
existing mock live price, cash-constrained, with randomized slippage and
Zerodha-style brokerage; a lazily-created paper `Portfolio` (`kind="paper"`)
seeded with ₹10L virtual capital; two new AI tools (`preview_trade` — a
what-if impact preview with no DB writes, `evaluate_order` — post-trade
entry-quality evaluation vs. the 30-day price range), both reachable from
the `MockModelProvider` keyword router and, for free via the shared
`TOOL_REGISTRY`, from `OllamaModelProvider`; a `/paper` order-ticket page
with a live preview-before-you-commit flow and per-order "Ask coach"
handoff into the AI Terminal. A real concurrency bug (two racing "get or
create paper portfolio" calls producing duplicate accounts) was caught live
during browser verification and fixed with a DB-level unique index — see
§9 and §11. Deliberately not built: limit/stop orders, partial fills or
order-book depth, margin/leverage, delayed/retrospective outcome tracking
("how did this trade turn out"), and gamification/leaderboards (the spec
itself flags trade-volume rewards as risky) — each needs infrastructure
this phase doesn't have or was explicitly avoided as a bad incentive.

**Phase 5 — Brokerage** (done, scoped — see §9): `BrokerAdapter` interface
(`domains/broker/adapter.py`) mirroring `ModelProvider`'s pattern —
`MockBrokerAdapter` (checked-in default, simulated connected account) and
`ZerodhaKiteAdapter` (real Kite Connect v3 REST calls, built to spec but not
live-tested — no real credentials available in this environment); broker
credential/token isolation via application-layer Fernet encryption
(`core/crypto.py`, the first encryption-at-rest in this codebase); a
lazily-created, sync-only `Portfolio` (`kind="broker"`) that mirrors the
connected broker's real holdings exactly (upsert + delete-stale); one new
AI tool (`get_broker_holdings`); a `/broker` page (connect/sync/disconnect,
read-only holdings table, AI coach handoff). Real order placement through a
connected broker is implemented (`POST /broker/orders`) but gated behind
`BROKER_LIVE_TRADING_ENABLED=false` by default, independent of whether real
credentials are configured — flipping it on is the compliance/legal-review
gate the original spec calls for, not a side effect of setup. Deliberately
not built: non-Zerodha brokers, Kite's WebSocket live-tick/order-postback
streams (reuses the existing polling quote pattern instead), margin/
leverage visibility, and multi-broker-per-user support (one connection per
broker per user, enforced by a DB-level unique index).

**Phase 6 — Professional** (done, scoped — see §9; the last roadmap phase):
a read-only options analysis engine (`domains/options/`) — closed-form
Black-Scholes pricing/Greeks (`pricing.py`, fixture-tested against a
published reference value and exact identities), synthetic options chains
generated on request (not persisted) around the live simulated spot price
with an assumed volatility skew; a `/options` page (chain table, 2D
IV-vs-strike smile chart); two new AI tools (`get_options_chain`,
`price_option`) and a real `options_specialist` AI mode (previously an
honest-decline stub). Multi-portfolio support: a header portfolio switcher
and an "All portfolios" aggregate view (`/portfolio`), built almost
entirely on the frontend since `GET /portfolios` already supported multiple
portfolios per user since Phase 1. Deliberately not built: options
*trading* (no positions, no exercise/assignment), index options (chains
work for any seeded symbol including `NIFTY50`/`BANKNIFTY` since they
already have simulated quotes — this was originally planned as deferred,
turned out to already work for free), a full 3D vol surface, true
multi-client institutional dashboards, public APIs, and billing tiers —
the last four have no existing data model or consumer to build on and
would be speculative work (see §9).

## 11. Known technical risks

- Python 3.14 is very new in this environment; dependency versions in
  `apps/api/pyproject.toml` should be re-verified against latest compatible
  releases if install fails.
- SQLite does not enforce the same concurrency/constraint behavior as
  Postgres — integration tests against SQLite are a stand-in, not a
  substitute for testing against Postgres before production deploy.
- `MockModelProvider`'s intent resolution is rule-based, not model-driven —
  that's permanent, not a placeholder anymore (`OllamaModelProvider` is the
  real path now; the mock one exists purely so the repo runs with zero
  external services).
- The mock market data generator seeds ~365 calendar days (~250-260 trading
  days) per security. That's enough for a meaningful 95% VaR/CVaR sample but
  thin for 99% (only a handful of tail observations) — real values, not
  fabricated ones, but treat 99% VaR/CVaR as low-confidence until Phase 3+
  brings deeper historical data.
- Any time-series line/area chart needs an explicit, data-driven Y-axis
  `domain` (see `tightDomain()` in `apps/web/app/(dashboard)/risk/page.tsx`).
  Recharts' default 0-anchored axis squashes a portfolio-value series that
  moves a few percent around ~₹1 lakh into an unreadable sliver — this was a
  real bug caught during Phase 2 browser verification, not a hypothetical.
- `ADMIN_EMAILS` is read once via `get_settings()` (`@lru_cache`) — changing
  it requires an API process restart, not just editing `.env`. The tests in
  `tests/test_admin.py` clear that cache explicitly (`config.get_settings.cache_clear()`);
  do the same if you ever need to change it programmatically rather than by
  restart.
- Portfolio-derived React Query caches (analytics/holdings/risk) share the
  `["portfolio", id, ...]` key prefix specifically so one
  `invalidateQueries({queryKey: ["portfolio", id]})` call invalidates all of
  them (see `apps/web/lib/use-portfolio.ts`). A real bug in Phase 2 came from
  independent keys — a new query got left out of a hand-written invalidation
  list. Any new portfolio-derived query (events/macro don't need this today,
  since they aren't portfolio-scoped) should join that same prefix, not
  invent its own key.
- `OllamaModelProvider` requires `ollama serve` running locally and
  `OLLAMA_MODEL` (default `llama3.1`) pulled. A cold model load is ~15s on
  the first request of a session (subsequent requests are ~1-10s depending
  on question complexity) — `httpx.AsyncClient` timeout is set to
  `OLLAMA_REQUEST_TIMEOUT_SECONDS` (default 60s) to accommodate this; raise
  it if a slower machine times out on first load.
- A local 8B model can, on a compound/multi-part question, write a tool
  call out as JSON-ish text instead of using Ollama's native `tool_calls`
  field. `_looks_like_described_tool_call()`
  (`domains/ai/ollama_provider.py`) catches the common pattern and nudges
  the model once — but this is a regex heuristic against one observed
  failure shape, not a formal guarantee it catches every variant. If you
  see a raw-JSON-looking response in the AI Terminal, that heuristic missed
  a new shape of the same failure mode; extend the regex, don't add a
  second detection mechanism.
- `Base.metadata.create_all()` (`core/db.py::init_models()`) only creates
  tables that don't exist yet — it does **not** add new columns to an
  already-existing table. This has bitten the persistent local dev DB
  twice now (adding `cash_balance`/`order_id` in Phase 4 required a one-off
  `ALTER TABLE` migration script, not just a server restart). Alembic is
  scaffolded but not wired into the dev startup path; any future column
  addition to an existing model needs either a manual migration against
  the existing `aparix_dev.db` or an Alembic migration before it'll take
  effect for anyone with a pre-existing database.
- Any "get or create" idempotent DB operation in this codebase needs
  either a DB-level unique constraint with a catch-`IntegrityError`-and-
  re-read pattern, or guaranteed non-concurrent callers — TanStack Query
  does not dedupe concurrent requests across different query keys that
  happen to call the same backend operation. `get_or_create_paper_portfolio()`
  (`domains/paper_trading/service.py`) is the reference implementation of
  the fix, added after this exact race produced duplicate paper portfolios
  and a `MultipleResultsFound` crash during Phase 4 browser verification —
  see §9. Treat any new lazily-created, per-user singleton resource as
  needing the same pattern from the start, not as an edge case to catch
  later. `get_or_create_broker_portfolio()` (`domains/broker/service.py`,
  Phase 5) applies the identical pattern from day one rather than waiting
  to hit the same race live.
- Phase 5's new `broker_connections` table needed no manual migration —
  unlike Phase 4's `cash_balance`/`order_id` columns, it's a brand-new
  table, and `create_all()` (see above) does handle those. The distinction
  matters: a new *table* is free, a new *column on an existing table* is
  not.
- Live browser testing during Phase 5 surfaced real request queueing under
  load: with an open market-data WebSocket, several React Query hooks
  polling on page load, and (when `AI_PROVIDER=ollama`) a slow local model
  round-trip all competing for the browser's limited concurrent-connections-
  per-origin budget on HTTP/1.1, a UI action's request can sit queued for
  several seconds — confirmed via CDP network tracing, not a hang or a
  broker-specific bug (an isolated `fetch()`/`curl` call to the same
  endpoint resolves in under 30ms). Not fixed this phase — genuinely fixing
  it means HTTP/2 on the dev server or reducing concurrent background
  polling, both bigger changes than Phase 5's scope. If a UI action seems
  slow to respond during manual testing, check for concurrent AI/WebSocket
  activity in the same browser session before assuming a new bug.
- The AI Terminal's mode buttons (`apps/web/app/(dashboard)/ai/page.tsx`)
  are `disabled` until `GET /api/v1/ai/config` resolves — clicking one
  immediately after navigating to `/ai`, before that response lands, is a
  no-op. This surfaced during Phase 6 verification as an apparently-broken
  mode switch (the click did nothing, the chat request used the old mode);
  it's expected behavior working as designed, not a bug — a test script (or
  a very fast real click) needs to wait for the config response, not a
  fixed delay, before clicking a mode button.
- `domains/options/service.py`'s chain generation is stateless and
  in-memory (no DB writes), so unlike every "get or create" singleton
  pattern above, it has no concurrency story to worry about — two
  concurrent requests for the same symbol+expiry just independently
  recompute the identical deterministic result. Don't add caching here
  without checking that a stale cached chain (spot price moved since
  computed) isn't served as if current — the whole point of computing on
  request is that a chain always reflects the live simulated spot.
- Observed live during Tier 1 Session 3 verification: asked
  `llama3.1` "has TCS paid any dividend recently" with no other context,
  it called `get_corporate_actions` with a fabricated `as_of` (`2023-12-01`)
  instead of omitting the optional parameter — the tool correctly returned
  an empty result for that date, and the model reported that honestly
  ("no dividend information available as of [that date]"), so the no-
  fabrication guarantee held (no invented figure), but the *reasoning*
  about which date to query was wrong. A minor instance of the same
  general local-model tool-argument unreliability already documented
  above (described-tool-call repair, Phase 3.5) — noted here rather than
  chased with more prompt engineering, since the structural guardrail
  (only ever cite what a real tool call returned) is what actually matters
  and it worked.

## 12. Tier 1 infrastructure

A separate, larger effort from the phased product roadmap above — see
`docs/APARIX_TIER1_AUDIT.md` (written before this work, an honest
per-domain status check) and `docs/APARIX_TIER1_COMPLETION_REPORT.md`
(written after, with a production-readiness estimate). Summarized here
because it touches core architecture every phase above depends on.

- **Data provenance** (`core/provenance.py`) — a shared `Provenance` model
  attached to real API responses (market quotes, macro indicators), with a
  genuine staleness check (`quality: good|stale`), not a hardcoded value.
  Narrower than the AI layer's existing provenance (every `ai_tool_calls`
  row already traces an AI-cited number to its source) — unifying the two
  is future work, not done here.
- **`DataQualityService`** (`domains/admin/data_quality.py`) — real checks
  against real (mock) data: stale live quotes, invalid/negative candle
  prices or bad OHLC ordering, missing macro indicators. Exposed via
  `GET /admin/data-quality`. Each check can genuinely report a problem if
  the underlying data actually has one (see its tests) — not a set of
  checks that always report GOOD by construction.
- **`MacroDataProvider`** (`domains/macro/provider.py`) — the macro domain
  migrated to the interface-+Mock pattern already proven by
  `MarketDataProvider`/`ModelProvider`/`BrokerAdapter`, env-driven
  (`MACRO_PROVIDER=mock`, the only value that exists). A refactor (same
  data, same behavior), not a new data source — proves the seam generalizes
  cleanly rather than declaring that it would.
- **RBAC** (`core/roles.py`, `core/deps.py::require_role()`) — a stored
  `role` column (`super_admin/admin/compliance/analyst/support/user`)
  replacing the previously-binary admin-email-allowlist check.
  `ADMIN_EMAILS` is deliberately preserved as an alternate admin grant
  (`require_role` treats it as equivalent to `role="admin"`), so existing
  admin access via the env allowlist wasn't disturbed by this landing. A
  real role-editing UI + audit trail followed in Tier 1 Session 7, once
  backend correctness was established first — see §12.
- **Instrument master** (`models/security.py`) — `Security` gained `isin`,
  `segment`, `asset_class`, `lot_size`, `tick_size` (all nullable,
  unpopulated for today's seeded universe) — real columns for a licensed
  provider to write to later, not a speculative guess at its shape.
- **Real Alembic migrations** — see `docs/DATABASE_MIGRATION.md` for the
  full story. `app.main`'s lifespan now runs `core/migrations.py::run_migrations()`
  instead of a bare `create_all()`; a baseline migration captures the full
  schema; a real 26-user local dev database was migrated live (not just a
  test fixture) to prove the adoption path works. This directly fixes the
  `create_all()`-can't-add-columns gap that caused two real incidents in
  Phases 4–6 (see §11).
- Found and fixed while wiring migrations: `models/__init__.py` never
  imported `models.broker`, so `BrokerConnection` (Phase 5) was silently
  missing from `Base.metadata` whenever only `import app.models` ran (as
  Alembic's `env.py` does) — the running app worked by accident, via a
  different import path registering it first. A real, if narrow, bug —
  not caught by any existing test, because the app itself never hit it.

**Session 2 — Fundamentals + point-in-time integrity** (done): the
deferred item above, now built. `domains/fundamentals/` — a
`FundamentalsProvider` interface + `MockFundamentalsProvider` generating
synthetic income-statement/balance-sheet/cash-flow data (annual +
quarterly) per seeded security, anchored to that security's actual mock
price (an earlier version generated financials independent of price and
produced a P/E of ~1667 for a ~₹3000 stock — internally consistent but
implausible; fixed by working backward from price → target P/E → EPS →
PAT → revenue, and by sizing balance-sheet items off *annualized* revenue
even for a quarterly statement, since equity is a point-in-time snapshot,
not a flow that shrinks to a quarter's size). `domains/fundamentals/analytics.py`
— ROE/ROCE/ROA/D-E/interest-coverage/current-ratio/P-E/P-B/EV-EBITDA/
EV-Sales/FCF-yield, pure functions, fixture-tested against a hand-computed
example. `get_fundamentals` is AI tool #17.

**The point-in-time guarantee (§15, mandatory)**:
`get_latest_statement_as_of()` filters on `effective_date`, not
`period_end` — a query "as of" a date never returns a statement announced
after that date, even if the fiscal period itself already ended.
`tests/test_point_in_time_integrity.py` (§49 — the suite Session 1
deferred for lack of anything to test against) checks the exact leak
scenario: a period that *ended* but wasn't *announced* yet must not leak
into a query dated in that gap — the test that would fail under a naive
`period_end <= as_of` implementation and passes under the real one.
Point-in-time pricing applies the same discipline to the price side of a
ratio: a past `as_of` uses the nearest historical `Candle` close, not
today's live spot.

**Session 3 — Corporate actions engine** (done): the deferred item above,
now built. `domains/corporate_actions/` — a `CorporateActionsProvider`
interface + `MockCorporateActionsProvider` seeding dividends broadly and a
split/bonus/rights for a deterministic subset of securities (never a
merger/demerger/symbol_change/delisting against the live tradable
universe — see §9). `domains/corporate_actions/analytics.py::adjust_price_series()`
is the real adjustment algorithm — walks actions ex-date-descending,
multiplies every pre-ex-date price by the cumulative ratio — fixture-tested
against a hand-constructed raw series with an actual embedded 2-for-1
split discontinuity (₹200→₹101 raw, adjusts to a smooth ₹100-scale series
throughout). Not applied to the live seeded candle history this session —
see the `Candle.close` convention trade-off in §9. `get_corporate_actions`
is AI tool #18, and carries the same `effective_date <= as_of` point-in-time
guarantee as fundamentals (`list_actions_as_of()`), tested the same way
(`tests/test_corporate_actions.py`, mirroring
`tests/test_point_in_time_integrity.py`'s pattern for a second domain).

**Session 4 — News ingestion** (done): the full pipeline (§18) — SOURCE →
FETCH → NORMALIZE → DEDUPLICATE → CLASSIFY → EVENT EXTRACTION → STORE —
for real, not a simulation of it. `domains/news/provider.py::RSSNewsProvider`
makes a genuine HTTP request and parses real XML (stdlib `xml.etree`, no
new dependency); `MockNewsProvider` (checked-in default) needs neither.
`domains/news/classifier.py` is a small, transparent, fixture-tested
keyword-rule table, not an ML/LLM classifier — see §9 for why, and for the
Google-News-RSS-vs-RBI-feed licensing research (`docs/DATA_LICENSING.md`).
Verified against the **live** feed, not just a captured fixture: a real
run against `https://www.rbi.org.in/pressreleases_rss.xml` fetched 10 real
press releases and correctly classified zero of them as market-moving
events, because that day's actual content was entirely routine — the
classifier not forcing significance onto ordinary content is correct
behavior, confirmed live, not merely hoped for. A real bug was caught and
fixed the same way every prior session's bugs were: `MockNewsProvider`'s
first version duplicated an existing `SEED_EVENTS` headline verbatim,
silently creating a second, inconsistent `Event` row for the same story —
caught by an existing test's hardcoded event count, fixed by giving the
mock article genuinely distinct content, and the real local dev database
(which had already picked up the duplicate) was cleaned up and
re-verified live, not just fixed going forward. `search_news` is AI tool
#19. Deliberately not built: entity extraction and the knowledge-graph
step from the full spec pipeline, sentiment analysis, and a second real
source beyond RBI (a commercial publisher's feed would need its own
licensing review before use — see `docs/DATA_LICENSING.md`).

**Session 5 — Macro time-series/vintage tracking** (done): extends the
same point-in-time discipline fundamentals and corporate actions already
have to the macro domain. `MacroIndicator` (single current value per
code) is left untouched — a new, separate `macro_indicator_releases`
table (`models/macro_release.py`) carries the actual revision history:
one row per (code, period, revision_number), each with its own real
`release_date` distinct from the period it describes. Deliberately scoped
to only `cpi_inflation` and `gdp_growth` (`domains/macro/vintage.py::VINTAGE_INDICATORS`)
— the only two of the app's 7 seeded macro indicators that have a
real-world revision practice; the other 5 (repo rate, 10Y G-Sec yield,
INR/USD, crude oil, gold) are market-quoted rates/prices with no
revision concept, and generating a fake "vintage history" for them would
be exactly the kind of fabricated precision this project's discipline
prohibits — see §9. `domains/macro/vintage.py::generate_releases()` is a
pure, deterministically-seeded generator that walks backward from each
indicator's current value producing period/revision pairs with realistic
publication lags (CPI: ~14-30 days; GDP: ~45-75 days), never emitting a
release whose date would fall in the future relative to the seed date.
`get_releases_as_of()`/`get_latest_known_reading_as_of()`
(`domains/macro/service.py`) carry the same `release_date <= as_of`
point-in-time guarantee as fundamentals and corporate actions, tested the
same way (`tests/test_macro_history.py`, mirroring
`tests/test_point_in_time_integrity.py`'s pattern for a third domain).
`GET /macro/indicators/{code}/history` returns 404 — not an empty fake
list — for a non-revised indicator or an `as_of` date before any release
existed, so a caller can't mistake "no vintage concept applies here" for
"no data available yet." `get_macro_history` is AI tool #20. Hit the same
"seed only runs once" gotcha a third time this session: `seed_vintage_if_needed()`
was initially nested inside the existing `seed_if_needed()`, but this
repo's real local dev database already had `macro_indicators` rows from
Phase 3, long before this table existed, so the outer function's
already-seeded short-circuit meant vintage seeding never ran — fixed by
decoupling it into its own top-level call in `app/main.py`'s lifespan,
the same fix pattern already used for corporate actions and news. A test
originally asserting the most-recently-available period's final revision
would exactly equal the indicator's current value failed in a way that
turned out to be a genuine design realization, not a bug: due to
realistic publication lag, the most-recently-available period as of
"today" is often not the current calendar period (whose data hasn't been
released yet), so it only approximately tracks the current value — the
test was relaxed to an approximate check with an explanatory comment
rather than the generator being made less realistic to satisfy an overly
strict assertion. No frontend surface was added this session (deliberate
scope decision — no existing page naturally hosts it without
restructuring `/home`); the data is reachable via the API and the AI
Terminal.

**Session 6 — RAG foundation** (done): real retrieval-augmented search
over the one genuinely real document corpus this codebase has — ingested
news articles (Session 4). `domains/rag/embeddings.py::EmbeddingProvider`
follows the same interface+Mock pattern as every other domain, but the
checked-in default (`HashingEmbeddingProvider`) is a real algorithm
(feature hashing / the "hashing trick" — a genuine classical
information-retrieval technique) run over real ingested text, not random
noise or fabricated data — it's simply weaker than a dense neural
embedding at capturing synonyms/paraphrases, and the `researcher` mode's
system prompt says so directly rather than overselling it. A real local
model was pulled and used for the opt-in upgrade
(`ollama pull nomic-embed-text`, verified live: real 768-dim embeddings
returned from a genuine `POST /api/embeddings` call). `document_embeddings`
(additive, keyed on `(article_id, model)` so switching providers doesn't
require deleting prior vectors) is indexed incrementally and idempotently
(`domains/rag/service.py::reindex_missing()`) — called once at startup
and again after every real news ingestion run, deliberately not a
one-time seed, since the same "seed only runs once" gotcha already hit
three times this session doesn't apply to something designed to run
indefinitely. `search_knowledge_base` is AI tool #21; the previously
schema-only `researcher` AI mode (accepted since Session 1's RBAC work
but backed by nothing — `MODE_INSTRUCTIONS` had no entry for it, so it
fell back to a generic "not available yet" note) now has a real
instruction set and a real tool to back it.

Two real bugs were caught and fixed during live verification, not shipped:
(1) Ollama handed back `top_k` as the string `"5"` instead of an int,
crashing a list slice in `retrieve()` — fixed by coercing defensively in
`search_knowledge_base_tool`, the same category of local-model
argument-type unreliability already documented in §11, but this instance
crashed instead of just resolving to a wrong value. (2) More seriously:
after that crash, llama3.1 answered the user's question anyway with three
entirely invented publisher names, article titles, and similarity scores
formatted exactly like real tool output — and `_apply_guardrail()` didn't
flag it, because the old version only checked whether *any* tool call was
attempted, not whether one actually succeeded. Fixed by treating an
attempted-and-failed tool call the same as no tool call at all (see §9);
a regression test (`test_guardrail_flags_a_response_built_on_only_failed_tool_calls`)
reproduces the exact scenario. A closely related, narrower issue was
observed and addressed by tightening the `researcher` system-prompt
instruction rather than by a structural code change: given a genuinely
empty (not failed) tool result, the model initially said "I will provide
a generic answer based on general knowledge" and fabricated two citations
anyway — the instruction was strengthened to explicitly forbid inventing
a publisher/title/quote and to require saying plainly when nothing
relevant is in the corpus; re-verified live and the model then declined
honestly. A separate, still-unresolved instance was also observed live:
given a query where retrieval genuinely found the right document (a
0.53 cosine-similarity match, clearly the correct article), the model
still said "I couldn't find any specific information" — a real synthesis
weakness in a locally-run 8B-class model reading its own tool output, not
a fabrication (it under-used real evidence rather than inventing false
evidence), and — consistent with this session's established precedent for
this category of finding — not chased with further prompt engineering,
since the structural "never fabricate" guarantee is what actually
matters and it held. No new frontend surface was added — the existing AI
Terminal's generic tool-call viewer (`AparixAIMessage.tsx`) already
renders any tool's real result, `search_knowledge_base` included, and
`/ai/config`'s `supported_modes` list already drives which mode buttons
are enabled, so `researcher` became a genuinely clickable, functional
mode with zero frontend code changes.

**Session 7 — RBAC role-management UI + audit trail** (done): the natural
follow-up to Session 1's backend-only RBAC landing, which explicitly
flagged "no role-editing UI or audit trail specifically for role changes
yet" as a real gap. `PATCH /admin/users/{id}/role`
(`domains/admin/service.py::update_user_role()`) is real, not a stub —
every change is written through the existing `log_action()` audit
mechanism (`action="admin.update_user_role"`, `input_data` carries
`target_user_id`/`old_role`/`new_role`), verified live: the admin page's
audit log table shows a real `admin.update_user_role` row with a
`success` result immediately after a real role change. Two privilege-
escalation guards exist beyond "is an admin," both enforced server-side
and reflected in the UI (a disabled `<select>`, not just a hidden one —
the guard is the source of truth, the UI just avoids inviting a 403):
self-role-change is blocked entirely (a compromised or careless admin
session can't change its own role — a second admin must), and only a
`super_admin` may grant the `super_admin` role or change an existing
`super_admin`'s role (a plain `admin` can't mint or strip the platform's
highest privilege). `UpdateUserRoleRequest`'s pydantic `field_validator`
rejects an unknown role string with a 422 before the service layer is
ever reached. No new database table or migration — `User.role` has
existed since Session 1; this session made it real to actually edit.
Live-verified end to end: a real admin account changed a real target
user's role through the actual `/admin` page UI, the change persisted,
and the audit log entry appeared — zero console errors (one apparent
hydration-mismatch console error on first attempt turned out to be an
artifact of navigating directly via URL rather than in-app link
navigation — a Next.js SSR/CSR difference unrelated to this session's
code, confirmed by re-running the identical flow through a normal
in-app click with zero errors).

**Session 8 — Survivorship-bias / point-in-time security universe**
(done): the last item Session 3 explicitly deferred ("seeding these
against the live universe would break existing paper trading/portfolio/
backtest flows; full survivorship-bias support is separate future work").
`Security` gained `is_tradable`/`listed_date`/`delisted_date` (all
nullable-safe defaults — every security seeded before this migration
keeps `is_tradable=True` with null dates, meaning "no known constraint,"
not a false claim of a real listing date this app never had). Two
dedicated, clearly fictitious historical-only securities
(`domains/market_data/historical_seed_data.py` — real Indian company
identities are used everywhere else in this app, but a delisting/merger
is a specific, checkable real-world fact this codebase has no basis to
assert about an actual company) are seeded with real candle history
ending at their real delisting date (not running forward to today for a
security that no longer trades — `MarketDataProvider.generate_history()`
gained an `end_date` parameter for this) and exactly one real
`CorporateAction` each (`delisting`/`merger` — the two
`DISRUPTIVE_ACTION_TYPES`, core/corporate_action_types.py, that were
previously schema-only). `list_securities_as_of()`
(`domains/market_data/service.py`) is the actual point-in-time universe
query — the same discipline already applied to a single security's own
data (fundamentals, corporate actions, macro vintage) now applied to
universe *membership itself*: a query dated before a security's
delisting/merger correctly still includes it, live-verified via
`GET /market/securities/universe?as_of=...` against the running server.
`list_securities()` (the live tradable universe — frontend dropdowns,
live tick seeding) defaults to excluding non-tradable securities, so
every existing caller's behavior is unchanged by construction, not by
convention — live-verified via Playwright that `/portfolio`, `/options`,
and `/fundamentals`'s symbol dropdowns never show either historical
security, and that a paper-trading order against one 404s. No frontend
surface was added for browsing the point-in-time universe itself
(deliberate scope decision, same reasoning as macro vintage — no existing
page naturally hosts it); the data is reachable via the API.

**Session 9 — Rate limiting, request-ID middleware, sanitized error
responses** (done): §42, flagged in the original Tier 1 audit and
unaddressed across 8 prior sessions. `RequestIDMiddleware`/
`RateLimitMiddleware` (`core/middleware.py`) are plain Starlette
middleware, not a third-party package — small enough to own directly,
consistent with this codebase's pattern everywhere else. A real, working
in-process `FixedWindowRateLimiter` (`core/rate_limit.py`) — a general
per-client-IP limit and a stricter one for `/auth/login`/`/auth/register`/
`/auth/refresh` (the brute-force-relevant paths) — returns real `429`s
with a real `Retry-After` header, live-verified: 10 rapid login attempts
against the actual running server returned `401` for the first 10, then
`429` for the 11th and 12th. Explicitly scoped to a single process (an
in-memory dict, not Redis) — consistent with the rest of this app's
architecture (one asyncio process, SQLite), not a shortcut; disabled
entirely in the test suite (`RATE_LIMIT_ENABLED=false` in conftest.py) so
the suite's hundreds of requests from one fake client IP don't trip it,
with the real behavior instead tested directly against a small dedicated
throwaway app (`tests/test_middleware.py`) rather than fighting the
production `app` singleton's import-time settings lock-in.

Every request now carries a real correlation ID (`X-Request-ID`,
generated fresh unless a client supplies a syntactically valid UUID — an
arbitrary client-supplied string is rejected rather than trusted, since
it would otherwise flow straight into structured log lines, a real
log-injection risk). `core/logging_config.py` attaches a real formatted
handler to the root logger (previously nonexistent — `app.*` loggers like
`domains/news/service.py`'s pre-existing `logger.exception()` calls fell
back to Python's bare "handler of last resort," dropping WARNING-level
calls entirely) with a filter that injects the request ID from a
`contextvars.ContextVar` set at the start of every request, so a single
request's log lines can be correlated even under concurrent traffic.

**Sanitized error responses turned out to already be the framework
default — verified empirically, not assumed:** before writing any code, a
throwaway probe forced a real unhandled `RuntimeError` containing a
deliberately sensitive-looking string through the actual app and
confirmed Starlette's default (`debug=False`, never set to `True`
anywhere in this codebase) already returns a bare `"Internal Server
Error"` with no leak. What this session added on top, genuinely new: a
global `@app.exception_handler(Exception)` that returns a *consistent
JSON* shape (`{"detail": "...", "request_id": "..."}`, matching the rest
of the API) instead of Starlette's default plain-text body, and — the
real, previously-nonexistent capability — logs the actual exception with
a traceback server-side, correlated by request ID, so a genuine bug is
actually debuggable rather than just safely hidden. A real Starlette
internal was learned and then verified, not assumed: a handler registered
for the bare `Exception` type is installed into `ServerErrorMiddleware`
(outermost, added before user middleware — see
`Starlette.build_middleware_stack()`), not `ExceptionMiddleware`, so it
sits *outside* `RequestIDMiddleware` — a response built there would never
pass back through `RequestIDMiddleware`'s normal
"attach header after call_next returns" line, so the handler sets
`X-Request-ID` on its own response directly. Caught by a genuine test
failure (`KeyError: 'x-request-id'`), not predicted in advance.
`tests/test_middleware.py::test_existing_typed_http_exceptions_are_unaffected_by_the_catch_all_handler`
confirms the new catch-all handler never shadows FastAPI's own handling
of a deliberately-raised `HTTPException` (a 404 for an unknown symbol is
still a real 404, not swallowed into a generic 500) — Starlette dispatches
to the most specific handler in the exception's MRO, so this was a real
risk worth a dedicated regression test, not a hypothetical one.

**Deferred** (see `docs/APARIX_TIER1_AUDIT.md`/
`docs/APARIX_TIER1_COMPLETION_REPORT.md` for the full list and why): a
document-upload/PDF/filing corpus beyond ingested news articles, an ANN
vector index (ok at the current corpus size — see §9), macro
vintage/revision tracking for the 5 market-quoted indicators that have no
real-world revision concept (repo rate, 10Y G-Sec yield, INR/USD, crude
oil, gold — see §9), retroactively adjusting the live seeded candle
history for corporate actions, `demerger`/`symbol_change`/`isin_change`
still unseeded even against a historical-only security (schema/logic only,
tested via synthetic fixtures), restatement tracking (every fundamentals
statement is `is_restated=False`), real data providers for fundamentals/
corporate-actions/macro (still `MOCK` only), entity extraction and the
knowledge-graph step of the news pipeline, a financial knowledge graph
more broadly, a historical analogue engine, portfolio exposure beyond
sector, and a real Postgres verification pass (documented but never run
against a real instance in this environment).
