"""DEMO DATA — seeded mock market events, generated at server startup with
timestamps spread over the last ~14 days (see service.seed_if_needed).

No real news API key exists, so this follows the exact same pattern as
MockMarketDataProvider — illustrative, deterministic, clearly is_mock=True,
never presented as a live feed.

Content-safety note (see docs/ARCHITECTURE.md Phase 3 trade-offs): negative
events stay impersonal — sector-wide, macro, or weather-on-operations. The
one event naming a real company (RELIANCE) mirrors the flooding-disrupts-
refining example from the product spec itself: a weather/operational event,
not an accusation of wrongdoing. No fabricated misconduct, fraud, or scandal
content is attached to any real, named company.

Fields: (headline, summary, event_type, severity, direction, primary_target,
secondary_tags, region, days_ago)
"""

SEED_EVENTS: list[tuple[str, str, str, str, str, str, list[str], str, int]] = [
    (
        "Severe flooding disrupts industrial operations near Jamnagar",
        "Heavy monsoon rainfall has disrupted road and rail access around Jamnagar, Gujarat, "
        "temporarily affecting logistics for refining and petrochemical operations in the region.",
        "natural_disaster",
        "high",
        "negative",
        "RELIANCE",
        ["Energy", "Gujarat", "Refining", "Petrochemicals"],
        "Gujarat, India",
        1,
    ),
    (
        "RBI holds repo rate steady in latest policy review",
        "The Reserve Bank of India's Monetary Policy Committee kept the repo rate unchanged, "
        "citing balanced inflation and growth conditions.",
        "regulatory",
        "low",
        "neutral",
        "NIFTY50",
        ["Financials", "Monetary Policy"],
        "India",
        2,
    ),
    (
        "IT services firms trim revenue guidance on softer US demand",
        "Several large IT services providers flagged softer discretionary spending from US "
        "enterprise clients, trimming full-year revenue growth guidance.",
        "earnings",
        "medium",
        "negative",
        "Information Technology",
        ["IT Services", "US demand"],
        "India / US",
        3,
    ),
    (
        "Government expands PLI incentives for auto component manufacturing",
        "An expanded production-linked incentive scheme aims to boost domestic manufacturing of "
        "auto components and EV parts.",
        "regulatory",
        "medium",
        "positive",
        "Automobiles",
        ["PLI", "EV", "Manufacturing"],
        "India",
        4,
    ),
    (
        "Brent crude rises sharply on Middle East supply concerns",
        "Oil prices jumped after reports of disrupted shipping routes in the Middle East raised "
        "concerns about crude supply.",
        "commodity_shock",
        "high",
        "negative",
        "Energy",
        ["Crude oil", "Middle East", "Supply chain"],
        "Middle East",
        5,
    ),
    (
        "Telecom regulator proposes revised spectrum pricing framework",
        "The telecom regulator has floated a consultation paper on revised spectrum pricing that "
        "could affect operators' capital expenditure plans.",
        "regulatory",
        "medium",
        "negative",
        "Telecommunications",
        ["Spectrum", "Regulation"],
        "India",
        6,
    ),
    (
        "Private banks report strong quarterly earnings on loan growth",
        "Several large private-sector banks posted better-than-expected quarterly profits, driven "
        "by healthy loan growth and stable asset quality.",
        "earnings",
        "medium",
        "positive",
        "Financials",
        ["Earnings", "Loan growth"],
        "India",
        7,
    ),
    (
        "India's GDP growth outlook revised upward for the fiscal year",
        "Economists raised full-year GDP growth estimates, citing resilient domestic consumption "
        "and investment activity.",
        "macro",
        "low",
        "positive",
        "NIFTY50",
        ["GDP", "Growth"],
        "India",
        8,
    ),
    (
        "Above-normal monsoon forecast lifts rural consumption outlook",
        "Meteorological forecasts point to above-normal monsoon rainfall, supporting expectations "
        "for stronger rural demand this year.",
        "macro",
        "low",
        "positive",
        "Consumer Staples",
        ["Monsoon", "Rural demand"],
        "India",
        10,
    ),
    (
        "Easing global chip shortage improves supply chain visibility",
        "Semiconductor supply constraints have eased further, benefiting electronics and auto "
        "manufacturers reliant on chip imports.",
        "supply_chain",
        "low",
        "positive",
        "Automobiles",
        ["Semiconductors", "Supply chain"],
        "Global",
        12,
    ),
    # The next two demonstrate real knowledge-graph event propagation
    # (Tier 1 — see domains/knowledge_graph/) — primary_target is a real
    # location/commodity name, not a symbol/sector, so the impact
    # calculation resolves it through the graph to every seeded security
    # with a real, documented exposure, at a disclosed decayed pass-
    # through, rather than requiring one hand-picked direct target.
    (
        "Cyclone warning issued for Gujarat coast, ports and plants on alert",
        "The India Meteorological Department has issued a cyclone warning for the Gujarat coastline; "
        "port operators and industrial facilities in the region are activating contingency plans.",
        "natural_disaster",
        "medium",
        "negative",
        "Gujarat",
        ["Gujarat", "Ports", "Weather"],
        "Gujarat, India",
        9,
    ),
    (
        "Coal supply disruptions weigh on thermal power generation capacity",
        "Logistics constraints at major coal mines have slowed deliveries to thermal power plants, "
        "raising near-term concerns about generation capacity utilization.",
        "supply_chain",
        "medium",
        "negative",
        "coal",
        ["Coal", "Power generation", "Supply chain"],
        "India",
        11,
    ),
]
