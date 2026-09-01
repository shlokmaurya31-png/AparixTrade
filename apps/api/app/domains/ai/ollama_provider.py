"""Real LLM-backed ModelProvider — local Ollama, model configurable via
OLLAMA_MODEL (default llama3.1). See docs/ARCHITECTURE.md Phase 3.5
trade-offs for why Ollama over a paid API, why the hallucination guardrail
here is best-effort rather than exhaustive, and why AI_PROVIDER still
defaults to "mock" in the checked-in .env.example.

The tool-calling loop runs against the exact same TOOL_REGISTRY
(domains/ai/tools.py) that MockModelProvider uses — the "never invent a
number" guarantee from Phase 1 is structural (every number traces to a real
tool call, persisted as an AIToolCall row), not specific to which provider
answered.
"""

import json
import re

import httpx

from app.core.config import get_settings
from app.domains.ai.provider import ModelProvider, ModelResponse, ToolCallRecord
from app.domains.ai.tool_schemas import TOOL_SCHEMAS, assert_schemas_match_registry
from app.domains.ai.tools import TOOL_REGISTRY, call_tool
from app.models.portfolio import Portfolio
from sqlalchemy.ext.asyncio import AsyncSession

assert_schemas_match_registry(set(TOOL_REGISTRY.keys()))

MAX_TOOL_ROUNDS = 4

BASE_SYSTEM_PROMPT = (
    "You are Aparix, an AI assistant inside a personal financial intelligence dashboard for Indian retail "
    "investors. CRITICAL RULE: never state a specific number about the user's portfolio, holdings, risk, "
    "market data, events, or macro indicators unless it came directly from a tool call you made in this "
    "conversation. If no available tool can answer the question, say so honestly instead of guessing or "
    "estimating. All market, portfolio, and macro data in this system is simulated/demo data for a "
    "development build — never imply it is live or real. Never say something is 'guaranteed' or 'risk-free' "
    "or promise a certain outcome; describe results as estimates, scenarios, or historical simulations."
)

MODE_INSTRUCTIONS: dict[str, str] = {
    "simple": (
        "Respond in plain, friendly English for a beginner investor. Avoid jargon; briefly explain any term "
        "you must use. Keep answers to 2-4 sentences."
    ),
    "quant": (
        "Respond with precise quantitative language: exact figures, percentages, and the relevant statistical "
        "or financial terms (Sharpe, VaR, beta, etc). Be terse and data-dense."
    ),
    "analyst": (
        "Respond like an equity research analyst: a brief conclusion up front, then the supporting figures. "
        "Professional, structured tone."
    ),
    "risk_officer": (
        "Respond focused entirely on risk: concentration, volatility, tail risk, and what could go wrong. "
        "Be direct about downside — this mode exists to surface risk, not reassure."
    ),
    "portfolio_manager": (
        "Respond focused on portfolio construction and allocation: diversification, position sizing, and how "
        "holdings work together as a whole, not just individually."
    ),
    "macro_economist": (
        "Respond emphasizing macro context (rates, inflation, growth, currency) and how it connects to the "
        "portfolio — use get_macro_indicators when relevant."
    ),
}

FALLBACK_MODE_NOTE = (
    "The user's selected AI mode ('{mode}') isn't backed by real data yet — this platform has no options-"
    "analytics or cited-research data source built. Answer in the plain, beginner-friendly 'simple' style "
    "instead, and if the question genuinely needs options or cited-research data, say that capability isn't "
    "available yet rather than improvising a persona you can't back up."
)

_NUMBER_RE = re.compile(r"\d[\d,]*\.?\d*")

# A weaker model can, on a more complex/compound question, "describe" a tool
# call as JSON-ish text instead of actually invoking Ollama's native
# tool_calls mechanism (observed live with llama3.1 on a two-part question
# during Phase 3.5 verification — not a hypothetical). That text would
# otherwise be returned as if it were a real final answer, describing intent
# instead of fulfilling it. Detect the pattern and nudge the model to
# actually call the tool(s), rather than showing the broken output.
_DESCRIBED_TOOL_CALL_RE = re.compile(r'"name"\s*:\s*"[a-z_]+"\s*,\s*"(parameters|arguments)"', re.IGNORECASE)


def _looks_like_described_tool_call(text: str) -> bool:
    return bool(_DESCRIBED_TOOL_CALL_RE.search(text))


def _build_system_prompt(mode: str) -> str:
    style = MODE_INSTRUCTIONS.get(mode) or FALLBACK_MODE_NOTE.format(mode=mode)
    return f"{BASE_SYSTEM_PROMPT}\n\nStyle for this conversation: {style}"


def _apply_guardrail(text: str, tool_calls: list[ToolCallRecord]) -> str:
    """Best-effort, not exhaustive — see docs/ARCHITECTURE.md Phase 3.5
    trade-offs for why a full per-number cross-check isn't done here. This
    only catches the clearest failure mode: the model stating figures
    without having queried any tool at all."""
    if tool_calls:
        return text
    if _NUMBER_RE.search(text):
        return (
            text
            + "\n\n[Note: this response wasn't backed by an Aparix data tool call — treat any figures above as "
            "illustrative, not verified. Try rephrasing so I can look up real data.]"
        )
    return text


class OllamaUnavailableError(Exception):
    pass


class OllamaModelProvider(ModelProvider):
    name = "ollama"

    async def _chat(self, messages: list[dict]) -> dict:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=settings.ollama_request_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json={
                        "model": settings.ollama_model,
                        "messages": messages,
                        "tools": TOOL_SCHEMAS,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                return response.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            raise OllamaUnavailableError(str(exc)) from exc

    async def respond(self, db: AsyncSession, *, portfolio: Portfolio, message: str, mode: str) -> ModelResponse:
        settings = get_settings()
        messages: list[dict] = [
            {"role": "system", "content": _build_system_prompt(mode)},
            {"role": "user", "content": message},
        ]
        calls: list[ToolCallRecord] = []

        try:
            for _ in range(MAX_TOOL_ROUNDS):
                data = await self._chat(messages)
                assistant_message = data.get("message", {})
                tool_calls = assistant_message.get("tool_calls") or []

                if not tool_calls:
                    text = (assistant_message.get("content") or "").strip()

                    if _looks_like_described_tool_call(text):
                        # One corrective nudge, not a silent failure and not
                        # showing the broken output to the user.
                        messages.append({"role": "assistant", "content": text})
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Don't describe a function call as text — actually call the function(s) "
                                    "using the tool-calling mechanism."
                                ),
                            }
                        )
                        continue

                    if not text:
                        text = "I wasn't able to come up with an answer to that — could you rephrase?"
                    return ModelResponse(text=_apply_guardrail(text, calls), tool_calls=calls)

                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_message.get("content") or "",
                        "tool_calls": tool_calls,
                    }
                )

                for tc in tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    fn_args = fn.get("arguments") or {}

                    if fn_name not in TOOL_REGISTRY:
                        result = {"error": f"unknown tool: {fn_name}"}
                    else:
                        try:
                            result = await call_tool(fn_name, db, portfolio, **fn_args)
                        except Exception as exc:  # a weaker model can pass malformed arguments
                            result = {"error": f"tool call failed: {exc}"}

                    calls.append(ToolCallRecord(tool_name=fn_name, arguments=fn_args, result=result))
                    messages.append(
                        {"role": "tool", "content": json.dumps(result, default=str), "tool_call_id": tc.get("id", "")}
                    )

            text = (
                "I gathered some data but couldn't put together a final answer in time — try asking again, "
                "maybe more specifically."
            )
            return ModelResponse(text=_apply_guardrail(text, calls), tool_calls=calls)

        except OllamaUnavailableError as exc:
            return ModelResponse(
                text=(
                    f"Couldn't reach the local Ollama server at {settings.ollama_base_url} ({exc}). Make sure "
                    f"`ollama serve` is running and `{settings.ollama_model}` is pulled. [DEMO DATA]"
                ),
                tool_calls=[],
            )
