import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.domains.market_data.service import live_market_state

router = APIRouter()

TICK_INTERVAL_SECONDS = 3


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        dead: list[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_text(json.dumps(payload, default=str))
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/market.price")
async def market_price_stream(websocket: WebSocket) -> None:
    """Channel: market.price — pushes simulated last-traded-price ticks for
    the mock NIFTY-subset universe. Every payload is tagged is_mock=true."""
    await manager.connect(websocket)
    try:
        await websocket.send_text(
            json.dumps({"type": "snapshot", "quotes": live_market_state.all_quotes()}, default=str)
        )
        while True:
            # Client isn't expected to send anything; just keep the socket alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def run_tick_loop() -> None:
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        changes = live_market_state.tick_all()
        if changes:
            await manager.broadcast({"type": "tick", "quotes": changes})
