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
| Events (`domains/events`) | `MOCK` (mostly) | Hand-authored seed events (e.g. the Jamnagar flood scenario). One or more may now genuinely originate from `domains/news` when `NEWS_PROVIDER=rss` — see that row below; `Event.is_mock` distinguishes them per-row |
| News ingestion — Google News RSS (evaluated, **not used**) | `UNKNOWN` → **rejected** | Its own feed copyright notice states the feed "is made available solely for the purpose of rendering Google News results within a personal feed reader for personal, non-commercial use. Any other use... is expressly prohibited." — checked directly by fetching and reading it (`docs/APARIX_TIER1_COMPLETION_REPORT.md` Session 4), not assumed. This app is not a personal feed reader, so this source was not integrated |
| News ingestion — RBI official press releases (`domains/news`, default real source) | `REQUIRES_ATTRIBUTION` | RBI's feed explicitly states "Copyright Reserve Bank of India. All Rights Reserved." — **not** public domain despite being a government source. Press releases are issued by a financial regulator specifically for public dissemination and news reporting, which is meaningfully different from a commercial publisher's paywalled journalism or Google News' explicit personal-use-only restriction — but this app only stores/displays headline + a short (HTML-stripped) summary + a link back to RBI's own page, never reproduces full release text, and attributes every article to its real publisher in the UI. This is a defensible "fair dealing"-style aggregation posture, not a confirmed legal clearance — flag for real legal review before any production/commercial use, per the framework below. `NEWS_PROVIDER` defaults to `mock`, so this source is never contacted unless explicitly enabled |
| Financial statements / fundamentals (`domains/fundamentals`) | `MOCK` | Synthetic income statement/balance sheet/cash flow generated per security, anchored to that security's mock price so ratios stay plausible — not a real company's actual filings |
| Corporate actions (`domains/corporate_actions`) | `MOCK` | Synthetic dividends/splits/bonuses/rights per security — not a real company's actual corporate action history |
| Options chains/Greeks (`domains/options`) | `MOCK` (computed) | Synthetic strikes/IV, closed-form-priced from mock spot data — not sourced data at all, so "licensing" doesn't apply the same way, but still not real |
| Zerodha Kite Connect (`domains/broker/zerodha_adapter.py`) | `COMMERCIAL_LICENSE_REQUIRED` | Requires a paid Kite Connect developer subscription (https://developers.kite.trade) and each user's own OAuth consent — this app never redistributes Kite data to anyone but the account holder it belongs to, and the adapter has never actually been exercised against a live account in this build (see `docs/ARCHITECTURE.md` §9) |
| Ollama / `llama3.1` (`domains/ai/ollama_provider.py`) | N/A — local model weights, not a data feed | Governed by the model's own license (Meta Llama license for `llama3.1`), not a data-licensing question; out of scope for this document |

**Everything currently shipped is `MOCK` by default, requires the end
user's own paid/authorized credentials (Zerodha), or — the one exception,
opt-in only (`NEWS_PROVIDER=rss`) — aggregates a government regulator's
own public press releases in headline+summary+link form, attributed to
its real publisher. Nothing in this codebase redistributes a real third
party's paywalled/licensed content to users who haven't separately
obtained it themselves.**

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
