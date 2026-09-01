import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_v1_router
from app.core.config import get_settings
from app.core.db import AsyncSessionLocal, init_models
from app.domains.events.service import seed_if_needed as seed_events_if_needed
from app.domains.macro.service import seed_if_needed as seed_macro_if_needed
from app.domains.market_data.service import live_market_state, seed_if_needed as seed_market_if_needed
from app.domains.market_data.websocket import router as market_ws_router, run_tick_loop

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    async with AsyncSessionLocal() as db:
        await seed_market_if_needed(db)
        await live_market_state.init_from_db(db)
        await seed_macro_if_needed(db)
        await seed_events_if_needed(db)

    tick_task = asyncio.create_task(run_tick_loop())
    try:
        yield
    finally:
        tick_task.cancel()


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
