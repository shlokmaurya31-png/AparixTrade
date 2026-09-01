import datetime

from app.domains.news.provider import MockNewsProvider, _parse_rss_items, _strip_html

# A trimmed, real sample captured from RBI's actual press-release feed
# (https://www.rbi.org.in/pressreleases_rss.xml) during development — not
# fabricated XML shape. Network access itself is exercised manually, not
# in the automated suite (same discipline as Ollama-dependent code: tested
# via a captured fixture, never a live external call in pytest).
SAMPLE_RSS_XML = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
<channel>
<title>PRESS RELEASES FROM RBI</title>
<link>http://www.rbi.org.in</link>
<description>This is Feed from RBI for Press Releases.</description>
<copyright>Copyright Reserve Bank of India. All Rights Reserved.</copyright>
<item>
<title><![CDATA[RBI to conduct Overnight Variable Rate Reverse Repo (VRRR) auction under LAF on September 02, 2026]]></title>
<link>https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=99001</link>
<description><![CDATA[<table width="100%"><tr><td><p>On a review of current and evolving liquidity conditions, it has been decided to conduct a VRRR auction.</p></td></tr></table>]]></description>
<pubDate>Tue, 01 Sep 2026 14:00:00 GMT</pubDate>
</item>
<item>
<title><![CDATA[RBI hikes repo rate by 25 basis points]]></title>
<link>https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=99002</link>
<description><![CDATA[The Monetary Policy Committee raised the repo rate to control inflation.]]></description>
<pubDate>Mon, 31 Aug 2026 09:30:00 GMT</pubDate>
</item>
<item>
<title></title>
<link></link>
<description><![CDATA[An item with no title or link must be skipped, not crash the parser.]]></description>
<pubDate>Mon, 31 Aug 2026 09:00:00 GMT</pubDate>
</item>
</channel>
</rss>
"""


def test_strip_html_removes_tags_and_collapses_whitespace():
    assert _strip_html("<table><tr><td>Hello   world</td></tr></table>") == "Hello world"


def test_parse_rss_items_extracts_expected_fields():
    items = _parse_rss_items(SAMPLE_RSS_XML)
    assert len(items) == 2  # the title/link-less item is skipped
    first = items[0]
    assert first["title"].startswith("RBI to conduct Overnight Variable Rate Reverse Repo")
    assert first["url"] == "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=99001"
    assert "liquidity conditions" in first["summary"]
    assert "<" not in first["summary"]  # HTML stripped


def test_parse_rss_items_parses_rfc822_pub_date():
    items = _parse_rss_items(SAMPLE_RSS_XML)
    assert items[0]["published_at"] == datetime.datetime(2026, 9, 1, 14, 0, 0, tzinfo=datetime.timezone.utc)


def test_parse_rss_items_skips_entries_with_no_title_or_link():
    items = _parse_rss_items(SAMPLE_RSS_XML)
    titles = [i["title"] for i in items]
    assert all(t for t in titles)


def test_parse_rss_items_on_empty_feed_returns_empty_list():
    empty = """<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""
    assert _parse_rss_items(empty) == []


async def test_mock_provider_returns_a_fixed_illustrative_set():
    items = await MockNewsProvider().fetch()
    assert len(items) >= 1
    assert all({"title", "summary", "url", "published_at"} <= set(item.keys()) for item in items)
