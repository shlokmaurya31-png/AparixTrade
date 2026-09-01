"""A small, hand-curated financial knowledge graph — Tier 1 §? (financial
knowledge graph + event propagation beyond one target).

Every fact below is a well-known, publicly documented headquarters/major-
facility location or commodity dependency for a real, large, publicly
listed Indian company — general public knowledge (the kind found in any
company profile or annual report), not a precise, date-stamped claim that
could be flatly wrong the way a specific delisting date could (contrast
with the deliberately *fictitious* companies in
domains/market_data/historical_seed_data.py, chosen for exactly that
reason). Where a fact felt uncertain rather than well-established, it was
left out rather than guessed — this is a genuinely small, conservative
graph, not a comprehensive one, and isn't trying to be.

Deliberately scoped to ONE hop per relationship type, not a multi-node
chain ("location -> industry -> company -> supply-chain -> commodity ->
macro" as the fullest version of this idea could go): a location links
directly to the securities based there, a commodity links directly to the
securities that consume it. No company-to-company supply-chain edges are
seeded at all — verifying a *specific* real supplier relationship between
two of these companies is a materially less certain, less publicly clean
fact than "where is this company headquartered," and this session's
"never fabricate" discipline means leaving that edge type out entirely
rather than guessing at a plausible-sounding one.

Also deliberately consumption-side only for commodities: a producer's
opposite-signed exposure (ONGC benefiting from, not being hurt by, a
crude oil price spike) is not modeled — every commodity link here is a
`depends_on` (consumes) relationship, and the event-propagation math
(domains/knowledge_graph/service.py) applies the event's own shock
direction uniformly to every consumption-side holding, not a per-security
sign flip.
"""

LOCATIONS: list[tuple[str, str]] = [
    ("Gujarat", "state"),
    ("Maharashtra", "state"),
    ("Karnataka", "state"),
    ("Haryana", "state"),
    ("Delhi", "union_territory"),
    ("Uttarakhand", "state"),
]

COMMODITIES: list[tuple[str, str]] = [
    ("crude_oil", "Crude Oil"),
    ("coal", "Coal"),
    ("steel", "Steel"),
    ("palm_oil", "Palm Oil"),
]

# symbol, location_name, relationship_type
SECURITY_LOCATIONS: list[tuple[str, str, str]] = [
    # Reliance's Jamnagar refining/petrochemical complex, Gujarat — the
    # world's largest single-site refinery, real and widely documented
    # (and already this app's own long-standing example scenario).
    ("RELIANCE", "Gujarat", "major_facility"),
    ("RELIANCE", "Maharashtra", "headquarters"),  # Mumbai HQ
    # Tata Motors' Sanand plant, Gujarat (passenger vehicles).
    ("TATAMOTORS", "Gujarat", "major_facility"),
    ("TATAMOTORS", "Maharashtra", "headquarters"),  # Mumbai HQ
    ("ADANIENT", "Gujarat", "headquarters"),  # Ahmedabad
    ("TCS", "Maharashtra", "headquarters"),
    ("HDFCBANK", "Maharashtra", "headquarters"),
    ("ICICIBANK", "Maharashtra", "headquarters"),
    ("AXISBANK", "Maharashtra", "headquarters"),
    ("KOTAKBANK", "Maharashtra", "headquarters"),
    ("SBIN", "Maharashtra", "headquarters"),
    ("LT", "Maharashtra", "headquarters"),
    ("HINDUNILVR", "Maharashtra", "headquarters"),
    ("ASIANPAINT", "Maharashtra", "headquarters"),
    ("SUNPHARMA", "Maharashtra", "headquarters"),
    ("INFY", "Karnataka", "headquarters"),  # Bengaluru
    ("WIPRO", "Karnataka", "headquarters"),  # Bengaluru
    ("MARUTI", "Haryana", "major_facility"),  # Gurugram/Manesar plants
    ("MARUTI", "Delhi", "headquarters"),
    ("BHARTIARTL", "Delhi", "headquarters"),
    ("NTPC", "Delhi", "headquarters"),
    ("ONGC", "Uttarakhand", "headquarters"),  # Dehradun
]

# symbol, commodity_code, relationship_type
SECURITY_COMMODITIES: list[tuple[str, str, str]] = [
    ("RELIANCE", "crude_oil", "depends_on"),  # refining feedstock
    ("ASIANPAINT", "crude_oil", "depends_on"),  # petrochemical-derived paints/coatings
    ("TATAMOTORS", "steel", "depends_on"),  # auto manufacturing
    ("MARUTI", "steel", "depends_on"),
    ("LT", "steel", "depends_on"),  # engineering/construction
    ("NTPC", "coal", "depends_on"),  # India's largest coal-based power generator
    ("ADANIENT", "coal", "depends_on"),  # coal trading/mining is a core, original Adani business
    ("HINDUNILVR", "palm_oil", "depends_on"),  # widely-documented FMCG palm-oil dependency
]
