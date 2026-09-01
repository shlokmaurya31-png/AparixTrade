"""ZerodhaKiteAdapter — a real implementation of BrokerAdapter against
Zerodha's Kite Connect v3 REST API (https://kite.trade/docs/connect/v3/).

Built to the documented API contract using plain httpx calls (same approach
as domains/ai/ollama_provider.py — no vendor SDK dependency). NOT live-tested
against a real Kite Connect account: that requires a paid developer
subscription and a registered app, which this project doesn't have. Treat
this as "implemented to spec, unverified against the live API" — wire in
real ZERODHA_API_KEY/ZERODHA_API_SECRET and do a real connect + holdings
sync before trusting it, per docs/ARCHITECTURE.md Phase 5 trade-offs.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import httpx

from app.domains.broker.adapter import (
    BrokerAdapter,
    BrokerConnectError,
    BrokerCredentials,
    BrokerHolding,
    BrokerOrderResult,
    LoginResult,
)

KITE_LOGIN_URL = "https://kite.zerodha.com/connect/login"
KITE_API_BASE = "https://api.kite.trade"
KITE_VERSION = "3"


class ZerodhaKiteAdapter(BrokerAdapter):
    name = "zerodha"

    def get_login_url(self, *, api_key: str | None) -> str:
        if not api_key:
            raise BrokerConnectError("ZERODHA_API_KEY is not configured.")
        return f"{KITE_LOGIN_URL}?v={KITE_VERSION}&api_key={api_key}"

    async def complete_login(
        self, *, api_key: str | None, api_secret: str | None, request_token: str | None
    ) -> LoginResult:
        if not api_key or not api_secret:
            raise BrokerConnectError("ZERODHA_API_KEY / ZERODHA_API_SECRET are not configured.")
        if not request_token:
            raise BrokerConnectError("Missing request_token from the Kite login redirect.")

        # Kite's documented checksum: sha256(api_key + request_token + api_secret)
        checksum = hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode("utf-8")).hexdigest()

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{KITE_API_BASE}/session/token",
                headers={"X-Kite-Version": KITE_VERSION},
                data={"api_key": api_key, "request_token": request_token, "checksum": checksum},
            )
        body = response.json()
        if response.status_code != 200 or body.get("status") != "success":
            raise BrokerConnectError(f"Kite token exchange failed: {body.get('message', response.text)}")

        data = body["data"]
        # Kite doesn't return an explicit expiry timestamp — access tokens
        # are documented as valid "for the day" (until ~early morning IST).
        # 24h is a practical approximation, not a value Kite hands back;
        # the token could be rejected earlier by Kite itself, in which case
        # a later API call surfaces an auth error and the connection is
        # marked "expired" (see service.py).
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        return LoginResult(
            access_token=data["access_token"], expires_at=expires_at, broker_user_id=data.get("user_id")
        )

    def _headers(self, credentials: BrokerCredentials) -> dict:
        if not credentials.api_key or not credentials.access_token:
            raise BrokerConnectError("Broker connection is missing an access token — reconnect required.")
        return {
            "Authorization": f"token {credentials.api_key}:{credentials.access_token}",
            "X-Kite-Version": KITE_VERSION,
        }

    async def get_holdings(self, credentials: BrokerCredentials) -> list[BrokerHolding]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{KITE_API_BASE}/portfolio/holdings", headers=self._headers(credentials))
        body = response.json()
        if response.status_code != 200 or body.get("status") != "success":
            raise BrokerConnectError(f"Kite holdings fetch failed: {body.get('message', response.text)}")

        return [
            BrokerHolding(
                symbol=row["tradingsymbol"],
                quantity=float(row["quantity"]),
                avg_price=float(row["average_price"]),
                last_price=float(row["last_price"]) if row.get("last_price") is not None else None,
            )
            for row in body["data"]
        ]

    async def place_order(
        self, credentials: BrokerCredentials, *, symbol: str, side: str, quantity: float
    ) -> BrokerOrderResult:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{KITE_API_BASE}/orders/regular",
                headers=self._headers(credentials),
                data={
                    "tradingsymbol": symbol,
                    "exchange": "NSE",
                    "transaction_type": side.upper(),  # "BUY" | "SELL"
                    "order_type": "MARKET",
                    "quantity": int(quantity),
                    "product": "CNC",  # delivery, not intraday — see docs/ARCHITECTURE.md Phase 5 scope
                    "validity": "DAY",
                },
            )
        body = response.json()
        if response.status_code not in (200, 201) or body.get("status") != "success":
            return BrokerOrderResult(
                broker_order_id="",
                status="rejected",
                fill_price=None,
                message=body.get("message", response.text),
            )

        # Kite order placement is asynchronous — a successful response here
        # only means the order was ACCEPTED, not filled. Real fill price
        # requires a follow-up status check (GET /orders/{order_id}) or the
        # Kite postback/WebSocket order-update stream, neither of which is
        # wired up this phase — status is honestly reported as "pending",
        # never a fabricated fill price.
        return BrokerOrderResult(
            broker_order_id=body["data"]["order_id"], status="pending", fill_price=None
        )
