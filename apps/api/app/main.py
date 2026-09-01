import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_v1_router
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.core.logging_config import configure_logging
from app.core.middleware import RateLimitMiddleware, RequestIDMiddleware
from app.core.migrations import run_migrations
from app.core.rate_limit import FixedWindowRateLimiter
from app.domains.corporate_actions.service import seed_if_needed as seed_corporate_actions_if_needed
from app.domains.events.service import seed_if_needed as seed_events_if_needed
from app.domains.fundamentals.service import seed_if_needed as seed_fundamentals_if_needed
from app.domains.knowledge_graph.service import seed_if_needed as seed_knowledge_graph_if_needed
from app.domains.macro.service import (
    seed_if_needed as seed_macro_if_needed,
    seed_vintage_if_needed as seed_macro_vintage_if_needed,
)
from app.domains.market_data.service import (
    live_market_state,
    seed_historical_universe_if_needed,
    seed_if_needed as seed_market_if_needed,
)
from app.domains.market_data.websocket import router as market_ws_router, run_tick_loop
from app.domains.news.service import run_news_ingestion_loop, seed_if_needed as seed_news_if_needed
from app.domains.rag.service import reindex_missing as reindex_rag_if_needed

settings = get_settings()
configure_logging()
logger = logging.getLogger("app.errors")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()
    async with AsyncSessionLocal() as db:
        await seed_market_if_needed(db)
        await live_market_state.init_from_db(db)
        # Depends on the seeded securities existing (looks each up by
        # symbol) — after seed_market_if_needed, otherwise independent of
        # every other domain's own seeding.
        await seed_knowledge_graph_if_needed(db)
        await seed_macro_if_needed(db)
        await seed_macro_vintage_if_needed(db)
        await seed_events_if_needed(db)
        await seed_fundamentals_if_needed(db)
        await seed_corporate_actions_if_needed(db)
        # Runs after fundamentals/corporate-actions seeding, not before —
        # both of those use a table-wide "already populated?" count check,
        # and this adds rows to the corporate_actions table too (each
        # historical security's own delisting/merger record); running
        # first would make that count check see rows already exist and
        # skip seeding the real universe entirely. See its own docstring.
        await seed_historical_universe_if_needed(db)
        await seed_news_if_needed(db)
        # Idempotent/incremental (see domains/rag/service.py docstring) —
        # correct to call unconditionally on every startup, not a one-time
        # seed, so it also catches up any article a prior run left unindexed.
        await reindex_rag_if_needed(db)

    tick_task = asyncio.create_task(run_tick_loop())
    # Only a real provider gets a periodic background fetch — the checked-in
    # "mock" default is seeded once above and never polls anything.
    news_task = asyncio.create_task(run_news_ingestion_loop()) if settings.news_provider == "rss" else None
    try:
        yield
    finally:
        tick_task.cancel()
        if news_task is not None:
            news_task.cancel()


app = FastAPI(
    title="Aparix API",
    description="Aparix — Indian financial intelligence platform (Phase 1 foundation). "
    "All market data served by this API in development mode is simulated (DEMO DATA).",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware order matters — Starlette runs the LAST-added middleware
# FIRST on the way in (outermost), so this order gives: CORS (outermost,
# every response — including a 429 or 500 — still gets proper CORS
# headers) -> RequestID (assigned before rate limiting checks/logs it) ->
# RateLimit (innermost, closest to the actual route).
if settings.rate_limit_enabled:
    app.add_middleware(
        RateLimitMiddleware,
        general_limiter=FixedWindowRateLimiter(
            max_requests=settings.rate_limit_general_per_minute, window_seconds=60.0
        ),
        auth_limiter=FixedWindowRateLimiter(max_requests=settings.rate_limit_auth_per_minute, window_seconds=60.0),
    )
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router)
app.include_router(market_ws_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches only what FastAPI's own handlers for HTTPException/
    RequestValidationError don't (Starlette dispatches to the most
    specific registered handler in the exception's MRO, so this never
    shadows those) — a genuinely unexpected error. Logs the real
    exception, with a traceback, server-side and correlated by request ID;
    the client only ever gets a generic message plus that same ID to quote
    back, never the exception's own message — verified empirically before
    this handler existed that Starlette's own default already didn't leak
    a traceback, but this makes the guarantee explicit, tested, and gives
    the response a request ID for correlation, which the framework default
    didn't."""
    request_id = getattr(request.state, "request_id", "-")
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    # A handler registered for the bare `Exception` type runs inside
    # Starlette's ServerErrorMiddleware, which sits OUTSIDE RequestIDMiddleware
    # (see Starlette's Starlette.build_middleware_stack()) — an exception
    # propagating up bypasses that middleware's normal
    # "attach header after call_next returns" path entirely, so the header
    # has to be set here directly, not left to the middleware.
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "aparix-api", "mode": "development", "data": "DEMO DATA"}
