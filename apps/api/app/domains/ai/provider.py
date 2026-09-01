"""ModelProvider abstraction.

Swapping in a real LLM later (e.g. AnthropicModelProvider) means implementing
this same interface — the tool registry, session/message persistence, and API
routes above it are already provider-agnostic. See docs/ARCHITECTURE.md §7.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.ai.tools import call_tool
from app.models.portfolio import Portfolio


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass
class ModelResponse:
    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


class ModelProvider(ABC):
    name: str

    @abstractmethod
    async def respond(
        self, db: AsyncSession, *, portfolio: Portfolio, message: str, mode: str
    ) -> ModelResponse:
        raise NotImplementedError


class MockModelProvider(ModelProvider):
    """Rule-based intent resolution over a handful of supported questions,
    then a response template filled with real tool output. This is a
    deliberate Phase 1 placeholder for a real LLM router — see
    docs/ARCHITECTURE.md §7/§11: it will be replaced, not extended."""

    name = "mock"

    async def respond(self, db: AsyncSession, *, portfolio: Portfolio, message: str, mode: str) -> ModelResponse:
        lowered = message.lower()
        calls: list[ToolCallRecord] = []

        async def use(tool_name: str, **kwargs: Any) -> dict:
            result = await call_tool(tool_name, db, portfolio, **kwargs)
            calls.append(ToolCallRecord(tool_name=tool_name, arguments=kwargs, result=result))
            return result

        if any(k in lowered for k in ["stress test", "shock", "what if"]):
            data = await use("run_stress_test")
            text = self._stress_test_text(data, mode)

        elif any(k in lowered for k in ["monte carlo", "simulation", "simulate"]):
            data = await use("run_monte_carlo")
            text = self._monte_carlo_text(data, mode)

        elif "backtest" in lowered:
            data = await use("run_backtest")
            text = self._backtest_text(data, mode)

        elif any(k in lowered for k in ["sharpe", "sortino", "value at risk", " var ", "var?", "cvar"]) or lowered.startswith("var "):
            data = await use("get_risk_profile")
            text = self._risk_ratios_text(data, mode)

        elif "event" in lowered and any(k in lowered for k in ["affect", "impact"]):
            data = await use("get_event_impact")
            text = self._event_impact_text(data, mode)

        elif any(k in lowered for k in ["press release", "search news", "rbi statement", "ingested news"]):
            query = None
            for kw in ["about", "regarding", "on"]:
                if f" {kw} " in lowered:
                    query = message.split(f" {kw} ", 1)[1].strip() or None
                    break
            data = await use("search_news", query=query)
            text = self._search_news_text(data, mode)

        elif any(
            k in lowered
            for k in ["knowledge base", "research", "relevant documents", "find documents", "evidence for", "evidence of"]
        ):
            query = None
            for kw in ["about", "regarding", "on", "for", "of"]:
                if f" {kw} " in lowered:
                    query = message.split(f" {kw} ", 1)[1].strip() or None
                    break
            data = await use("search_knowledge_base", query=query or message, top_k=3)
            text = self._knowledge_base_text(data, mode)

        elif any(k in lowered for k in ["news", "event", "what's happening", "whats happening", "headlines", "market moving"]):
            data = await use("get_events")
            text = self._events_text(data["events"], mode)

        elif any(
            k in lowered for k in ["revision", "revised", "vintage", "inflation history", "gdp history"]
        ) and any(k in lowered for k in ["inflation", "cpi", "gdp"]):
            code = "gdp_growth" if "gdp" in lowered else "cpi_inflation"
            data = await use("get_macro_history", code=code)
            text = self._macro_history_text(data, mode)

        elif any(k in lowered for k in ["gdp", "inflation", "cpi", "repo rate", "interest rate", "macro", "g-sec", "gsec"]):
            data = await use("get_macro_indicators")
            text = self._macro_text(data["indicators"], mode)

        elif any(
            k in lowered
            for k in ["should i buy", "should i sell", "should i add", "thinking of buying", "thinking of selling"]
        ):
            side = "sell" if "sell" in lowered else "buy"
            kwargs: dict[str, Any] = {"side": side}
            symbol = self._guess_symbol(message)
            if symbol:
                kwargs["symbol"] = symbol
            data = await use("preview_trade", **kwargs)
            text = self._preview_trade_text(data, mode)

        elif any(
            k in lowered
            for k in ["how was that trade", "how did that trade", "evaluate my trade", "evaluate that trade", "review my trade", "review that order"]
        ):
            data = await use("evaluate_order")
            text = self._evaluate_order_text(data, mode)

        elif any(k in lowered for k in ["broker", "zerodha", "kite", "linked account"]):
            data = await use("get_broker_holdings")
            text = self._broker_holdings_text(data, mode)

        elif any(
            k in lowered
            for k in [
                "dividend", "stock split", "bonus issue", "rights issue", "buyback", "corporate action",
            ]
        ):
            symbol = self._guess_symbol(message) or "RELIANCE"
            data = await use("get_corporate_actions", symbol=symbol)
            text = self._corporate_actions_text(data, mode)

        elif any(
            k in lowered
            for k in [
                "fundamentals", "roe", "roce", "p/e", "pe ratio", "balance sheet", "income statement",
                "cash flow", "revenue", "earnings", "eps", "debt to equity", "debt/equity",
            ]
        ):
            symbol = self._guess_symbol(message) or "RELIANCE"
            data = await use("get_fundamentals", symbol=symbol)
            text = self._fundamentals_text(data, mode)

        elif any(
            k in lowered
            for k in [
                "options chain", "option chain", "greeks", "implied volatility", "delta", "gamma", "theta",
                "vega", "call option", "put option", "strike price",
            ]
        ):
            symbol = self._guess_symbol(message) or "RELIANCE"
            if "chain" in lowered:
                data = await use("get_options_chain", symbol=symbol)
                text = self._options_chain_text(data, mode)
            else:
                option_type = "put" if "put" in lowered else "call"
                kwargs: dict[str, Any] = {"symbol": symbol, "option_type": option_type}
                strike_match = re.search(r"\b(\d{2,6}(?:\.\d+)?)\b", message)
                if strike_match:
                    kwargs["strike"] = float(strike_match.group(1))
                data = await use("price_option", **kwargs)
                text = self._price_option_text(data, mode)

        elif any(k in lowered for k in ["sector", "concentrat", "diversif"]):
            data = await use("get_sector_exposure")
            text = self._sector_exposure_text(data["sector_exposure"], mode)

        elif any(k in lowered for k in ["risk"]):
            portfolio_data = await use("get_portfolio")
            risk_data = await use("get_risk_profile")
            text = self._risk_text(portfolio_data, risk_data, mode)

        elif any(k in lowered for k in ["biggest", "largest", "top holding"]):
            data = await use("get_holdings")
            text = self._biggest_holding_text(data["holdings"], mode)

        elif any(k in lowered for k in ["down", "up", "pnl", "p&l", "loss", "profit", "today"]):
            data = await use("get_portfolio")
            text = self._day_pnl_text(data, mode)

        else:
            data = await use("get_portfolio")
            text = self._summary_text(data, mode)

        return ModelResponse(text=text, tool_calls=calls)

    @staticmethod
    def _day_pnl_text(data: dict, mode: str) -> str:
        direction = "up" if data["day_pnl"] >= 0 else "down"
        if mode == "quant":
            return (
                f"Day P&L: {data['day_pnl']:+.2f} INR ({data['day_pnl_pct']:+.3f}%). "
                f"Total unrealized P&L: {data['total_pnl']:+.2f} INR ({data['total_pnl_pct']:+.3f}%). "
                f"Portfolio risk score: {data['risk_score']}/5. [DEMO DATA]"
            )
        return (
            f"Your portfolio is {direction} {abs(data['day_pnl_pct']):.2f}% today "
            f"({data['day_pnl']:+.0f} INR). [DEMO DATA — simulated prices]"
        )

    @staticmethod
    def _sector_exposure_text(sector_exposure: list[dict], mode: str) -> str:
        if not sector_exposure:
            return "You don't have any holdings yet, so there's no sector exposure to show."
        top = sector_exposure[0]
        if mode == "quant":
            breakdown = ", ".join(f"{s['sector']} {s['weight_pct']:.1f}%" for s in sector_exposure)
            return f"Sector weights: {breakdown}. [DEMO DATA]"
        return (
            f"Your largest sector exposure is {top['sector']} at {top['weight_pct']:.0f}% of your portfolio. "
            f"[DEMO DATA — simulated prices]"
        )

    @staticmethod
    def _risk_text(portfolio_data: dict, risk_data: dict, mode: str) -> str:
        vol = portfolio_data["annualized_volatility_pct"]
        beta = portfolio_data["beta_vs_nifty"]
        var95 = risk_data.get("var_95_pct")
        sharpe = risk_data.get("sharpe_ratio")
        if mode == "quant":
            vol_text = f"{vol:.1f}%" if vol is not None else "insufficient history"
            beta_text = f"{beta:.2f}" if beta is not None else "insufficient history"
            var_text = f"{var95:.2f}%" if var95 is not None else f"needs {20 - risk_data.get('sample_size', 0)} more days of history"
            sharpe_text = f"{sharpe:.2f}" if sharpe is not None else "insufficient history"
            return (
                f"Concentration score: {portfolio_data['concentration_score']:.1f}/100 (HHI-based). "
                f"Annualized volatility: {vol_text}. Beta vs NIFTY 50: {beta_text}. "
                f"95% 1-day VaR: {var_text}. Sharpe ratio: {sharpe_text} "
                f"(assumed risk-free rate {risk_data['risk_free_rate_annual_pct']}%). "
                f"Composite risk score: {portfolio_data['risk_score']}/5. [DEMO DATA]"
            )
        labels = {1: "low", 2: "fairly low", 3: "moderate", 4: "elevated", 5: "high"}
        var_sentence = (
            f" On a bad day (1-in-20), historical simulation suggests you could lose about {var95:.1f}%."
            if var95 is not None
            else ""
        )
        return (
            f"Your portfolio's overall risk is {labels[portfolio_data['risk_score']]} "
            f"({portfolio_data['risk_score']}/5). This reflects how concentrated your holdings are "
            f"and how much they've moved historically.{var_sentence} [DEMO DATA]"
        )

    @staticmethod
    def _risk_ratios_text(data: dict, mode: str) -> str:
        if data["sample_size"] < 20:
            return (
                f"Not enough price history yet to compute VaR/CVaR/Sharpe/Sortino reliably "
                f"(only {data['sample_size']} days available, need at least 20). [DEMO DATA]"
            )
        if mode == "quant":
            return (
                f"VaR 95%/99%: {data['var_95_pct']:.2f}% / {data['var_99_pct']:.2f}%. "
                f"CVaR 95%/99%: {data['cvar_95_pct']:.2f}% / {data['cvar_99_pct']:.2f}%. "
                f"Sharpe: {data['sharpe_ratio']:.2f}. Sortino: {data['sortino_ratio']:.2f}. "
                f"Max drawdown: {data['max_drawdown_pct']:.2f}%. "
                f"(Assumed risk-free rate {data['risk_free_rate_annual_pct']}%, {data['sample_size']} trading days "
                f"of history — historical simulation, not a parametric estimate.) [DEMO DATA]"
            )
        return (
            f"Historically, there's a 1-in-20 chance of losing more than {data['var_95_pct']:.1f}% in a day "
            f"(and a 1-in-100 chance of losing more than {data['var_99_pct']:.1f}%), based on "
            f"{data['sample_size']} days of simulated price history. Sharpe ratio (risk-adjusted return): "
            f"{data['sharpe_ratio']:.2f}. [DEMO DATA]"
        )

    @staticmethod
    def _stress_test_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"Couldn't run that stress test: {data['error']} [DEMO DATA]"
        direction = "lose" if data["estimated_impact"] < 0 else "gain"
        if mode == "quant":
            return (
                f"Shock: {data['target']} {data['shock_pct']:+.1f}%. Estimated impact: "
                f"{data['estimated_impact']:+.2f} INR ({data['estimated_impact_pct']:+.3f}%). "
                f"Portfolio value {data['portfolio_value_before']:.2f} -> {data['portfolio_value_after']:.2f} INR. "
                f"{data['assumptions']} [DEMO DATA]"
            )
        return (
            f"If {data['target']} moved {data['shock_pct']:+.0f}%, your portfolio would {direction} about "
            f"{abs(data['estimated_impact_pct']):.1f}% ({data['estimated_impact']:+.0f} INR), based on each "
            f"holding's historical sensitivity. [DEMO DATA — hypothetical scenario, not a forecast]"
        )

    @staticmethod
    def _monte_carlo_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"Couldn't run a simulation: {data['error']} [DEMO DATA]"
        if mode == "quant":
            return (
                f"{data['method']} simulation, {data['num_paths']} paths, {data['horizon_days']}-day horizon. "
                f"Terminal value percentiles — P5: {data['p5']:.2f}, P50: {data['p50']:.2f}, P95: {data['p95']:.2f} INR. "
                f"Probability of loss: {data['probability_of_loss_pct']:.1f}%. {data['assumptions']} [DEMO DATA]"
            )
        return (
            f"Over the next {data['horizon_days']} days, a {data['method']} simulation of "
            f"{data['num_paths']} scenarios suggests your portfolio could range from about "
            f"{data['p5']:.0f} to {data['p95']:.0f} INR (currently {data['current_value']:.0f}), with a "
            f"{data['probability_of_loss_pct']:.0f}% chance of ending up down. This is a projection under "
            f"stated assumptions, not a prediction. [DEMO DATA]"
        )

    @staticmethod
    def _backtest_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"Couldn't run a backtest: {data['error']} [DEMO DATA]"
        if data["cagr_pct"] is None:
            return "Not enough price history to backtest this portfolio yet. [DEMO DATA]"
        if mode == "quant":
            return (
                f"Buy-and-hold backtest, {data['num_trading_days']} trading days: CAGR {data['cagr_pct']:+.2f}%, "
                f"max drawdown {data['max_drawdown_pct']:.2f}%, annualized volatility "
                f"{data['annualized_volatility_pct'] if data['annualized_volatility_pct'] is not None else 'n/a'}%. "
                f"{data['assumptions']} [DEMO DATA]"
            )
        return (
            f"If you'd held today's portfolio weights over the last {data['num_trading_days']} trading days "
            f"(simulated history), it would have returned {data['total_return_pct']:+.1f}% "
            f"(~{data['cagr_pct']:+.1f}% annualized), with a worst drawdown of {data['max_drawdown_pct']:.1f}%. "
            f"No costs or rebalancing assumed. [DEMO DATA]"
        )

    @staticmethod
    def _events_text(events: list[dict], mode: str) -> str:
        if not events:
            return "No market events available right now. [DEMO DATA]"
        if mode == "quant":
            lines = "; ".join(
                f"{e['headline']} ({e['event_type']}, {e['severity']}, {e['direction']}, target={e['primary_target']})"
                for e in events[:3]
            )
            return f"Recent events: {lines} [DEMO DATA — seeded, not a live feed]"
        top = events[0]
        return (
            f"Latest: \"{top['headline']}\" ({top['severity']} severity, {top['direction']} for "
            f"{top['primary_target']}). Ask \"how does this event affect my portfolio\" for an impact estimate. "
            f"[DEMO DATA — seeded events, not a live news feed]"
        )

    @staticmethod
    def _event_impact_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"Couldn't assess event impact: {data['error']} [DEMO DATA]"
        direction = "lose" if data["estimated_impact"] < 0 else "gain"
        if mode == "quant":
            return (
                f"Event: \"{data['headline']}\" ({data['severity']}, {data['direction']}). Target: {data['target']}, "
                f"shock {data['shock_pct']:+.1f}%. Estimated impact: {data['estimated_impact']:+.2f} INR "
                f"({data['estimated_impact_pct']:+.3f}%). {data['assumptions']} [DEMO DATA]"
            )
        return (
            f"\"{data['headline']}\" — based on its severity, your portfolio would likely {direction} about "
            f"{abs(data['estimated_impact_pct']):.1f}% ({data['estimated_impact']:+.0f} INR). This is a "
            f"severity-based estimate, not a calibrated forecast. [DEMO DATA]"
        )

    @staticmethod
    def _macro_text(indicators: list[dict], mode: str) -> str:
        if not indicators:
            return "No macro data available. [DEMO DATA]"
        if mode == "quant":
            lines = ", ".join(f"{i['name']} {i['value']}{i['unit']}" for i in indicators)
            return f"Macro snapshot: {lines} [DEMO DATA — seeded, not RBI/MOSPI-fetched]"
        # All indicators, not just a truncated slice — there are only ~7 and
        # a user asking about a specific one (e.g. "repo rate") shouldn't
        # have it silently dropped by an arbitrary cutoff.
        headline = ", ".join(f"{i['name']}: {i['value']}{i['unit']}" for i in indicators)
        return f"Current macro snapshot — {headline}. [DEMO DATA]"

    @staticmethod
    def _macro_history_text(data: dict, mode: str) -> str:
        if not data.get("releases"):
            return f"{data.get('note', 'No history available.')} [DEMO DATA]"
        releases = data["releases"]
        if mode == "quant":
            lines = "; ".join(
                f"{r['period']} rev{r['revision_number']}={r['value']} (released {r['release_date']})"
                for r in releases
            )
            return f"{data['code']} vintage history: {lines} [DEMO DATA — synthetic, only CPI/GDP have real revisions]"
        latest = releases[-1]
        was_revised = any(r["period"] == latest["period"] and r["revision_number"] > 0 for r in releases)
        revision_note = " (this figure has since been revised)" if was_revised and latest["revision_number"] == 0 else ""
        return (
            f"As of the date requested, the most recently known {data['code']} reading was {latest['value']} "
            f"for the period ending {latest['period']} (published {latest['release_date']}){revision_note}. "
            f"[DEMO DATA — synthetic vintage history]"
        )

    _TICKER_RE = re.compile(r"\b[A-Z]{2,10}\b")
    _TICKER_STOPWORDS = {"I", "AI"}

    @classmethod
    def _guess_symbol(cls, message: str) -> str | None:
        # Best-effort only — the keyword router can't do real entity
        # extraction. A real model (OllamaModelProvider) parses this
        # properly via its tool-calling arguments instead of this heuristic.
        matches = [m for m in cls._TICKER_RE.findall(message) if m not in cls._TICKER_STOPWORDS]
        return matches[0] if matches else None

    @staticmethod
    def _preview_trade_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"Couldn't preview that trade: {data['error']} [DEMO DATA]"
        afford_note = "" if data["affordable"] else " — you don't have enough cash/holding for this right now"
        if mode == "quant":
            return (
                f"{data['side'].upper()} {data['quantity']} {data['symbol']} @ ~{data['estimated_fill_price']:.2f} "
                f"(slippage {data['estimated_slippage_pct']:.3f}%, brokerage {data['estimated_brokerage']:.2f} INR). "
                f"Cash: {data['cash_before']:.2f} -> {data['cash_after']:.2f} INR. Concentration: "
                f"{data['concentration_score_before']:.1f} -> {data['concentration_score_after']:.1f}/100"
                f"{afford_note}. [DEMO DATA — paper trading]"
            )
        return (
            f"If you {data['side']} {data['quantity']} {data['symbol']}, it would fill around "
            f"{data['estimated_fill_price']:.2f} INR after slippage and fees, leaving "
            f"{data['cash_after']:.0f} INR cash{afford_note}. This would move your concentration score from "
            f"{data['concentration_score_before']:.0f} to {data['concentration_score_after']:.0f} out of 100. "
            f"[DEMO DATA — paper trading, not real money]"
        )

    @staticmethod
    def _evaluate_order_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"Couldn't evaluate that: {data['error']} [DEMO DATA]"
        if data["status"] == "rejected":
            return f"That order was rejected — it never filled, so there's nothing to evaluate yet. [DEMO DATA]"
        pct = data["fill_percentile_in_30d_range"]
        range_note = (
            f"That's around the {pct:.0f}th percentile of the last 30 trading days' range "
            f"({data['range_30d_low']:.2f}-{data['range_30d_high']:.2f})."
            if pct is not None
            else "Not enough recent price history to place that in context."
        )
        if mode == "quant":
            return (
                f"{data['side'].upper()} filled at {data['fill_price']:.2f} INR (slippage {data['slippage_pct']:.3f}%, "
                f"brokerage {data['brokerage_fee']:.2f} INR). {range_note} {data['assumptions']} [DEMO DATA]"
            )
        return f"You {data['side']} at {data['fill_price']:.2f} INR. {range_note} {data['assumptions']} [DEMO DATA]"

    @staticmethod
    def _broker_holdings_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"{data['error']} [DEMO DATA]"
        mock_note = " (a simulated connection — no real brokerage is linked)" if data["is_mock"] else ""
        if not data["holdings"]:
            return f"Your {data['broker']} account is connected but has no holdings{mock_note}. [DEMO DATA]"
        if mode == "quant":
            lines = ", ".join(f"{h['symbol']} {h['quantity']}@{h['avg_price']:.2f}" for h in data["holdings"])
            return f"{data['broker']} holdings{mock_note}: {lines}. Total value {data['total_value']:.2f} INR. [DEMO DATA]"
        return (
            f"Your {data['broker']} account{mock_note} holds {len(data['holdings'])} positions worth about "
            f"{data['total_value']:.0f} INR. [DEMO DATA]"
        )

    @staticmethod
    def _search_news_text(data: dict, mode: str) -> str:
        articles = data["articles"]
        if not articles:
            return f"{data.get('note', 'No matching news found.')} [DEMO DATA]"
        mock_note = " (illustrative mock set)" if data.get("is_mock") else " (real ingested articles)"
        if mode == "quant":
            lines = "; ".join(f"{a['title']} — {a['publisher']}, {a['published_at']}" for a in articles[:5])
            return f"News{mock_note}: {lines} [DEMO DATA]"
        top = articles[0]
        return (
            f"Most recent: \"{top['title']}\" ({top['publisher']}, {top['published_at']}). "
            f"{len(articles)} article(s) found{mock_note}. [DEMO DATA]"
        )

    @staticmethod
    def _knowledge_base_text(data: dict, mode: str) -> str:
        results = data.get("results", [])
        if not results:
            return f"{data.get('note', 'No relevant documents found.')} [DEMO DATA]"
        if mode == "quant":
            lines = "; ".join(f"{r['title']} (score {r['score']})" for r in results)
            return f"Retrieved: {lines} [DEMO DATA]"
        top = results[0]
        return (
            f"Most relevant source: \"{top['title']}\" ({top['publisher']}, similarity {top['score']}). "
            f"{len(results)} document(s) retrieved. [DEMO DATA]"
        )

    @staticmethod
    def _corporate_actions_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"Couldn't get corporate actions: {data['error']} [DEMO DATA]"
        actions = data["actions"]
        if not actions:
            return f"No corporate actions on record for {data['symbol']}. [DEMO DATA]"
        if mode == "quant":
            lines = "; ".join(
                f"{a['action_type']}"
                + (f" ratio {a['ratio']}" if a["ratio"] else "")
                + (f" ₹{a['amount']}/share" if a["amount"] else "")
                + f" (ex {a['ex_date']})"
                for a in actions
            )
            return f"{data['symbol']} corporate actions: {lines} [DEMO DATA — synthetic record]"
        latest = actions[-1]
        detail = (
            f"a {latest['action_type']} (ratio {latest['ratio']})"
            if latest["ratio"]
            else f"a {latest['action_type']} of ₹{latest['amount']}/share"
            if latest["amount"]
            else f"a {latest['action_type']}"
        )
        return (
            f"{data['symbol']}'s most recent corporate action on record is {detail}, ex-date {latest['ex_date']}. "
            f"{len(actions)} action(s) total. [DEMO DATA — synthetic record, not a real company's actual history]"
        )

    @staticmethod
    def _fundamentals_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"Couldn't get fundamentals: {data['error']} [DEMO DATA]"
        r = data["ratios"]
        if mode == "quant":
            return (
                f"{data['symbol']} FY{data['fiscal_year']} (period ended {data['period_end']}): revenue "
                f"{data['revenue']:.0f}, PAT {data['pat']:.0f}, EPS {data['eps']:.2f}. ROE "
                f"{r['roe_pct']:.2f}% , ROCE {r['roce_pct']:.2f}%, D/E {r['debt_to_equity']:.2f}, current ratio "
                f"{r['current_ratio']:.2f}, P/E {r['pe_ratio']:.2f}, P/B {r['pb_ratio']:.2f}, EV/EBITDA "
                f"{r['ev_to_ebitda']:.2f}, FCF yield {r['fcf_yield_pct']:.2f}%. {data['assumptions']} "
                f"[DEMO DATA — synthetic fundamentals]"
            )
        return (
            f"{data['symbol']}'s most recently available results (FY{data['fiscal_year']}, ended "
            f"{data['period_end']}) show revenue of {data['revenue']:.0f} and profit after tax of "
            f"{data['pat']:.0f}, with an ROE of {r['roe_pct']:.1f}% and a P/E of {r['pe_ratio']:.1f}. "
            f"[DEMO DATA — synthetic fundamentals, not a real company's actual financials]"
        )

    @staticmethod
    def _options_chain_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"Couldn't get that options chain: {data['error']} [DEMO DATA]"
        contracts = data["contracts"]
        if not contracts:
            return "No option contracts available. [DEMO DATA]"
        atm_call = min(
            (c for c in contracts if c["option_type"] == "call"),
            key=lambda c: abs(c["strike"] - data["spot"]),
            default=None,
        )
        if mode == "quant":
            lines = "; ".join(
                f"{c['option_type']} {c['strike']} @ {c['premium']:.2f} (IV {c['iv_pct']:.1f}%, delta {c['delta']:.2f})"
                for c in contracts[:6]
            )
            return (
                f"{data['symbol']} chain, expiry {data['expiry']} ({data['days_to_expiry']}d), spot "
                f"{data['spot']:.2f}: {lines}. Risk-free rate {data['risk_free_rate_annual_pct']}%. {data['note']} "
                f"[DEMO DATA — synthetic chain, assumed IV, not a real options market]"
            )
        atm_note = (
            f" The near-the-money {atm_call['strike']:.0f} call is priced around {atm_call['premium']:.2f} INR "
            f"(assumed IV {atm_call['iv_pct']:.0f}%)."
            if atm_call
            else ""
        )
        return (
            f"{data['symbol']} spot is {data['spot']:.2f}, options expiring {data['expiry']} "
            f"({data['days_to_expiry']} days out).{atm_note} [DEMO DATA — synthetic chain, assumed volatility, "
            f"not a real options market]"
        )

    @staticmethod
    def _price_option_text(data: dict, mode: str) -> str:
        if "error" in data:
            return f"Couldn't price that option: {data['error']} [DEMO DATA]"
        if mode == "quant":
            return (
                f"{data['symbol']} {data['strike']:.0f} {data['option_type']} exp {data['expiry']}: premium "
                f"{data['premium']:.2f} INR, IV {data['iv_pct']:.1f}% (assumed), delta {data['delta']:.4f}, "
                f"gamma {data['gamma']:.6f}, theta {data['theta']:.4f}/day, vega {data['vega']:.4f}, "
                f"rho {data['rho']:.4f}. [DEMO DATA — synthetic pricing]"
            )
        return (
            f"The {data['symbol']} {data['strike']:.0f} {data['option_type']} expiring {data['expiry']} is "
            f"priced around {data['premium']:.2f} INR under an assumed {data['iv_pct']:.0f}% implied "
            f"volatility, with a delta of {data['delta']:.2f}. [DEMO DATA — synthetic pricing, not a real "
            f"options market]"
        )

    @staticmethod
    def _biggest_holding_text(holdings: list[dict], mode: str) -> str:
        if not holdings:
            return "You don't have any holdings yet."
        biggest = max(holdings, key=lambda h: h["market_value"])
        if mode == "quant":
            return f"Largest position by market value: {biggest['symbol']} at {biggest['market_value']:.2f} INR. [DEMO DATA]"
        return f"Your biggest holding is {biggest['symbol']}, worth about {biggest['market_value']:.0f} INR. [DEMO DATA]"

    @staticmethod
    def _summary_text(data: dict, mode: str) -> str:
        if data["holdings_count"] == 0:
            return "This portfolio doesn't have any holdings yet — add one to see analytics. [DEMO DATA]"
        if mode == "quant":
            return (
                f"Total value {data['total_value']:.2f} INR across {data['holdings_count']} holdings. "
                f"Total P&L {data['total_pnl']:+.2f} INR ({data['total_pnl_pct']:+.2f}%). "
                f"Day P&L {data['day_pnl']:+.2f} INR. Risk score {data['risk_score']}/5. [DEMO DATA]"
            )
        return (
            f"Your portfolio is worth about {data['total_value']:.0f} INR across "
            f"{data['holdings_count']} holdings, {'up' if data['total_pnl'] >= 0 else 'down'} "
            f"{abs(data['total_pnl_pct']):.1f}% overall. Ask me about risk, sector exposure, "
            f"or your biggest holding. [DEMO DATA]"
        )


def get_model_provider() -> ModelProvider:
    # Deferred import: ollama_provider.py imports ModelProvider/ModelResponse
    # from this module, so importing it at module level here would be
    # circular. See .env AI_PROVIDER and docs/ARCHITECTURE.md Phase 3.5
    # trade-offs — the checked-in default stays "mock".
    from app.core.config import get_settings

    if get_settings().ai_provider == "ollama":
        from app.domains.ai.ollama_provider import OllamaModelProvider

        return OllamaModelProvider()

    return MockModelProvider()
