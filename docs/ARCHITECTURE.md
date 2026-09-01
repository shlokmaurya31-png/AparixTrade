# Aparix — Architecture

Aparix is an AI-native Indian financial intelligence platform. This document
describes the system as built (Phase 1 + 2 + 3 + 3.5, scoped) and the shape
it is designed to grow into (Phase 4–6). It is intentionally condensed — the
full product spec this was derived from runs to ~80 sections; this document
captures the decisions that matter for engineers picking up the codebase.

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
`market_data`, `risk`, `simulation`, `events`, `macro`, `admin`, `ai`,
`audit`. Each is self-contained
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
- **`ModelProvider`** interface (`domains/ai/provider.py`) with a
  `MockModelProvider`: it runs the same tool registry a real LLM would
  (`get_portfolio`, `get_holdings`, `get_sector_exposure`, `get_market_data`),
  then fills a response template with the tool's actual return values. It
  never invents a number. A future `AnthropicModelProvider` implements the
  identical interface — routing, session/message persistence, and the tool
  registry are all provider-agnostic already.
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

## 5. Database

Dev default is **SQLite** (`aiosqlite`), zero install required. Production
target is **PostgreSQL** (`docker-compose.yml` provides it locally for anyone
with Docker). The schema is written using portable SQLAlchemy types
specifically so this swap is a connection-string change plus an Alembic
migration, not a rewrite — see the Trade-offs note below.

Tables: `users`, `user_preferences`, `portfolios`, `securities`, `candles`,
`holdings`, `transactions`, `ai_sessions`, `ai_messages`, `ai_tool_calls`,
`audit_logs`, `backtests`, `events`, `macro_indicators`. No speculative
columns for unbuilt features (e.g.
no `broker_account_id` sitting unused on `portfolios`) — those get added
when the feature they support gets built.

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
  mirror, command bar open/closed, AI mode).
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

**Tool registry** (`domains/ai/tools.py`, 11 tools): `get_portfolio`,
`get_holdings`, `get_sector_exposure`, `get_market_data` (Phase 1);
`get_risk_profile`, `run_stress_test`, `run_monte_carlo`, `run_backtest`
(Phase 2); `get_events`, `get_event_impact`, `get_macro_indicators`
(Phase 3). Both providers call the exact same functions — one JSON-schema
description per tool for the LLM (`domains/ai/tool_schemas.py`), checked
against `TOOL_REGISTRY` at import time (`assert_schemas_match_registry()`) so
a tool added to one without the other fails loudly at startup, not silently
at runtime.

**`OllamaModelProvider`** (`domains/ai/ollama_provider.py`, Phase 3.5): a
real agentic loop, capped at `MAX_TOOL_ROUNDS=4` — model returns tool_calls,
each executes for real, results feed back as `role: "tool"` messages, repeat
until the model returns plain text. A mode-specific system prompt
(`MODE_INSTRUCTIONS`) makes `simple/quant/analyst/risk_officer/
portfolio_manager/macro_economist` genuinely different response styles from
one model, not six hand-written templates; `options_specialist`/`researcher`
get an explicit instruction to say those capabilities don't exist rather
than improvise a persona with no data behind it. `GET /api/v1/ai/config`
exposes which provider/modes are actually live so the frontend's mode
switcher never overclaims what a given provider can do.

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
- The product performs analytics/education only in Phase 1 — no order
  execution exists, so no execution-related compliance surface exists yet.
  This is a deliberate regulatory boundary, not a gap: broker integration
  (Phase 5) is the point where compliance/legal review becomes required
  before anything resembling advice or execution ships.

## 9. Trade-offs made explicit

| Decision | Choice | Why | Consequence |
|---|---|---|---|
| Dev database | SQLite for local dev | No Docker/Postgres available in the build environment; spec requires the app to run with zero paid/external deps | Prod uses Postgres; schema kept portable; Alembic migration documents the swap |
| Monorepo tooling | npm workspaces, no Turborepo/pnpm | pnpm not installed; avoids adding infra before it's needed | Two dev commands instead of one; documented in README |
| Redis / Kafka | Deferred | Nothing built so far needs caching or a message bus | `docker-compose.yml` has Redis commented out |
| AI provider (checked-in default) | Mock, behind `ModelProvider` interface | No paid LLM dependency for local dev/demo out of the box | `OllamaModelProvider` (Phase 3.5) proved the interface — an `AnthropicModelProvider` would be the same shape, one new file |
| Charting | Recharts only | Candlestick/vol-surface charts belong to Markets/Options pages (Phase 3/6) | No TradingView-class library pulled in yet |
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
built and tested. Six AI modes are now real style variants from one model
(`simple/quant/analyst/risk_officer/portfolio_manager/macro_economist`);
`options_specialist`/`researcher` still honestly decline. A best-effort
hallucination guardrail and a described-tool-call repair loop (found live
during verification — see §9) harden it against the specific ways an 8B
open model is less reliable than a frontier one. `MockModelProvider` is
unchanged and stays the checked-in default. Not done: RAG (now unblocked —
a real model exists to consume it, just not built yet), the Anthropic
provider (same interface, not implemented).

- **Phase 4 — Paper trading**: order simulator, realistic fills/slippage, AI
  trading coach (pre/post-trade evaluation).
- **Phase 5 — Brokerage**: `BrokerAdapter` interface, Zerodha Kite Connect
  integration (sandbox first), broker credential isolation. This is also the
  point a real compliance/legal review is required before anything ships live.
- **Phase 6 — Professional**: options workspace (unblocks Greeks/vol
  surfaces), institutional dashboards, multi-portfolio/family-office
  features, public APIs, billing tiers.

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
