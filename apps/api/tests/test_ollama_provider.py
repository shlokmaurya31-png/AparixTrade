"""OllamaModelProvider is tested against a monkeypatched HTTP layer, never a
live Ollama daemon — a real local-model dependency in the suite would be
slow and non-deterministic across machines/CI. See docs/ARCHITECTURE.md
Phase 3.5 trade-offs. A live smoke test with the real model is done
manually, same as every previous phase.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.core.db import AsyncSessionLocal
from app.domains.ai.ollama_provider import OllamaModelProvider, OllamaUnavailableError, _apply_guardrail
from app.domains.ai.provider import ToolCallRecord
from app.domains.ai.tool_schemas import assert_schemas_match_registry
from app.domains.ai.tools import TOOL_REGISTRY
from app.domains.auth.service import register_user
from app.domains.portfolios.service import add_holding, create_portfolio, get_portfolio


async def _make_portfolio_with_holding() -> tuple[uuid.UUID, uuid.UUID]:
    async with AsyncSessionLocal() as db:
        user = await register_user(
            db, email=f"{uuid.uuid4().hex}@example.com", password="correct-horse-battery", full_name="Ollama Test"
        )
        portfolio = await create_portfolio(db, user_id=user.id, name="Test", kind="long_term")
        await add_holding(
            db, portfolio_id=portfolio.id, user_id=user.id, symbol="RELIANCE", quantity=10, avg_price=2500.0
        )
        return user.id, portfolio.id


# ── Tool-calling loop (mocked HTTP layer) ───────────────────────────────────


async def test_tool_calling_loop_executes_the_real_tool(client: AsyncClient, monkeypatch):
    user_id, portfolio_id = await _make_portfolio_with_holding()

    responses = [
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call_1", "function": {"name": "get_portfolio", "arguments": {}}}],
            }
        },
        {"message": {"role": "assistant", "content": "Your portfolio is doing fine."}},
    ]

    async def fake_chat(self, messages):
        return responses.pop(0)

    monkeypatch.setattr(OllamaModelProvider, "_chat", fake_chat)

    provider = OllamaModelProvider()
    async with AsyncSessionLocal() as db:
        portfolio = await get_portfolio(db, portfolio_id=portfolio_id, user_id=user_id)
        result = await provider.respond(db, portfolio=portfolio, message="how am I doing?", mode="simple")

    assert result.text == "Your portfolio is doing fine."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "get_portfolio"
    # Real computed data came back — not a stub the test defined.
    assert result.tool_calls[0].result["total_value"] > 0
    assert result.tool_calls[0].result["is_mock"] is True


async def test_multi_round_tool_calls_all_execute(client: AsyncClient, monkeypatch):
    user_id, portfolio_id = await _make_portfolio_with_holding()

    responses = [
        {
            "message": {
                "content": "",
                "tool_calls": [{"id": "1", "function": {"name": "get_portfolio", "arguments": {}}}],
            }
        },
        {
            "message": {
                "content": "",
                "tool_calls": [{"id": "2", "function": {"name": "get_sector_exposure", "arguments": {}}}],
            }
        },
        {"message": {"content": "You're concentrated in Energy."}},
    ]

    async def fake_chat(self, messages):
        return responses.pop(0)

    monkeypatch.setattr(OllamaModelProvider, "_chat", fake_chat)

    provider = OllamaModelProvider()
    async with AsyncSessionLocal() as db:
        portfolio = await get_portfolio(db, portfolio_id=portfolio_id, user_id=user_id)
        result = await provider.respond(db, portfolio=portfolio, message="what's my risk?", mode="simple")

    assert [c.tool_name for c in result.tool_calls] == ["get_portfolio", "get_sector_exposure"]
    assert result.text == "You're concentrated in Energy."


async def test_unknown_tool_name_from_model_is_handled_gracefully(client: AsyncClient, monkeypatch):
    user_id, portfolio_id = await _make_portfolio_with_holding()

    responses = [
        {
            "message": {
                "content": "",
                "tool_calls": [{"id": "1", "function": {"name": "not_a_real_tool", "arguments": {}}}],
            }
        },
        {"message": {"content": "ok"}},
    ]

    async def fake_chat(self, messages):
        return responses.pop(0)

    monkeypatch.setattr(OllamaModelProvider, "_chat", fake_chat)

    provider = OllamaModelProvider()
    async with AsyncSessionLocal() as db:
        portfolio = await get_portfolio(db, portfolio_id=portfolio_id, user_id=user_id)
        result = await provider.respond(db, portfolio=portfolio, message="do something weird", mode="simple")

    assert result.tool_calls[0].result == {"error": "unknown tool: not_a_real_tool"}


async def test_malformed_tool_arguments_do_not_crash(client: AsyncClient, monkeypatch):
    user_id, portfolio_id = await _make_portfolio_with_holding()

    responses = [
        {
            "message": {
                "content": "",
                # shock_pct as a string instead of a number — a weaker model can do this
                "tool_calls": [
                    {
                        "id": "1",
                        "function": {
                            "name": "run_stress_test",
                            "arguments": {"target": "NIFTY50", "shock_pct": "not-a-number"},
                        },
                    }
                ],
            }
        },
        {"message": {"content": "ok"}},
    ]

    async def fake_chat(self, messages):
        return responses.pop(0)

    monkeypatch.setattr(OllamaModelProvider, "_chat", fake_chat)

    provider = OllamaModelProvider()
    async with AsyncSessionLocal() as db:
        portfolio = await get_portfolio(db, portfolio_id=portfolio_id, user_id=user_id)
        result = await provider.respond(db, portfolio=portfolio, message="stress test", mode="simple")

    assert "error" in result.tool_calls[0].result


async def test_described_tool_call_text_triggers_a_corrective_retry(client: AsyncClient, monkeypatch):
    """Observed live with llama3.1 on a compound question during Phase 3.5
    verification: the model wrote out a function call as JSON-ish text
    instead of using Ollama's native tool_calls field. That must not be
    handed to the user as if it were a real answer."""
    user_id, portfolio_id = await _make_portfolio_with_holding()

    responses = [
        {
            "message": {
                "content": 'I need to call: {"name": "get_portfolio", "parameters": {}}',
            }
        },
        {
            "message": {
                "content": "",
                "tool_calls": [{"id": "1", "function": {"name": "get_portfolio", "arguments": {}}}],
            }
        },
        {"message": {"content": "Your portfolio is doing well."}},
    ]

    async def fake_chat(self, messages):
        return responses.pop(0)

    monkeypatch.setattr(OllamaModelProvider, "_chat", fake_chat)

    provider = OllamaModelProvider()
    async with AsyncSessionLocal() as db:
        portfolio = await get_portfolio(db, portfolio_id=portfolio_id, user_id=user_id)
        result = await provider.respond(db, portfolio=portfolio, message="how am I doing", mode="simple")

    assert result.text == "Your portfolio is doing well."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "get_portfolio"


async def test_exhausting_tool_rounds_returns_honest_fallback(client: AsyncClient, monkeypatch):
    user_id, portfolio_id = await _make_portfolio_with_holding()

    async def fake_chat(self, messages):
        return {
            "message": {
                "content": "",
                "tool_calls": [{"id": "x", "function": {"name": "get_portfolio", "arguments": {}}}],
            }
        }

    monkeypatch.setattr(OllamaModelProvider, "_chat", fake_chat)

    provider = OllamaModelProvider()
    async with AsyncSessionLocal() as db:
        portfolio = await get_portfolio(db, portfolio_id=portfolio_id, user_id=user_id)
        result = await provider.respond(db, portfolio=portfolio, message="loop forever", mode="simple")

    from app.domains.ai.ollama_provider import MAX_TOOL_ROUNDS

    assert len(result.tool_calls) == MAX_TOOL_ROUNDS
    assert "couldn't put together" in result.text.lower()


async def test_ollama_unavailable_returns_graceful_message_not_a_crash(client: AsyncClient, monkeypatch):
    user_id, portfolio_id = await _make_portfolio_with_holding()

    async def fake_chat(self, messages):
        raise OllamaUnavailableError("connection refused")

    monkeypatch.setattr(OllamaModelProvider, "_chat", fake_chat)

    provider = OllamaModelProvider()
    async with AsyncSessionLocal() as db:
        portfolio = await get_portfolio(db, portfolio_id=portfolio_id, user_id=user_id)
        result = await provider.respond(db, portfolio=portfolio, message="hello", mode="simple")

    assert "ollama" in result.text.lower()
    assert result.tool_calls == []


# ── Guardrail (pure function) ───────────────────────────────────────────────


def test_guardrail_flags_ungrounded_numeric_response():
    text = _apply_guardrail("Your portfolio is worth 50000 rupees.", [])
    assert "[Note:" in text


def test_guardrail_leaves_grounded_response_unchanged():
    call = ToolCallRecord(tool_name="get_portfolio", arguments={}, result={"total_value": 50000})
    text = _apply_guardrail("Your portfolio is worth 50000 rupees.", [call])
    assert text == "Your portfolio is worth 50000 rupees."


def test_guardrail_leaves_non_numeric_ungrounded_response_unchanged():
    text = _apply_guardrail("I don't have enough information to answer that.", [])
    assert text == "I don't have enough information to answer that."


# ── Schema/registry consistency ─────────────────────────────────────────────


def test_tool_schemas_match_registry():
    assert_schemas_match_registry(set(TOOL_REGISTRY.keys()))  # must not raise


def test_tool_schemas_mismatch_is_caught():
    with pytest.raises(RuntimeError):
        assert_schemas_match_registry({"get_portfolio", "totally_made_up_tool"})
