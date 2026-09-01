# Data Licensing

What data this codebase actually uses, and the classification framework
for whatever gets added next. Written per the Tier 1 infrastructure
request's explicit instruction not to assume public web data can be
redistributed, and not to use an `UNKNOWN`-licensed source in production
without review.

## Classification

| Class | Meaning |
|---|---|
| `MOCK` | Synthetic/seeded, not sourced from any real vendor or publisher — nothing to license because nothing is real |
| `PUBLIC` | Genuinely public data with no redistribution restriction (e.g. a government open-data portal with an explicit open license) |
| `REQUIRES_ATTRIBUTION` | Usable, but the source must be credited per its terms |
| `NON_COMMERCIAL` | Usable for research/personal use, not for a commercial product without a separate agreement |
| `COMMERCIAL_LICENSE_REQUIRED` | Needs a paid subscription/contract before any use (e.g. a market-data vendor, a broker API's data terms) |
| `UNKNOWN` | Not reviewed — **must not be used in production** until classified |

## Every data source in this codebase today

| Source | Class | Notes |
|---|---|---|
| Market data (`domains/market_data`) — securities, candles, live ticks | `MOCK` | Deterministic seeded random walk (`MockMarketDataProvider`). Illustrative starting prices only, never claimed as real historical NSE/BSE data |
| Macro indicators (`domains/macro`) | `MOCK` | 7 seeded illustrative values (repo rate, CPI, GDP, etc.), not RBI/MOSPI-fetched |
| Events (`domains/events`) | `MOCK` | Hand-authored seed events (e.g. the Jamnagar flood scenario), not derived from any real news source |
| Financial statements / fundamentals (`domains/fundamentals`) | `MOCK` | Synthetic income statement/balance sheet/cash flow generated per security, anchored to that security's mock price so ratios stay plausible — not a real company's actual filings |
| Corporate actions (`domains/corporate_actions`) | `MOCK` | Synthetic dividends/splits/bonuses/rights per security — not a real company's actual corporate action history |
| Options chains/Greeks (`domains/options`) | `MOCK` (computed) | Synthetic strikes/IV, closed-form-priced from mock spot data — not sourced data at all, so "licensing" doesn't apply the same way, but still not real |
| Zerodha Kite Connect (`domains/broker/zerodha_adapter.py`) | `COMMERCIAL_LICENSE_REQUIRED` | Requires a paid Kite Connect developer subscription (https://developers.kite.trade) and each user's own OAuth consent — this app never redistributes Kite data to anyone but the account holder it belongs to, and the adapter has never actually been exercised against a live account in this build (see `docs/ARCHITECTURE.md` §9) |
| Ollama / `llama3.1` (`domains/ai/ollama_provider.py`) | N/A — local model weights, not a data feed | Governed by the model's own license (Meta Llama license for `llama3.1`), not a data-licensing question; out of scope for this document |

**Everything currently shipped is either `MOCK` or requires the end
user's own paid/authorized credentials (Zerodha). Nothing in this codebase
today redistributes a real third party's licensed data to users who
haven't separately obtained it themselves.**

## Before adding any real data source

1. Classify it using the table above *before* writing the integration, not
   after.
2. If `COMMERCIAL_LICENSE_REQUIRED`: confirm the specific license actually
   covers the intended use (e.g. "personal API access" often does **not**
   cover "redistributing to all of this app's users" — that's a
   fundamentally different, usually more expensive, agreement).
3. If `UNKNOWN`: do not integrate it until it's been reviewed and moved to
   a real class. Scraping a website's HTML because it's technically
   reachable is not the same as having a license to redistribute its
   content — check the source's own terms of service, not just robots.txt.
4. Document the classification in this file, in the same PR as the
   integration — this file must never fall behind what's actually
   integrated.
5. Never mark something "public domain" or "fair use" as an
   engineering-convenience assumption — that's a legal determination, not
   a technical one, and it belongs with the reviewer(s) responsible for
   it, not something this document should assert on its own.

## Regulatory note

None of the above is a substitute for the compliance boundary already
documented in `docs/ARCHITECTURE.md` §8 (no execution/advisory claims
without professional legal review) and the Tier 1 request's own §45 —
data licensing and regulatory compliance are related but separate
concerns, and clearing one does not clear the other.
