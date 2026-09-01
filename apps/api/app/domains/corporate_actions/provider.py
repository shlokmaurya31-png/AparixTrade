"""CorporateActionsProvider abstraction (Tier 1 Session 3) — the pattern
proven by every other data domain in this codebase (market_data, macro,
fundamentals): abstract interface + Mock implementation, env-driven
selection.

Seeds plausible dividends broadly, and a stock split/bonus/rights for a
deterministic subset of securities — but never a merger/demerger/
symbol_change/delisting against the live tradable universe (see
core/corporate_action_types.py::DISRUPTIVE_ACTION_TYPES and
docs/ARCHITECTURE.md §9 for why).
"""

import random
from abc import ABC, abstractmethod
from datetime import date, timedelta

from app.core.corporate_action_types import ActionType

DIVIDEND_ANNOUNCEMENT_TO_EX_DAYS = (10, 20)
DIVIDEND_EX_TO_EFFECTIVE_DAYS = (1, 3)  # dividends are effective ~immediately once ex


def _offset(base: date, days: int) -> date:
    return base + timedelta(days=days)


def generate_actions(symbol: str, start_price: float, today: date) -> list[dict]:
    """Deterministic seeded RNG (same approach as every other mock
    generator in this codebase) — same symbol + start_price always
    produces the same actions."""
    rng = random.Random(f"aparix-corporate-actions-{symbol}")
    actions: list[dict] = []

    # Dividends: 1 per each of the last ~2 fiscal years, broadly across the
    # universe — real Indian large-caps typically pay at least an annual
    # dividend.
    for years_ago in (2, 1):
        announce = today - timedelta(days=365 * years_ago + rng.randint(-20, 20))
        ex = _offset(announce, rng.randint(*DIVIDEND_ANNOUNCEMENT_TO_EX_DAYS))
        effective = _offset(ex, rng.randint(*DIVIDEND_EX_TO_EFFECTIVE_DAYS))
        if ex > today:
            continue
        amount = round(start_price * rng.uniform(0.005, 0.02), 2)  # a modest yield, not a guess at a real payout
        actions.append(
            {
                "action_type": ActionType.DIVIDEND,
                "ratio": None,
                "amount": amount,
                "new_security_id": None,
                "announcement_date": announce,
                "record_date": _offset(ex, 1),
                "ex_date": ex,
                "effective_date": effective,
                "source": "mock",
            }
        )

    # A minority of securities also get exactly one non-cash action —
    # split/bonus/rights, mutually exclusive, chosen deterministically by
    # symbol. High-priced names lean toward a split (matches how real
    # high-priced Indian large-caps eventually split), everyone else has a
    # smaller chance of a bonus or rights issue.
    roll = rng.random()
    non_cash_action = None
    if start_price > 8000 and roll < 0.6:
        non_cash_action = (ActionType.SPLIT, rng.choice([2.0, 3.0]))
    elif roll < 0.15:
        non_cash_action = (ActionType.BONUS, rng.choice([1.5, 2.0]))  # "1:2" / "1:1"
    elif roll < 0.22:
        non_cash_action = (ActionType.RIGHTS, round(rng.uniform(1.1, 1.3), 2))

    if non_cash_action is not None:
        action_type, ratio = non_cash_action
        announce = today - timedelta(days=rng.randint(120, 300))
        ex = _offset(announce, rng.randint(15, 30))
        effective = ex
        if ex <= today:
            actions.append(
                {
                    "action_type": action_type,
                    "ratio": ratio,
                    "amount": None,
                    "new_security_id": None,
                    "announcement_date": announce,
                    "record_date": _offset(ex, 1),
                    "ex_date": ex,
                    "effective_date": effective,
                    "source": "mock",
                }
            )

    return actions


class CorporateActionsProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, symbol: str, start_price: float, today: date) -> list[dict]:
        raise NotImplementedError


class MockCorporateActionsProvider(CorporateActionsProvider):
    name = "mock"

    def generate(self, symbol: str, start_price: float, today: date) -> list[dict]:
        return generate_actions(symbol, start_price, today)


def get_corporate_actions_provider() -> CorporateActionsProvider:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.corporate_actions_provider == "mock":
        return MockCorporateActionsProvider()
    raise ValueError(f"Unknown CORPORATE_ACTIONS_PROVIDER: {settings.corporate_actions_provider!r}")
