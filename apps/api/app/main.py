import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.core.migrations import run_migrations
from app.domains.corporate_actions.service import seed_if_needed as seed_corporate_actions_if_needed
from app.domains.events.service import seed_if_needed as seed_events_if_needed
from app.domains.fundamentals.service import seed_if_needed as seed_fundamentals_if_needed
from app.domains.macro.service import (
    seed_if_needed as seed_macro_if_needed,
    seed_vintage_if_needed as seed_macro_vintage_if_needed,
)
from app.domains.market_data.service import live_market_state, seed_if_needed as seed_market_if_needed
from app.domains.market_data.websocket import router as market_ws_router, run_tick_loop
from app.domains.news.service import run_news_ingestion_loop, seed_if_needed as seed_news_if_needed
from app.domains.rag.service import reindex_missing as reindex_rag_if_needed

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()
    async with AsyncSessionLocal() as db:
        await seed_market_if_needed(db)
        await live_market_state.init_from_db(db)
        await seed_macro_if_needed(db)
        await seed_macro_vintage_if_needed(db)
        await seed_events_if_needed(db)
        await seed_fundamentals_if_needed(db)
        await seed_corporate_actions_if_needed(db)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router)
app.include_router(market_ws_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "aparix-api", "mode": "development", "data": "DEMO DATA"}
