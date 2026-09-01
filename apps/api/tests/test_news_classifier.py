from app.domains.news.classifier import classify_article

# Headline shapes modeled on real RBI press-release titles (see
# docs/APARIX_TIER1_AUDIT.md verification) — not fabricated wording.


def test_repo_rate_hike_is_high_severity_negative():
    c = classify_article(
        "RBI hikes repo rate by 25 basis points to control inflation",
        "The Monetary Policy Committee raised the repo rate.",
    )
    assert c is not None
    assert c.severity == "high"
    assert c.direction == "negative"
    assert c.primary_target == "NIFTY50"


def test_repo_rate_cut_is_high_severity_positive():
    c = classify_article("RBI cuts repo rate to boost growth", "MPC reduced the policy rate by 25 bps.")
    assert c is not None
    assert c.direction == "positive"


def test_repo_rate_held_steady_is_neutral():
    c = classify_article(
        "RBI keeps repo rate unchanged in latest policy review", "The MPC maintained status quo on rates."
    )
    assert c is not None
    assert c.direction == "neutral"


def test_routine_vrrr_auction_is_not_classified_as_an_event():
    # The most common real RBI RSS item shape — a routine daily liquidity
    # operation, not a market-moving event. Must NOT be forced into one.
    c = classify_article(
        "RBI to conduct Overnight Variable Rate Reverse Repo (VRRR) auction under LAF on September 02, 2026",
        "On a review of current and evolving liquidity conditions, it has been decided to conduct a VRRR auction.",
    )
    assert c is None


def test_unrelated_routine_press_release_is_not_classified():
    c = classify_article(
        "Ayurveda Day digital dialogue series launched", "A government outreach initiative on traditional medicine."
    )
    assert c is None


def test_crr_change_targets_financials():
    c = classify_article("RBI raises Cash Reserve Ratio by 50 bps", "Banks must now hold more reserves.")
    assert c is not None
    assert c.primary_target == "Financials"
    assert c.direction == "negative"


def test_bank_npa_regulation_is_negative_regardless_of_wording():
    c = classify_article("RBI tightens NPA provisioning norms for banks", "New rules increase provisioning burden.")
    assert c is not None
    assert c.direction == "negative"
    assert c.primary_target == "Financials"


def test_inflation_reading_up_is_negative():
    c = classify_article("CPI inflation projection raised for the fiscal year", "RBI revised its inflation outlook upward.")
    assert c is not None
    assert c.direction == "negative"


def test_classification_is_case_insensitive():
    c = classify_article("RBI HIKES REPO RATE", "THE MPC RAISED RATES.")
    assert c is not None
    assert c.direction == "negative"
