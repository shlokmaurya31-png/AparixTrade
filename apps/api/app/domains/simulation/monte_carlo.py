"""Monte Carlo engine — Phase 2.

Two methods, both operating on the portfolio's own historical daily-return
series (see docs/ARCHITECTURE.md Phase 2 trade-offs for why: a full
multi-asset correlated/factor-based simulator is deferred). Every result
states which method produced it and its assumptions — never presented as a
prediction, per the product's core safety principle (spec §15/§44).
"""

import math
import random
from dataclasses import dataclass

MAX_SAMPLE_PATHS = 100


@dataclass
class SimulationSummary:
    method: str
    num_paths: int
    horizon_days: int
    current_value: float
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float
    probability_of_loss_pct: float
    sample_paths: list[list[float]]
    assumptions: str


def _percentile(sorted_values: list[float], p: float) -> float:
    n = len(sorted_values)
    index = min(n - 1, max(0, int(round(p * (n - 1)))))
    return sorted_values[index]


def _summarize(
    *, method: str, terminals: list[float], paths: list[list[float]], current_value: float, horizon_days: int, assumptions: str
) -> SimulationSummary:
    sorted_terminals = sorted(terminals)
    n = len(terminals)
    probability_of_loss = sum(1 for t in terminals if t < current_value) / n if n else 0.0

    return SimulationSummary(
        method=method,
        num_paths=n,
        horizon_days=horizon_days,
        current_value=round(current_value, 2),
        p5=round(_percentile(sorted_terminals, 0.05), 2),
        p25=round(_percentile(sorted_terminals, 0.25), 2),
        p50=round(_percentile(sorted_terminals, 0.50), 2),
        p75=round(_percentile(sorted_terminals, 0.75), 2),
        p95=round(_percentile(sorted_terminals, 0.95), 2),
        probability_of_loss_pct=round(probability_of_loss * 100, 2),
        sample_paths=[[round(v, 2) for v in path] for path in paths[:MAX_SAMPLE_PATHS]],
        assumptions=assumptions,
    )


def simulate_gbm(
    *, current_value: float, daily_returns: list[float], horizon_days: int, num_paths: int, seed: int | None = None
) -> SimulationSummary:
    """Geometric Brownian Motion, drift/vol estimated from the portfolio's
    own historical daily returns (sample mean/std) — a parametric,
    normal-shock model, not a real forecast."""
    rng = random.Random(seed)
    n = len(daily_returns)
    mean = sum(daily_returns) / n
    variance = sum((r - mean) ** 2 for r in daily_returns) / (n - 1) if n > 1 else 0.0
    daily_vol = math.sqrt(variance)

    terminals: list[float] = []
    paths: list[list[float]] = []
    for _ in range(num_paths):
        value = current_value
        path = [value]
        for _ in range(horizon_days):
            shock = rng.gauss(0.0, 1.0)
            value *= math.exp((mean - 0.5 * daily_vol**2) + daily_vol * shock)
            path.append(value)
        terminals.append(value)
        paths.append(path)

    assumptions = (
        f"Geometric Brownian Motion using the portfolio's own historical daily mean return "
        f"({mean * 100:.3f}%/day) and volatility ({daily_vol * 100:.3f}%/day), normally-distributed shocks. "
        f"Not a forecast — a statistical projection under these assumptions."
    )
    return _summarize(
        method="gbm", terminals=terminals, paths=paths, current_value=current_value, horizon_days=horizon_days, assumptions=assumptions
    )


def simulate_bootstrap(
    *, current_value: float, daily_returns: list[float], horizon_days: int, num_paths: int, seed: int | None = None
) -> SimulationSummary:
    """Historical bootstrap: resamples actual observed daily returns (with
    replacement) rather than assuming a distribution — captures the real
    shape of past moves (fat tails etc.) at the cost of assuming the future
    resembles the sampled history."""
    rng = random.Random(seed)
    terminals: list[float] = []
    paths: list[list[float]] = []
    for _ in range(num_paths):
        value = current_value
        path = [value]
        for _ in range(horizon_days):
            r = rng.choice(daily_returns)
            value *= 1 + r
            path.append(value)
        terminals.append(value)
        paths.append(path)

    assumptions = (
        f"Historical bootstrap — resamples {len(daily_returns)} of the portfolio's own observed daily "
        f"returns with replacement. Assumes the future resembles this sampled history; captures the "
        f"actual shape of past moves rather than assuming a normal distribution."
    )
    return _summarize(
        method="bootstrap", terminals=terminals, paths=paths, current_value=current_value, horizon_days=horizon_days, assumptions=assumptions
    )
