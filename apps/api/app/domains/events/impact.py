"""Event → portfolio impact. Deliberately thin: all the actual shock-
propagation math already exists and is tested in
domains/simulation/stress_test.py::apply_shock() — an event's impact IS a
stress test, just with the target/magnitude derived from the event instead
of typed in by the user. Keeping exactly one impact-math implementation.
"""

from app.domains.simulation.stress_test import HoldingRow, apply_shock
from app.models.event import Event

SEVERITY_MAGNITUDE_PCT = {"low": 3.0, "medium": 7.0, "high": 15.0}
DIRECTION_SIGN = {"positive": 1, "negative": -1, "neutral": 0}


def event_shock_pct(event: Event) -> float:
    """A severity-based estimate, not a calibrated forecast — see
    docs/ARCHITECTURE.md Phase 3 trade-offs. No historical data exists to
    empirically derive these magnitudes."""
    return SEVERITY_MAGNITUDE_PCT[event.severity] * DIRECTION_SIGN[event.direction]


def compute_event_impact(
    event: Event,
    rows: list[HoldingRow],
    beta_by_symbol: dict[str, float],
    graph_exposure: dict[str, float] | None = None,
) -> dict:
    shock_pct = event_shock_pct(event)
    result = apply_shock(
        rows, target=event.primary_target, shock_pct=shock_pct, beta_by_symbol=beta_by_symbol, graph_exposure=graph_exposure
    )
    result["event_id"] = str(event.id)
    result["headline"] = event.headline
    result["severity"] = event.severity
    result["direction"] = event.direction
    return result
