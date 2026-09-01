"""BrokerAdapter abstraction — mirrors domains/ai/provider.py's
ModelProvider pattern: one small interface, a zero-external-deps default
(MockBrokerAdapter), and a real implementation (ZerodhaKiteAdapter,
zerodha_adapter.py) selected by BROKER_PROVIDER. See docs/ARCHITECTURE.md §7
for the AI provider precedent this follows.

Adapters never touch the DB or decrypt/encrypt anything themselves — the
service layer (service.py) resolves a BrokerCredentials from the stored,
encrypted BrokerConnection row and passes it in. This keeps credential
handling in exactly one place.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class BrokerCredentials:
    api_key: str | None = None
    api_secret: str | None = None
    access_token: str | None = None


@dataclass
class LoginResult:
    access_token: str
    expires_at: datetime | None
    broker_user_id: str | None = None


@dataclass
class BrokerHolding:
    symbol: str
    quantity: float
    avg_price: float
    last_price: float | None = None


@dataclass
class BrokerOrderResult:
    broker_order_id: str
    status: str  # "filled" | "rejected" | "pending"
    fill_price: float | None
    message: str | None = None


class BrokerConnectError(Exception):
    pass


class BrokerAdapter(ABC):
    name: str

    @abstractmethod
    def get_login_url(self, *, api_key: str | None) -> str:
        """Where the user authorizes this app. Adapters that don't need an
        external redirect (MockBrokerAdapter) return a same-app marker the
        router never actually navigates to."""
        raise NotImplementedError

    @abstractmethod
    async def complete_login(
        self, *, api_key: str | None, api_secret: str | None, request_token: str | None
    ) -> LoginResult:
        raise NotImplementedError

    @abstractmethod
    async def get_holdings(self, credentials: BrokerCredentials) -> list[BrokerHolding]:
        raise NotImplementedError

    @abstractmethod
    async def place_order(
        self, credentials: BrokerCredentials, *, symbol: str, side: str, quantity: float
    ) -> BrokerOrderResult:
        raise NotImplementedError


# A small, fixed seeded position set — deterministic on purpose (not
# randomized quantities/avg_prices) so tests and the UI show the same
# "connected account" every time. Distinct symbols from paper trading's
# usual demo flow so the two accounts are visibly different in the UI.
_MOCK_HOLDINGS = [
    ("INFY", 15, 1450.0),
    ("HDFCBANK", 25, 1580.0),
    ("ITC", 100, 410.0),
]


class MockBrokerAdapter(BrokerAdapter):
    """Simulates a connected brokerage account with zero external deps —
    the checked-in default (BROKER_PROVIDER=mock), same role
    MockModelProvider plays for the AI layer. There is no real account
    behind this: holdings are a fixed seeded set, clearly is_mock in every
    response, never presented as a real Zerodha connection."""

    name = "mock"

    def get_login_url(self, *, api_key: str | None) -> str:
        return "mock://connect"

    async def complete_login(
        self, *, api_key: str | None, api_secret: str | None, request_token: str | None
    ) -> LoginResult:
        return LoginResult(
            access_token=f"mock-token-{random.randint(100000, 999999)}",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            broker_user_id="MOCK001",
        )

    async def get_holdings(self, credentials: BrokerCredentials) -> list[BrokerHolding]:
        return [BrokerHolding(symbol=s, quantity=q, avg_price=p) for s, q, p in _MOCK_HOLDINGS]

    async def place_order(
        self, credentials: BrokerCredentials, *, symbol: str, side: str, quantity: float
    ) -> BrokerOrderResult:
        # Order placement through the mock broker is deliberately not
        # wired to actually change get_holdings()'s fixed set — the mock
        # adapter's job is to demo the "connected account" experience
        # (login, holdings sync), not to duplicate paper_trading's
        # execution engine. See docs/ARCHITECTURE.md Phase 5 trade-offs.
        return BrokerOrderResult(
            broker_order_id=f"MOCK-{random.randint(100000, 999999)}",
            status="rejected",
            fill_price=None,
            message="Mock broker does not execute orders — connect a real broker to place live orders.",
        )
