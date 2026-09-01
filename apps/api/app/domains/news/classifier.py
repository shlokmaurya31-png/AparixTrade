"""News → Event classification — pure, deterministic, keyword-based. Not
machine learning, and not pretending to be: a small rule table matched
against article title+summary text, fixture-tested against real headline
shapes (tests/test_news_classifier.py). See docs/ARCHITECTURE.md §9 for
why a transparent heuristic was chosen over an unverifiable ML claim.

Most ingested articles (routine operational announcements — a daily VRRR
auction notice, a circular) correctly classify to `None`: not every press
release is a market-moving event, and forcing one would be exactly the
kind of fabricated significance this platform's "never fake it" discipline
prohibits. `direction="neutral"` (DIRECTION_SIGN maps it to 0 in
domains/events/impact.py) is the honest default when the direction can't
actually be determined from the text — a zero estimated impact, not a
guessed sign.
"""

from dataclasses import dataclass

_HIKE_WORDS = ("hike", "hikes", "raised", "raises", "raise", "increase", "increased", "tighten", "tightened")
_CUT_WORDS = ("cut", "cuts", "reduced", "reduce", "lower", "lowered", "ease", "eased", "trim", "trimmed")


@dataclass
class Classification:
    event_type: str
    severity: str  # "low" | "medium" | "high"
    direction: str  # "positive" | "negative" | "neutral"
    primary_target: str


# (keywords, event_type, severity, target, hike_direction, cut_direction, neutral_direction)
# hike/cut/neutral direction let the same keyword family mean different
# things depending on which way the action actually goes (a rate hike and
# a rate cut are not the same event even though both mention "repo rate").
_RULES: list[tuple[tuple[str, ...], str, str, str, str, str, str]] = [
    (
        ("repo rate", "monetary policy committee", "mpc meeting", "policy rate"),
        "regulatory",
        "high",
        "NIFTY50",
        "negative",  # a hike is generally read as tightening -> bearish for equities
        "positive",  # a cut is generally read as easing -> bullish for equities
        "neutral",  # held steady / no change
    ),
    (
        ("cash reserve ratio", "crr ", "statutory liquidity ratio", " slr "),
        "regulatory",
        "medium",
        "Financials",
        "negative",
        "positive",
        "neutral",
    ),
    (
        ("npa", "provisioning norms", "banking regulation", "licence cancelled", "license cancelled", "bank licence"),
        "regulatory",
        "medium",
        "Financials",
        "negative",
        "negative",  # tightening language in this category reads negative either way
        "negative",
    ),
    (
        ("inflation", "cpi projection", "wpi"),
        "macro",
        "medium",
        "NIFTY50",
        "negative",  # rising inflation read as a headwind
        "positive",
        "neutral",
    ),
    (
        ("digital rupee", "cbdc", "central bank digital currency"),
        "regulatory",
        "low",
        "Financials",
        "neutral",
        "neutral",
        "neutral",
    ),
]


def _infer_direction(text: str, hike_dir: str, cut_dir: str, neutral_dir: str) -> str:
    has_hike = any(w in text for w in _HIKE_WORDS)
    has_cut = any(w in text for w in _CUT_WORDS)
    if has_hike and not has_cut:
        return hike_dir
    if has_cut and not has_hike:
        return cut_dir
    return neutral_dir  # both, or neither, mentioned -> can't honestly tell which way


def classify_article(title: str, summary: str) -> Classification | None:
    text = f" {title.lower()} {summary.lower()} "
    for keywords, event_type, severity, target, hike_dir, cut_dir, neutral_dir in _RULES:
        if any(kw in text for kw in keywords):
            direction = _infer_direction(text, hike_dir, cut_dir, neutral_dir)
            return Classification(event_type=event_type, severity=severity, direction=direction, primary_target=target)
    return None
