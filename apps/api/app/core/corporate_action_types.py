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

# Types this session deliberately doesn't seed against the live tradable
# universe (would break existing paper trading/portfolio flows) — see
# docs/ARCHITECTURE.md §9. Supported as schema/logic, tested via synthetic
# fixtures only.
DISRUPTIVE_ACTION_TYPES: Final[tuple[str, ...]] = (
    ActionType.MERGER,
    ActionType.DEMERGER,
    ActionType.SYMBOL_CHANGE,
    ActionType.ISIN_CHANGE,
    ActionType.DELISTING,
)
