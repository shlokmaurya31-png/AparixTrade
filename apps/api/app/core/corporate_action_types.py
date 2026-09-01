"""Corporate action type constants — same plain-string-constants pattern as
core/roles.py (a fixed, small set, not a dynamically extensible enum).
"""

from typing import Final


class ActionType:
    DIVIDEND: Final = "dividend"
    SPLIT: Final = "split"
    BONUS: Final = "bonus"
    RIGHTS: Final = "rights"
    BUYBACK: Final = "buyback"
    MERGER: Final = "merger"
    DEMERGER: Final = "demerger"
    SYMBOL_CHANGE: Final = "symbol_change"
    ISIN_CHANGE: Final = "isin_change"
    DELISTING: Final = "delisting"


ALL_ACTION_TYPES: Final[tuple[str, ...]] = (
    ActionType.DIVIDEND,
    ActionType.SPLIT,
    ActionType.BONUS,
    ActionType.RIGHTS,
    ActionType.BUYBACK,
    ActionType.MERGER,
    ActionType.DEMERGER,
    ActionType.SYMBOL_CHANGE,
    ActionType.ISIN_CHANGE,
    ActionType.DELISTING,
)

# Types with a share-adjustment ratio (used by adjust_price_series()) —
# dividends/buybacks affect cash, not the share count, so they're excluded.
RATIO_ACTION_TYPES: Final[tuple[str, ...]] = (ActionType.SPLIT, ActionType.BONUS, ActionType.RIGHTS)

# Types never seeded against the LIVE tradable universe (would break
# existing paper trading/portfolio flows) — see docs/ARCHITECTURE.md §9.
# DELISTING and MERGER are seeded for real, but only against the 2
# dedicated historical-only securities (Tier 1 survivorship-bias work,
# domains/market_data/historical_seed_data.py) that were never tradable in
# the first place. DEMERGER/SYMBOL_CHANGE/ISIN_CHANGE remain supported as
# schema/logic, tested via synthetic fixtures only — no seeded example of
# either exists yet.
DISRUPTIVE_ACTION_TYPES: Final[tuple[str, ...]] = (
    ActionType.MERGER,
    ActionType.DEMERGER,
    ActionType.SYMBOL_CHANGE,
    ActionType.ISIN_CHANGE,
    ActionType.DELISTING,
)
