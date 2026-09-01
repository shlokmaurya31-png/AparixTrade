"""DEMO DATA — dedicated historical-only securities, seeded specifically to
give the point-in-time security universe query (list_securities_as_of())
something real to prove survivorship-bias correctness against: a security
that existed, then stopped existing, so a query dated before that date must
still show it and a query dated after must not.

Deliberately fictitious company names, not real Indian companies — Session
3 (corporate actions) already established every other seeded security is a
real company's identity with synthetic price data; a delisting/merger is a
specific, checkable real-world fact, and asserting a real company was
delisted/merged on a synthetic date this app invented would be a factual
claim this codebase has no basis for. These two are clearly demo shells
instead — see docs/ARCHITECTURE.md §9.
"""

from datetime import date

# symbol, name, sector, start_price, listed_date, delisted_date, delisting reason
DELISTED_SECURITY = (
    "ORIONINFRA",
    "Orion Infratech Ltd (delisted)",
    "Industrials",
    340.0,
    date(2015, 4, 1),
    date(2023, 11, 15),
)

# symbol, name, sector, start_price, listed_date, delisted_date, merged-into symbol
MERGED_SECURITY = (
    "VELOCFIN",
    "Velocity Fincorp Ltd (merged into HDFCBANK)",
    "Financials",
    610.0,
    date(2012, 1, 1),
    date(2021, 6, 30),
    "HDFCBANK",
)
