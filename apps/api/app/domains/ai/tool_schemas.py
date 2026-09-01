"""Function-calling schemas for TOOL_REGISTRY (domains/ai/tools.py), in the
OpenAI/Ollama tools format. Describes the calling contract only — no
business logic lives here, and every tool name below must exist in
TOOL_REGISTRY or get_model_provider() would be handing a real model a tool
it can't actually invoke.
"""

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": (
                "Get the user's portfolio: total value, day P&L, total P&L, sector exposure, "
                "concentration score, volatility, beta vs NIFTY 50, and a 1-5 risk score."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_holdings",
            "description": "List each individual holding in the user's portfolio with its market value and P&L.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sector_exposure",
            "description": "Get the user's portfolio weight by sector.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_data",
            "description": "Get the current simulated quote (last price, change %) for a stock or index symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": 'Ticker symbol, e.g. "RELIANCE", "TCS", "NIFTY50", "BANKNIFTY".',
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_profile",
            "description": (
                "Get historical-simulation VaR/CVaR (95%/99%), Sharpe ratio, Sortino ratio, max drawdown, "
                "and holding correlation/covariance matrices for the user's portfolio."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_stress_test",
            "description": (
                "Run a hypothetical shock against the portfolio: a sector, a holding symbol, or the "
                'whole market ("NIFTY50"), moving by shock_pct percent. Returns the estimated ₹ and % impact.'
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": 'A sector name, a holding symbol, or "NIFTY50" for a market-wide shock.',
                    },
                    "shock_pct": {
                        "type": "number",
                        "description": "The shock size in percent, e.g. -15 for a 15% drop, 8 for an 8% rise.",
                    },
                },
                "required": ["target", "shock_pct"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_monte_carlo",
            "description": (
                "Run a Monte Carlo simulation projecting the portfolio's value over a future horizon, "
                "returning percentile outcomes (P5/P25/P50/P75/P95) and probability of loss."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["bootstrap", "gbm"],
                        "description": "bootstrap resamples real historical returns; gbm assumes a normal distribution.",
                    },
                    "horizon_days": {"type": "integer", "description": "Number of trading days to project forward."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_backtest",
            "description": (
                "Backtest a buy-and-hold of the portfolio's current weights over the available simulated "
                "price history. Returns CAGR, Sharpe, Sortino, max drawdown, and the equity curve."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_events",
            "description": "List recent market-moving news events (headline, sector/company affected, severity).",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Max number of events to return."}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_event_impact",
            "description": (
                "Estimate a specific event's ₹ and % impact on the user's portfolio. If event_id is omitted, "
                "uses the most recent medium/high-severity event."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "The event's id, from get_events. Optional."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_macro_indicators",
            "description": "Get current macro data: GDP growth, CPI inflation, RBI repo rate, 10Y G-Sec yield, INR/USD, crude oil, gold.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_macro_history",
            "description": (
                "Get the vintage/revision history for a macro indicator that actually has real revisions "
                "(cpi_inflation or gdp_growth only — other indicators are market-quoted rates/prices with no "
                "revision history). Point-in-time: if as_of is given, only shows what was actually published "
                "by that date, including which figures were later revised."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "enum": ["cpi_inflation", "gdp_growth"],
                        "description": "Which indicator's history to fetch.",
                    },
                    "as_of": {
                        "type": "string",
                        "description": "Date (YYYY-MM-DD) to evaluate as of. Optional — defaults to today.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "preview_trade",
            "description": (
                "Preview a hypothetical buy or sell order in the user's paper trading account WITHOUT executing "
                "it — estimated fill price, slippage, brokerage, cash impact, and how it would change portfolio "
                "concentration. Use this before placing any real order or when the user asks 'should I buy/sell'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "The security symbol, e.g. RELIANCE, TCS."},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "number", "description": "Number of shares."},
                },
                "required": ["symbol", "side", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_order",
            "description": (
                "Evaluate a paper trading order's entry quality: fill price vs the last 30 trading days' "
                "range, and the resulting slippage/brokerage. This evaluates the ENTRY, not the eventual "
                "outcome, which isn't knowable yet. If order_id is omitted, uses the most recent order."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order's id. Optional — defaults to the most recent order."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_broker_holdings",
            "description": (
                "Get the user's real broker-linked account holdings (synced from a connected brokerage, "
                "e.g. Zerodha), separate from the paper trading account. Returns an error if no broker is connected."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_options_chain",
            "description": (
                "Get a synthetic options chain (calls and puts) for a stock: strikes near the current price, "
                "premium, implied volatility (assumed, not market-derived), and Greeks (delta/gamma/theta/vega/rho). "
                "If expiry is omitted, uses the nearest available synthetic expiry."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Underlying stock symbol, e.g. RELIANCE, TCS."},
                    "expiry": {"type": "string", "description": "Expiry date (YYYY-MM-DD), from the available list. Optional."},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "price_option",
            "description": (
                "Price a single option contract (call or put) at a specific strike: premium, implied volatility, "
                "and Greeks. If strike is omitted, uses the nearest at-the-money strike. If expiry is omitted, "
                "uses the nearest available synthetic expiry."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Underlying stock symbol, e.g. RELIANCE, TCS."},
                    "strike": {"type": "number", "description": "Strike price. Optional — defaults to at-the-money."},
                    "option_type": {"type": "string", "enum": ["call", "put"]},
                    "expiry": {"type": "string", "description": "Expiry date (YYYY-MM-DD). Optional."},
                },
                "required": ["symbol", "option_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fundamentals",
            "description": (
                "Get a company's latest available financial statement (revenue, PAT, EPS, equity, debt, free "
                "cash flow) and computed ratios (ROE, ROCE, debt/equity, current ratio, P/E, P/B, EV/EBITDA, "
                "FCF yield). Point-in-time: if as_of is given, returns only the statement actually announced "
                "by that date, never a later one — never uses information from the future."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Company symbol, e.g. RELIANCE, TCS."},
                    "period_type": {"type": "string", "enum": ["annual", "quarterly"]},
                    "as_of": {
                        "type": "string",
                        "description": "Date (YYYY-MM-DD) to evaluate as of. Optional — defaults to today.",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_corporate_actions",
            "description": (
                "Get a company's corporate actions on record — dividends, splits, bonuses, rights issues, "
                "buybacks. Point-in-time: if as_of is given, only returns actions actually publicly known by "
                "that date."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Company symbol, e.g. RELIANCE, TCS."},
                    "as_of": {
                        "type": "string",
                        "description": "Date (YYYY-MM-DD) to evaluate as of. Optional — defaults to today.",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": (
                "Search ingested news/press-release articles by keyword (e.g. 'repo rate', 'inflation'). "
                "Returns the most recent matches with title, publisher, date, and URL. If query is omitted, "
                "returns the most recent articles regardless of topic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keyword to search for. Optional."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Real semantic search over ingested news/press-release articles (embedding-based, not just "
                "keyword substring matching — see search_news for that). Use this to find and cite real "
                "evidence for a research-style question, e.g. 'what's the evidence for a rate hike' or 'find "
                "documents about inflation'. Returns the most relevant articles with a similarity score."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for."},
                    "top_k": {"type": "integer", "description": "Max number of results. Optional, defaults to 3."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_graph_exposure",
            "description": (
                "Look up which seeded securities have a real, documented exposure to a location "
                "(e.g. 'Gujarat', 'Maharashtra') or commodity (e.g. 'crude_oil', 'coal', 'steel', "
                "'palm_oil') via the financial knowledge graph — a headquarters/major-facility link for "
                "a location, or a consumption-side dependency for a commodity. This is the same "
                "resolution used internally when an event or stress test targets a location/commodity "
                "instead of a specific symbol/sector."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "A location or commodity name to look up."},
                },
                "required": ["target"],
            },
        },
    },
]

_SCHEMA_NAMES = {schema["function"]["name"] for schema in TOOL_SCHEMAS}


def assert_schemas_match_registry(registry_names: set[str]) -> None:
    """Called once at import time (see ollama_provider.py) — if a tool is
    ever added to TOOL_REGISTRY without a matching schema here (or vice
    versa), fail loudly at startup rather than silently handing the model
    a tool it can't call or omitting one it should have."""
    if _SCHEMA_NAMES != registry_names:
        missing_schemas = registry_names - _SCHEMA_NAMES
        missing_registry = _SCHEMA_NAMES - registry_names
        raise RuntimeError(
            f"TOOL_SCHEMAS / TOOL_REGISTRY mismatch. "
            f"In registry but no schema: {missing_schemas or 'none'}. "
            f"In schema but no registry entry: {missing_registry or 'none'}."
        )
