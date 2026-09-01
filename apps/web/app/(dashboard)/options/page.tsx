"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { AparixCard } from "@/components/aparix/AparixCard";
import { DemoDataBadge } from "@/components/aparix/AparixBadge";
import { AparixMetric } from "@/components/aparix/AparixMetric";
import { AparixTable } from "@/components/aparix/AparixTable";
import { api, type OptionContract } from "@/lib/api";

function formatInr(value: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(
    value
  );
}

// Same reasoning as tightDomain() in app/(dashboard)/risk/page.tsx: a
// 0-anchored Y-axis squashes an IV series that only moves within a ~15-40%
// band into an unreadable sliver.
function tightDomain(values: number[]): [number, number] {
  if (values.length === 0) return [0, 1];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = (max - min) * 0.15 || 1;
  return [Math.max(0, min - padding), max + padding];
}

export default function OptionsPage() {
  const securities = useQuery({ queryKey: ["securities"], queryFn: api.market.securities });
  // Explicit user picks; when null, derived defaults below (not an effect —
  // no need to synchronize external state, this is plain rendering logic)
  // fall back to the first loaded symbol/expiry.
  const [symbolChoice, setSymbolChoice] = useState<string | null>(null);
  const [expiryChoice, setExpiryChoice] = useState<string | null>(null);

  const defaultSymbol = useMemo(() => {
    const list = securities.data ?? [];
    return (list.find((s) => !s.is_index) ?? list[0])?.symbol ?? null;
  }, [securities.data]);
  const symbol = symbolChoice ?? defaultSymbol;

  const expiries = useQuery({
    queryKey: ["options-expiries", symbol],
    queryFn: () => api.options.expiries(symbol!),
    enabled: Boolean(symbol),
  });
  const defaultExpiry = expiries.data?.expiries[0] ?? null;
  const expiry = expiryChoice ?? defaultExpiry;

  const chain = useQuery({
    queryKey: ["options-chain", symbol, expiry],
    queryFn: () => api.options.chain(symbol!, expiry!),
    enabled: Boolean(symbol && expiry),
  });

  const smileData = useMemo(() => {
    if (!chain.data) return [];
    // IV is the same for a call and a put at the same strike (both are
    // priced off the one assumed IV for that strike — see
    // domains/options/service.py) — one point per strike is enough.
    const byStrike = new Map<number, number>();
    for (const c of chain.data.contracts) byStrike.set(c.strike, c.iv_pct);
    return Array.from(byStrike.entries())
      .map(([strike, iv_pct]) => ({ strike, iv_pct }))
      .sort((a, b) => a.strike - b.strike);
  }, [chain.data]);

  const ivDomain = useMemo(() => tightDomain(smileData.map((d) => d.iv_pct)), [smileData]);

  const sortedContracts = useMemo(() => {
    if (!chain.data) return [];
    return [...chain.data.contracts].sort((a, b) => a.strike - b.strike || a.option_type.localeCompare(b.option_type));
  }, [chain.data]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Options</h1>
        <DemoDataBadge />
      </div>
      <p className="text-xs text-muted-foreground">
        Read-only chain analysis: synthetic strikes, an assumed (not market-derived) implied volatility, and
        Black-Scholes Greeks. There&apos;s no options paper trading or position tracking yet — this is analysis only.
      </p>

      <AparixCard title="Chain">
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Symbol</label>
            <select
              value={symbol ?? ""}
              onChange={(e) => {
                setSymbolChoice(e.target.value);
                setExpiryChoice(null);
              }}
              className="rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
            >
              {(securities.data ?? []).map((s) => (
                <option key={s.id} value={s.symbol}>
                  {s.symbol} — {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Expiry</label>
            <select
              value={expiry ?? ""}
              onChange={(e) => setExpiryChoice(e.target.value)}
              className="rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
            >
              {(expiries.data?.expiries ?? []).map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          </div>
        </div>

        {chain.data && (
          <div className="mb-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <AparixMetric label="Spot" value={formatInr(chain.data.spot)} />
            <AparixMetric label="Days to expiry" value={String(chain.data.days_to_expiry)} />
            <AparixMetric label="Risk-free rate" value={`${chain.data.risk_free_rate_annual_pct}%`} />
            <AparixMetric label="Contracts" value={String(chain.data.contracts.length)} />
          </div>
        )}

        {chain.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {chain.isError && <p className="text-sm text-negative">Couldn&apos;t load that chain.</p>}

      </AparixCard>

      {smileData.length > 1 && (
        <AparixCard title="Volatility smile (assumed IV vs. strike)">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={smileData} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="strike" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} width={70} domain={ivDomain} unit="%" />
              <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} labelFormatter={(s) => `Strike ${s}`} />
              <Line type="monotone" dataKey="iv_pct" stroke="var(--accent)" dot={{ r: 2 }} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
          <p className="mt-1 text-xs text-muted-foreground">
            A 2D IV-vs-strike view, not a full strike × expiry × IV surface — see docs/ARCHITECTURE.md Phase 6
            trade-offs.
          </p>
        </AparixCard>
      )}

      <AparixCard title="Contracts">
        <AparixTable<OptionContract>
          columns={[
            { header: "Strike", align: "right", render: (c) => c.strike.toFixed(2) },
            {
              header: "Type",
              render: (c) => (
                <span className={c.option_type === "call" ? "text-positive" : "text-negative"}>
                  {c.option_type.toUpperCase()}
                </span>
              ),
            },
            { header: "Premium", align: "right", render: (c) => formatInr(c.premium) },
            { header: "IV", align: "right", render: (c) => `${c.iv_pct.toFixed(1)}%` },
            { header: "Delta", align: "right", render: (c) => c.delta.toFixed(4) },
            { header: "Gamma", align: "right", render: (c) => c.gamma.toFixed(6) },
            { header: "Theta/day", align: "right", render: (c) => c.theta.toFixed(4) },
            { header: "Vega", align: "right", render: (c) => c.vega.toFixed(4) },
            { header: "Rho", align: "right", render: (c) => c.rho.toFixed(4) },
          ]}
          rows={sortedContracts}
          keyFor={(c) => `${c.strike}-${c.option_type}`}
          emptyMessage="Select a symbol and expiry to see a chain."
        />
      </AparixCard>
    </div>
  );
}
