import datetime as dt

import pytest
from httpx import AsyncClient

from app.domains.events.impact import compute_event_impact, event_shock_pct
from app.domains.simulation.stress_test import HoldingRow
from app.models.event import Event


def _make_event(**overrides) -> Event:
    defaults = dict(
        headline="Test event",
        summary="Test summary",
        event_type="regulatory",
        severity="medium",
        direction="negative",
        primary_target="Energy",
        secondary_tags=[],
        region="India",
        published_at=dt.datetime.now(dt.timezone.utc),
        is_mock=True,
    )
    defaults.update(overrides)
    return Event(**defaults)


def test_event_shock_pct_matches_severity_and_direction_table():
    assert event_shock_pct(_make_event(severity="low", direction="positive")) == pytest.approx(3.0)
    assert event_shock_pct(_make_event(severity="medium", direction="negative")) == pytest.approx(-7.0)
    assert event_shock_pct(_make_event(severity="high", direction="negative")) == pytest.approx(-15.0)
    assert event_shock_pct(_make_event(severity="low", direction="neutral")) == pytest.approx(0.0)


def test_compute_event_impact_reuses_apply_shock_direct_symbol():
    event = _make_event(severity="high", direction="negative", primary_target="RELIANCE")
    rows = [
        HoldingRow(symbol="RELIANCE", sector="Energy", market_value=10_000),
        HoldingRow(symbol="TCS", sector="Information Technology", market_value=10_000),
    ]

    result = compute_event_impact(event, rows, beta_by_symbol={})

    reliance = next(r for r in result["per_holding_impact"] if r["symbol"] == "RELIANCE")
    tcs = next(r for r in result["per_holding_impact"] if r["symbol"] == "TCS")
    assert reliance["impact"] == pytest.approx(-1500.0)  # 10000 * -15%
    assert tcs["impact"] == pytest.approx(0.0)
    assert result["headline"] == "Test event"
    assert result["severity"] == "high"


def test_compute_event_impact_market_wide_uses_beta():
    event = _make_event(severity="medium", direction="positive", primary_target="NIFTY50")
    rows = [HoldingRow(symbol="HDFCBANK", sector="Financials", market_value=20_000)]

    result = compute_event_impact(event, rows, beta_by_symbol={"HDFCBANK": 0.5})

    # +7% * beta 0.5 = +3.5% applied
    assert result["per_holding_impact"][0]["shock_applied_pct"] == pytest.approx(3.5)
    assert result["estimated_impact"] == pytest.approx(700.0)


def test_compute_event_impact_neutral_direction_has_no_effect():
    event = _make_event(severity="high", direction="neutral", primary_target="Financials")
    rows = [HoldingRow(symbol="HDFCBANK", sector="Financials", market_value=20_000)]

    result = compute_event_impact(event, rows, beta_by_symbol={})
    assert result["estimated_impact"] == pytest.approx(0.0)


# ── HTTP-level: full stack, seeded events, real portfolio ──────────────────


async def test_events_are_seeded_and_reachable(client: AsyncClient):
    response = await client.get("/api/v1/events")
    assert response.status_code == 200
    events = response.json()
    # 10 hand-seeded SEED_EVENTS + 1 real event created by news ingestion's
    # classifier from MockNewsProvider's "digital rupee pilot" mock article
    # (domains/news/service.py::ingest_once, seeded once at startup like
    # every other domain) — a genuine second source of events now, not a
    # duplicate or a magic number.
    assert len(events) == 11
    jamnagar = next(e for e in events if "Jamnagar" in e["headline"])
    assert jamnagar["primary_target"] == "RELIANCE"
    assert jamnagar["severity"] == "high"
    assert jamnagar["direction"] == "negative"


async def test_jamnagar_event_impact_hits_reliance_holding(client: AsyncClient, auth_headers: dict):
    portfolio = await client.post(
        "/api/v1/portfolios", json={"name": "Event Test", "kind": "long_term"}, headers=auth_headers
    )
    portfolio_id = portfolio.json()["id"]

    holding = await client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"symbol": "RELIANCE", "quantity": 10, "avg_price": 2500.0},
        headers=auth_headers,
    )
    market_value = holding.json()["market_value"]

    events = await client.get("/api/v1/events")
    jamnagar_id = next(e for e in events.json() if "Jamnagar" in e["headline"])["id"]

    impact = await client.get(
        f"/api/v1/events/{jamnagar_id}/impact",
        params={"portfolio_id": portfolio_id},
        headers=auth_headers,
    )
    assert impact.status_code == 200
    body = impact.json()
    assert body["target"] == "RELIANCE"
    assert body["shock_pct"] == pytest.approx(-15.0)
    assert body["estimated_impact"] == pytest.approx(market_value * -0.15, rel=1e-6)
