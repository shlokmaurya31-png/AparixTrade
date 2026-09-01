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

        elif any(k in lowered for k in ["news", "event", "what's happening", "whats happening", "headlines", "market moving"]):
            data = await use("get_events")
            text = self._events_text(data["events"], mode)

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
