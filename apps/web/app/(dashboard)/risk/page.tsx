"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { AparixBadge, DemoDataBadge } from "@/components/aparix/AparixBadge";
import { AparixCard } from "@/components/aparix/AparixCard";
import { AparixHeatmap } from "@/components/aparix/AparixHeatmap";
import { AparixMetric } from "@/components/aparix/AparixMetric";
import { api, ApiError, type BacktestResult, type MonteCarloResult, type StressTestResult } from "@/lib/api";
import { usePrimaryPortfolio } from "@/lib/use-portfolio";

function formatInr(value: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
    value
  );
}

function percentileSeries(paths: number[][]) {
  if (paths.length === 0) return [];
  const horizon = paths[0].length;
  const series = [];
  for (let day = 0; day < horizon; day++) {
    const values = paths.map((p) => p[day]).sort((a, b) => a - b);
    const pct = (p: number) => values[Math.min(values.length - 1, Math.max(0, Math.round(p * (values.length - 1))))];
    series.push({ day, p5: pct(0.05), p50: pct(0.5), p95: pct(0.95) });
  }
  return series;
}

/** A 0-anchored Y-axis (Recharts' default) squashes a portfolio-value line
 * into an unreadable sliver near the top, since these values move a few
 * percent around ~1 lakh INR, not from 0. Zoom to the actual data range with
 * a margin instead — this is a value/price series, not a bar chart where a
 * 0 baseline matters. */
function tightDomain(values: number[]): [number, number] {
  if (values.length === 0) return [0, 1];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = (max - min) * 0.1 || max * 0.02 || 1;
  return [Math.floor(min - padding), Math.ceil(max + padding)];
}

export default function RiskPage() {
  const { portfolio, risk, holdings } = usePrimaryPortfolio();
  const queryClient = useQueryClient();

  // ── Stress test ──
  const [shockTarget, setShockTarget] = useState("NIFTY50");
  const [shockPct, setShockPct] = useState(-15);
  const [stressResult, setStressResult] = useState<StressTestResult | null>(null);
  const [stressError, setStressError] = useState<string | null>(null);
  const [stressLoading, setStressLoading] = useState(false);

  // ── Monte Carlo ──
  const [mcMethod, setMcMethod] = useState<"bootstrap" | "gbm">("bootstrap");
  const [mcHorizon, setMcHorizon] = useState(30);
  const [mcResult, setMcResult] = useState<MonteCarloResult | null>(null);
  const [mcError, setMcError] = useState<string | null>(null);
  const [mcLoading, setMcLoading] = useState(false);

  // ── Backtest ──
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const backtestHistory = useQuery({
    queryKey: ["backtest-history", portfolio?.id],
    queryFn: () => api.simulation.backtestHistory(portfolio!.id),
    enabled: Boolean(portfolio),
  });

  const shockTargets = useMemo(() => {
    const rows = holdings.data ?? [];
    const sectors = Array.from(new Set(rows.map((h) => h.sector)));
    const symbols = rows.map((h) => h.symbol);
    return ["NIFTY50", ...sectors, ...symbols];
  }, [holdings.data]);

  const mcChartData = useMemo(() => (mcResult ? percentileSeries(mcResult.sample_paths) : []), [mcResult]);
  const mcDomain = useMemo(() => tightDomain(mcChartData.flatMap((d) => [d.p5, d.p95])), [mcChartData]);
  const backtestDomain = useMemo(
    () => tightDomain((backtestResult?.equity_curve ?? []).map((p) => p.value)),
    [backtestResult]
  );

  async function runStressTest(e: React.FormEvent) {
    e.preventDefault();
    if (!portfolio) return;
    setStressLoading(true);
    setStressError(null);
    try {
      setStressResult(await api.simulation.stressTest(portfolio.id, { target: shockTarget, shock_pct: shockPct }));
    } catch (err) {
      setStressError(err instanceof ApiError ? err.message : "Couldn't run that stress test.");
    } finally {
      setStressLoading(false);
    }
  }

  async function runMonteCarlo(e: React.FormEvent) {
    e.preventDefault();
    if (!portfolio) return;
    setMcLoading(true);
    setMcError(null);
    try {
      setMcResult(await api.simulation.monteCarlo(portfolio.id, { method: mcMethod, horizon_days: mcHorizon, num_paths: 1000 }));
    } catch (err) {
      setMcError(err instanceof ApiError ? err.message : "Couldn't run that simulation.");
    } finally {
      setMcLoading(false);
    }
  }

  async function runBacktest() {
    if (!portfolio) return;
    setBacktestLoading(true);
    setBacktestError(null);
    try {
      const result = await api.simulation.runBacktest(portfolio.id, { initial_value: 100_000 });
      setBacktestResult(result);
      await queryClient.invalidateQueries({ queryKey: ["backtest-history", portfolio.id] });
    } catch (err) {
      setBacktestError(err instanceof ApiError ? err.message : "Couldn't run that backtest.");
    } finally {
      setBacktestLoading(false);
    }
  }

  if (!portfolio) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  const r = risk.data;
  const insufficientHistory = r != null && r.sample_size < 20;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Risk & Simulation</h1>
        <DemoDataBadge />
      </div>

      <AparixCard title="Risk metrics (historical simulation)">
        {insufficientHistory && (
          <p className="text-sm text-muted-foreground">
            Only {r?.sample_size} days of overlapping price history across your holdings — need at least 20 for a
            reliable estimate. Add holdings with more history or check back after a few more simulated trading days.
          </p>
        )}
        {!insufficientHistory && r && (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              <AparixMetric label="VaR 95% (1d)" value={r.var_95_pct != null ? `${r.var_95_pct.toFixed(2)}%` : "—"} />
              <AparixMetric label="VaR 99% (1d)" value={r.var_99_pct != null ? `${r.var_99_pct.toFixed(2)}%` : "—"} />
              <AparixMetric label="CVaR 95%" value={r.cvar_95_pct != null ? `${r.cvar_95_pct.toFixed(2)}%` : "—"} />
              <AparixMetric label="CVaR 99%" value={r.cvar_99_pct != null ? `${r.cvar_99_pct.toFixed(2)}%` : "—"} />
              <AparixMetric label="Sharpe" value={r.sharpe_ratio?.toFixed(2) ?? "—"} />
              <AparixMetric label="Sortino" value={r.sortino_ratio?.toFixed(2) ?? "—"} />
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Historical simulation over {r.sample_size} trading days of simulated price history. Sharpe/Sortino
              assume a {r.risk_free_rate_annual_pct}% annual risk-free rate. Max drawdown (weighted, historical):{" "}
              {r.max_drawdown_pct != null ? `${r.max_drawdown_pct.toFixed(2)}%` : "—"}.
            </p>
          </>
        )}
      </AparixCard>

      {r?.correlation_matrix && r.correlation_matrix.symbols.length >= 2 && (
        <AparixCard title="Holding correlation matrix">
          <AparixHeatmap symbols={r.correlation_matrix.symbols} matrix={r.correlation_matrix.matrix} />
        </AparixCard>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AparixCard title="Stress test (custom shock)">
          <form onSubmit={runStressTest} className="space-y-3">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">Target</label>
                <select
                  value={shockTarget}
                  onChange={(e) => setShockTarget(e.target.value)}
                  className="rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
                >
                  {shockTargets.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-muted-foreground">Shock %</label>
                <input
                  type="number"
                  step="1"
                  min="-90"
                  max="90"
                  value={shockPct}
                  onChange={(e) => setShockPct(Number(e.target.value))}
                  className="w-24 rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
                />
              </div>
              <button
                type="submit"
                disabled={stressLoading}
                className="rounded bg-accent px-4 py-1.5 text-sm font-medium text-accent-foreground disabled:opacity-50"
              >
                {stressLoading ? "Running…" : "Run"}
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {["1997 Asian crisis", "2008 GFC", "2020 COVID crash", "2022 rate shock"].map((label) => (
                <AparixBadge key={label} tone="neutral">
                  {label}
                  <span className="ml-1 opacity-70">Coming soon</span>
                </AparixBadge>
              ))}
            </div>
          </form>
          {stressError && <p className="mt-2 text-xs text-negative">{stressError}</p>}
          {stressResult && (
            <div className="mt-3 border-t border-border pt-3 text-sm">
              <p>
                {shockTarget} {shockPct >= 0 ? "+" : ""}
                {shockPct}% → estimated impact{" "}
                <span className={stressResult.estimated_impact >= 0 ? "text-positive" : "text-negative"}>
                  {formatInr(stressResult.estimated_impact)} ({stressResult.estimated_impact_pct.toFixed(2)}%)
                </span>
                . Portfolio value {formatInr(stressResult.portfolio_value_before)} →{" "}
                {formatInr(stressResult.portfolio_value_after)}.
              </p>
              <p className="mt-2 text-xs text-muted-foreground">{stressResult.assumptions}</p>
            </div>
          )}
        </AparixCard>

        <AparixCard title="Monte Carlo simulation">
          <form onSubmit={runMonteCarlo} className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">Method</label>
              <select
                value={mcMethod}
                onChange={(e) => setMcMethod(e.target.value as "bootstrap" | "gbm")}
                className="rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
              >
                <option value="bootstrap">Historical bootstrap</option>
                <option value="gbm">Geometric Brownian Motion</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">Horizon (days)</label>
              <input
                type="number"
                min="1"
                max="365"
                value={mcHorizon}
                onChange={(e) => setMcHorizon(Number(e.target.value))}
                className="w-24 rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
              />
            </div>
            <button
              type="submit"
              disabled={mcLoading}
              className="rounded bg-accent px-4 py-1.5 text-sm font-medium text-accent-foreground disabled:opacity-50"
            >
              {mcLoading ? "Simulating…" : "Run 1,000 paths"}
            </button>
          </form>
          {mcError && <p className="mt-2 text-xs text-negative">{mcError}</p>}
          {mcResult && (
            <div className="mt-3 border-t border-border pt-3">
              <div className="grid grid-cols-3 gap-2 text-sm">
                <AparixMetric label="P5" value={formatInr(mcResult.p5)} />
                <AparixMetric label="P50" value={formatInr(mcResult.p50)} />
                <AparixMetric label="P95" value={formatInr(mcResult.p95)} />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Probability of loss: {mcResult.probability_of_loss_pct.toFixed(1)}%
              </p>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={mcChartData} margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} width={70} domain={mcDomain} />
                  <Tooltip formatter={(v) => formatInr(Number(v))} labelFormatter={(d) => `Day ${d}`} />
                  <Line type="monotone" dataKey="p95" stroke="var(--positive)" dot={false} strokeWidth={1} />
                  <Line type="monotone" dataKey="p50" stroke="var(--accent)" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="p5" stroke="var(--negative)" dot={false} strokeWidth={1} />
                </LineChart>
              </ResponsiveContainer>
              <p className="mt-1 text-xs text-muted-foreground">{mcResult.assumptions}</p>
            </div>
          )}
        </AparixCard>
      </div>

      <AparixCard title="Backtest — buy and hold current weights">
        <button
          onClick={runBacktest}
          disabled={backtestLoading}
          className="self-start rounded bg-accent px-4 py-1.5 text-sm font-medium text-accent-foreground disabled:opacity-50"
        >
          {backtestLoading ? "Running…" : "Run backtest"}
        </button>
        {backtestError && <p className="mt-2 text-xs text-negative">{backtestError}</p>}
        {backtestResult && backtestResult.cagr_pct !== null && (
          <div className="mt-3 border-t border-border pt-3">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <AparixMetric label="Total return" value={`${backtestResult.total_return_pct.toFixed(2)}%`} />
              <AparixMetric label="CAGR" value={`${backtestResult.cagr_pct.toFixed(2)}%`} />
              <AparixMetric label="Max drawdown" value={`${backtestResult.max_drawdown_pct?.toFixed(2) ?? "—"}%`} />
              <AparixMetric
                label="Sharpe / Sortino"
                value={`${backtestResult.sharpe_ratio?.toFixed(2) ?? "—"} / ${backtestResult.sortino_ratio?.toFixed(2) ?? "—"}`}
              />
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={backtestResult.equity_curve} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="trade_date" tick={{ fontSize: 10 }} minTickGap={40} />
                <YAxis tick={{ fontSize: 10 }} width={70} domain={backtestDomain} />
                <Tooltip formatter={(v) => formatInr(Number(v))} />
                <Line type="monotone" dataKey="value" stroke="var(--accent)" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
            <p className="mt-1 text-xs text-muted-foreground">{backtestResult.assumptions}</p>
          </div>
        )}

        {(backtestHistory.data?.length ?? 0) > 0 && (
          <div className="mt-4 border-t border-border pt-3">
            <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Past runs
            </h3>
            <div className="space-y-1 text-xs text-muted-foreground">
              {backtestHistory.data!.map((run) => (
                <div key={run.id} className="flex justify-between">
                  <span>{run.created_at ? new Date(run.created_at).toLocaleString() : "—"}</span>
                  <span className="font-mono-nums">
                    CAGR {run.cagr_pct?.toFixed(2) ?? "—"}% · Max DD {run.max_drawdown_pct?.toFixed(2) ?? "—"}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </AparixCard>
    </div>
  );
}
