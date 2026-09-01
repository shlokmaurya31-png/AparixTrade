# Aparix

AI-native Indian financial intelligence platform. **Phase 1 + 2 + 3 + 3.5 +
4**: auth, an adaptive dashboard, a portfolio engine, mock Indian market
data, a risk & simulation engine (VaR/CVaR, Sharpe/Sortino, correlation
matrices, Monte Carlo, custom stress testing, buy-and-hold backtesting), an
event intelligence engine (mock news events mapped to sectors/companies
with a quantified portfolio-impact estimate — the "flood disrupts
Reliance's Jamnagar operations" scenario, working end to end), a mock macro
data feed, a read-only admin dashboard, a paper trading simulator (virtual
₹10L capital, realistic slippage/brokerage, cash-constrained buy/sell — no
real money, no real broker), and an AI Terminal that actually understands
free-form questions — a real local LLM (Ollama, `llama3.1`) calling the
same tool registry every number in this app already traces back to,
including a pre-trade preview and a post-trade entry-quality coach, never
inventing a figure. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for
the full design, trade-offs, and Phase 5–6 roadmap.

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
AI coach how the fill looked), and the AI Terminal at `/ai` — try "what's
happening in the market", "how does this event affect my portfolio",
"should I buy RELIANCE", or "stress test my portfolio".

To see the admin dashboard: add your account's email to `ADMIN_EMAILS` in
`apps/api/.env`, restart the API, and log in again — an "Admin" nav item
appears with user/audit-log/AI-usage/system-health views.

**To use the real AI** instead of the templated mock: install
[Ollama](https://ollama.com), `ollama pull llama3.1`, make sure `ollama
serve` is running, then set `AI_PROVIDER=ollama` in `apps/api/.env` and
restart the API. The AI Terminal's mode badges (Simple/Quant/Analyst/Risk
Officer/Portfolio Manager/Macro Economist) become clickable and genuinely
change response style — the first request in a session is slow (~15s, cold
model load), after that it's a few seconds per reply.

## Test

```bash
cd apps/api && uv run pytest        # portfolio + risk + simulation + events + macro + admin + AI-provider fixtures/flows
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

All market data, events, macro data, and AI responses in this build are
clearly labeled `DEMO DATA` / mock in the UI — nothing here is a live feed,
real news, or a real broker connection. See `docs/ARCHITECTURE.md` §9 for
why, and what Phase 4+ adds.
