"""NewsProvider abstraction — same interface+Mock pattern as every other
domain in this codebase, but with a genuine second implementation this
time: RSSNewsProvider makes a real HTTP request to a real, live RSS feed
and parses real XML. Not a simulation of ingestion — actual ingestion,
gated off by default (NEWS_PROVIDER=mock) so a fresh clone doesn't
silently start hitting an external server. See docs/DATA_LICENSING.md for
why the default real source is RBI's official press-release feed rather
than a commercial publisher's (whose terms typically restrict reuse) or
Google News' RSS (whose own terms explicitly forbid anything but personal,
non-commercial feed-reading — checked directly, not assumed).
"""

import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

DEFAULT_RSS_URL = "https://www.rbi.org.in/pressreleases_rss.xml"
DEFAULT_RSS_PUBLISHER = "Reserve Bank of India"
DEFAULT_RSS_SOURCE = "rbi_press_releases"

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(raw: str) -> str:
    """RSS <description> fields commonly embed HTML (RBI's feed wraps
    tables around numeric details) — a plain-text summary is more useful
    to store and display than raw markup. A regex tag-strip, not a full
    HTML parser: good enough for a summary snippet, not attempting to
    preserve structure."""
    text = _TAG_RE.sub(" ", raw)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _parse_rss_items(xml_text: str) -> list[dict]:
    """Pure parsing logic, split out from the network fetch specifically so
    it can be fixture-tested against a captured XML sample without hitting
    the network (tests/test_news_provider.py)."""
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = _strip_html(item.findtext("description") or "")
        pub_date_raw = item.findtext("pubDate")
        try:
            published_at = parsedate_to_datetime(pub_date_raw) if pub_date_raw else None
            if published_at and published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            published_at = None
        if not title or not link:
            continue
        items.append(
            {
                "title": title[:500],
                "summary": (description or title)[:2000],
                "url": link[:1000],
                "published_at": published_at or datetime.now(timezone.utc),
            }
        )
    return items


class NewsProvider(ABC):
    name: str

    @abstractmethod
    async def fetch(self) -> list[dict]:
        """Returns a list of {"title","summary","url","published_at"} dicts."""
        raise NotImplementedError


class MockNewsProvider(NewsProvider):
    """Zero external dependency, the checked-in default. A fixed,
    deterministic illustrative set — not fetched from anywhere, clearly
    labeled is_mock=True by the caller (domains/news/service.py)."""

    name = "mock"

    async def fetch(self) -> list[dict]:
        # Deliberately distinct wording from domains/events/seed_data.py's
        # hand-authored SEED_EVENTS (a real bug once: a mock article here
        # duplicated an existing seed event's exact headline, silently
        # creating a second, inconsistent Event row for the same story —
        # caught by tests/test_events.py's seeded-count assertion).
        now = datetime.now(timezone.utc)
        return [
            {
                "title": "RBI expands digital rupee pilot to more retail partners",
                "summary": "The central bank digital currency pilot programme adds new participating banks "
                "and merchants.",
                "url": "https://example.invalid/mock-news/rbi-digital-rupee-pilot",
                "published_at": now,
            },
            {
                "title": "RBI conducts routine liquidity operation",
                "summary": "A scheduled variable rate reverse repo auction under the liquidity adjustment facility.",
                "url": "https://example.invalid/mock-news/rbi-vrrr",
                "published_at": now,
            },
        ]


class RSSNewsProvider(NewsProvider):
    """Real ingestion: fetches and parses an actual live RSS feed. Default
    source is RBI's official press-release feed (see module docstring for
    why). `url`/`publisher`/`source` are configurable via Settings so a
    deployment can point at a different, appropriately-licensed feed."""

    name = "rss"

    def __init__(self, url: str, publisher: str, source: str) -> None:
        self.url = url
        self.publisher = publisher
        self.source = source

    async def fetch(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(self.url)
            response.raise_for_status()
        return _parse_rss_items(response.text)


def get_news_provider() -> NewsProvider:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.news_provider == "mock":
        return MockNewsProvider()
    if settings.news_provider == "rss":
        return RSSNewsProvider(
            url=settings.news_rss_url, publisher=settings.news_rss_publisher, source=settings.news_rss_source
        )
    raise ValueError(f"Unknown NEWS_PROVIDER: {settings.news_provider!r}")
