# Aparix

AI-native Indian financial intelligence platform. **Phase 1 through 6 —
every phase on the original roadmap, scoped** (see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design and the
trade-offs behind every scoping decision), **plus Tier 1 infrastructure**
(data provenance, quality checks, RBAC, real Alembic migrations, and a
point-in-time fundamentals engine — see
[`docs/APARIX_TIER1_COMPLETION_REPORT.md`](docs/APARIX_TIER1_COMPLETION_REPORT.md)
for an honest breakdown of what's real vs. still missing): auth, an
adaptive dashboard, a portfolio engine, mock Indian market data, a risk &
simulation engine (VaR/CVaR, Sharpe/Sortino, correlation matrices, Monte
Carlo, custom stress testing, buy-and-hold backtesting), an event
intelligence engine (mock news events mapped to sectors/companies with a
quantified portfolio-impact estimate — the "flood disrupts Reliance's
Jamnagar operations" scenario, working end to end), a mock macro data
feed, a read-only admin dashboard (now with real RBAC and a data-quality
view), a paper trading simulator (virtual ₹10L capital, realistic
slippage/brokerage, cash-constrained buy/sell — no real money, no real
broker), a broker connection layer (`BrokerAdapter` interface — a
simulated demo broker out of the box, a real Zerodha Kite Connect adapter
built to spec for when you have real credentials, encrypted credential
storage, and live order placement kept off by default even once
connected), a read-only options analysis engine (synthetic chains,
Black-Scholes pricing/Greeks — no options trading, analysis only), a
point-in-time fundamentals engine (synthetic financial statements +
ratios, anchored to real prices so they stay plausible — a query "as of" a
date only ever sees what would actually have been announced by then, never
a later result), multi-portfolio support (a header switcher plus an
aggregate "all my portfolios" view), and an AI Terminal that actually
understands free-form questions — a real local LLM (Ollama, `llama3.1`)
calling the same tool registry every number in this app already traces
back to, including a pre-trade preview, a post-trade entry-quality coach,
real broker holdings, options Greeks, and fundamentals/ratios, never
inventing a figure.

Everything here runs locally with **no paid APIs, no Docker, and no external
accounts** — SQLite for the database, a seeded synthetic market for prices,
and (by default) a rule-based mock AI provider. Set `AI_PROVIDER=ollama` for
a real local model instead (see below) — still no paid API, no cost, no data
leaving your machine.

## Requirements

- Node.js 20.9+ (built with 25.x)
- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/)

## Run it

**Backend** (from `apps/api`):

```bash
uv sync --extra dev
cp ../../.env.example .env   # first time only; defaults work as-is
uv run uvicorn app.main:app --reload --port 8000
```

Tables and the demo NIFTY-subset universe are created/seeded automatically on
first startup (`aparix_dev.db`, SQLite). API docs: http://localhost:8000/docs

**Frontend** (from the repo root):

```bash
npm install
npm run dev:web
```

Open http://localhost:3000 — it redirects to `/register`. Create an account,
complete onboarding (this also creates your default portfolio), add a
RELIANCE holding on `/portfolio`, then check `/events` — the seeded
"flooding disrupts Jamnagar" event shows a real, quantified impact on your
holding. Also explore `/risk` (VaR/CVaR, correlation matrix, stress test,
Monte Carlo, backtest), `/paper` (virtual-capital order ticket — preview a
buy/sell before committing, see real slippage and brokerage, then ask the
AI coach how the fill looked), `/broker` (click "Connect broker (demo)" to
simulate linking a brokerage account, then "Sync holdings" to pull its
holdings into a read-only portfolio), `/options` (pick a symbol and expiry
to see a synthetic chain with real Black-Scholes premiums/Greeks and an IV
smile chart — analysis only, no options trading), `/fundamentals` (pick a
symbol to see synthetic income-statement/balance-sheet/cash-flow data and
computed ratios — annual or quarterly, point-in-time by design: a query
"as of" a past date only ever sees what would actually have been announced
by then), and the AI Terminal at
`/ai` — try "what's happening in the market", "how does this event affect
my portfolio", "should I buy RELIANCE", "what's in my broker account",
"what's the delta on a TCS call option" (switch to the Options Specialist
mode first), or "stress test my portfolio". Use the portfolio switcher in
the header (next to "+ New") to create and jump between multiple
portfolios — `/portfolio` shows a combined view across all of them once you
have more than one.

To see the admin dashboard: add your account's email to `ADMIN_EMAILS` in
`apps/api/.env`, restart the API, and log in again — an "Admin" nav item
appears with user/audit-log/AI-usage/system-health/data-quality views (the
last one runs real checks — stale quotes, invalid candle prices, missing
macro indicators — against the app's own data, not hardcoded findings). A
real role-based access system now backs admin access too (see
`docs/APARIX_TIER1_AUDIT.md`/`docs/APARIX_TIER1_COMPLETION_REPORT.md`) —
`ADMIN_EMAILS` still works exactly as before as an alternate grant.

**To use the real AI** instead of the templated mock: install
[Ollama](https://ollama.com), `ollama pull llama3.1`, make sure `ollama
serve` is running, then set `AI_PROVIDER=ollama` in `apps/api/.env` and
restart the API. The AI Terminal's mode badges (Simple/Quant/Analyst/Risk
Officer/Portfolio Manager/Macro Economist) become clickable and genuinely
change response style — the first request in a session is slow (~15s, cold
model load), after that it's a few seconds per reply.

**To connect a real Zerodha account** (optional — the demo broker above
needs none of this): generate a `BROKER_ENCRYPTION_KEY` with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
and set it in `apps/api/.env`, get a Kite Connect API key/secret from
[developers.kite.trade](https://developers.kite.trade) (paid subscription)
and set `ZERODHA_API_KEY`/`ZERODHA_API_SECRET`, then set
`BROKER_PROVIDER=zerodha` and restart the API. This wires in the real OAuth
login + holdings sync; it hasn't been tested against a live Kite account in
this build (see `docs/ARCHITECTURE.md` §9) — verify a real connect + sync
before relying on it. Live order placement stays off
(`BROKER_LIVE_TRADING_ENABLED=false`) until you explicitly turn it on.

## Test

```bash
cd apps/api && uv run pytest        # portfolio + risk + simulation + events + macro + admin + paper trading + broker + options + fundamentals + point-in-time + AI-provider fixtures/flows
npm run build -w web                # production build + strict TS check
npm run lint -w web
```

## Layout

```
apps/web/   Next.js 16 (App Router), TypeScript strict, Tailwind — the UI
apps/api/   FastAPI, SQLAlchemy async, modular monolith — everything else
docs/       Architecture doc
docker-compose.yml   Optional Postgres for local dev if you have Docker
```

All market data, events, macro data, options chains/Greeks, AI responses,
and the default broker connection in this build are clearly labeled
`DEMO DATA` / mock in the UI — nothing here is a live feed, real news, a
real options market, or (unless you've wired in real Zerodha credentials
and explicitly enabled live trading) a real broker connection. See
`docs/ARCHITECTURE.md` §9 for why, and what's deliberately out of scope
across every phase.
