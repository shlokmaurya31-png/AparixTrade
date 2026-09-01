"""Stress testing — Phase 2, synthetic/custom shocks only.

No historical crisis scenario library (2008 GFC, COVID, etc.) — this system
has no real historical crisis data, and fabricating those numbers would
violate the product's anti-faking principle (spec §70). See
docs/ARCHITECTURE.md Phase 2 trade-offs. Historical scenarios remain
"Coming soon" until real historical data ingestion exists (Phase 3+).

A shock target is either a benchmark ("NIFTY50"), a sector name, a single
holding's symbol, or (Tier 1 — knowledge-graph propagation) a real location/
commodity name resolved by domains/knowledge_graph/service.py. Benchmark
shocks propagate through each holding's beta; sector/symbol shocks apply
directly to the matching holdings; a location/commodity shock applies a
disclosed, decayed pass-through to indirectly-exposed holdings via
`graph_exposure`. Everything else gets zero — still a deliberate
simplification (no full cross-sector contagion model), just a less narrow
one than before.
"""

from dataclasses import dataclass


@dataclass
class HoldingRow:
    symbol: str
    sector: str
    market_value: float


BENCHMARK_TARGETS = {"NIFTY50", "BENCHMARK"}


def apply_shock(
    rows: list[HoldingRow],
    *,
    target: str,
    shock_pct: float,
    beta_by_symbol: dict[str, float],
    graph_exposure: dict[str, float] | None = None,
) -> dict:
    # graph_exposure — {symbol: pass_through_multiplier} — is resolved
    # by an async, DB-aware caller (domains/knowledge_graph/service.py)
    # before this pure, synchronous function is ever called, keeping
    # apply_shock() itself hand-fixture-testable exactly as it already was.
    graph_exposure = graph_exposure or {}
    total_value = sum(r.market_value for r in rows)
    per_holding_impact = []
    total_impact = 0.0
    target_upper = target.upper()

    for r in rows:
        if r.symbol.upper() == target_upper:
            applied_pct = shock_pct
            basis = "direct"
        elif r.sector.upper() == target_upper:
            applied_pct = shock_pct
            basis = "direct"
        elif target_upper in BENCHMARK_TARGETS:
            beta = beta_by_symbol.get(r.symbol, 1.0)
            applied_pct = shock_pct * beta
            basis = f"beta-adjusted (beta={beta:.2f})"
        elif r.symbol in graph_exposure:
            multiplier = graph_exposure[r.symbol]
            applied_pct = shock_pct * multiplier
            basis = f"indirect via knowledge graph ({multiplier:.0%} pass-through)"
        else:
            applied_pct = 0.0
            basis = "unaffected"

        impact = r.market_value * (applied_pct / 100)
        total_impact += impact
        per_holding_impact.append(
            {"symbol": r.symbol, "sector": r.sector, "shock_applied_pct": round(applied_pct, 2), "impact": round(impact, 2), "basis": basis}
        )

    return {
        "target": target,
        "shock_pct": shock_pct,
        "portfolio_value_before": round(total_value, 2),
        "estimated_impact": round(total_impact, 2),
        "estimated_impact_pct": round(total_impact / total_value * 100, 3) if total_value else 0.0,
        "portfolio_value_after": round(total_value + total_impact, 2),
        "per_holding_impact": per_holding_impact,
        "assumptions": (
            "Direct hits apply the shock 1:1 to a matching holding or sector; a benchmark shock is "
            "scaled per holding by its historical beta vs NIFTY 50; a real location/commodity target "
            "applies a disclosed, decayed pass-through (see the knowledge graph) to holdings with a "
            "real, documented exposure to it — everything else is unaffected. No full cross-sector "
            "contagion, liquidity, or second-order macro effects are modeled."
        ),
        "is_mock": True,
    }
