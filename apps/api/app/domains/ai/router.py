from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.domains.ai.provider import get_model_provider
from app.domains.audit.service import log_action
from app.domains.portfolios.service import PortfolioNotFoundError, get_portfolio
from app.models.ai import AIMessage, AISession, AIToolCall
from app.models.user import User
from app.schemas.ai import AiConfigOut, ChatRequest, ChatResponse, ToolCallOut

router = APIRouter(prefix="/ai", tags=["ai"])

# Mirrors MockModelProvider's style branches (domains/ai/provider.py) vs
# OllamaModelProvider.MODE_INSTRUCTIONS (domains/ai/ollama_provider.py) — a
# real per-provider style difference, not just "the mode value is accepted".
_MOCK_SUPPORTED_MODES = ["simple", "quant"]


@router.get("/config", response_model=AiConfigOut)
async def get_ai_config() -> AiConfigOut:
    settings = get_settings()
    if settings.ai_provider == "ollama":
        from app.domains.ai.ollama_provider import MODE_INSTRUCTIONS

        return AiConfigOut(
            provider="ollama", model=settings.ollama_model, supported_modes=list(MODE_INSTRUCTIONS.keys())
        )
    return AiConfigOut(provider="mock", model=None, supported_modes=_MOCK_SUPPORTED_MODES)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    try:
        portfolio = await get_portfolio(db, portfolio_id=payload.portfolio_id, user_id=current_user.id)
    except PortfolioNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found") from exc

    mode = current_user.preferences.ai_mode

    session: AISession | None = None
    if payload.session_id is not None:
        result = await db.execute(
            select(AISession).where(AISession.id == payload.session_id, AISession.user_id == current_user.id)
        )
        session = result.scalar_one_or_none()
    if session is None:
        session = AISession(user_id=current_user.id, mode=mode)
        db.add(session)
        await db.flush()

    db.add(AIMessage(session_id=session.id, role="user", content=payload.message))

    provider = get_model_provider()
    response = await provider.respond(db, portfolio=portfolio, message=payload.message, mode=mode)

    assistant_message = AIMessage(
        session_id=session.id, role="assistant", content=response.text, model_provider=provider.name
    )
    db.add(assistant_message)
    await db.flush()

    for call in response.tool_calls:
        db.add(
            AIToolCall(
                message_id=assistant_message.id,
                tool_name=call.tool_name,
                arguments=call.arguments,
                result=call.result,
            )
        )

    await log_action(
        db,
        user_id=current_user.id,
        action="ai.chat",
        input_data={"portfolio_id": str(payload.portfolio_id), "message": payload.message},
        output_data={"tool_calls": [c.tool_name for c in response.tool_calls]},
    )
    await db.commit()

    return ChatResponse(
        session_id=session.id,
        message=response.text,
        mode=mode,
        provider=provider.name,
        tool_calls=[ToolCallOut(tool_name=c.tool_name, arguments=c.arguments, result=c.result) for c in response.tool_calls],
    )
