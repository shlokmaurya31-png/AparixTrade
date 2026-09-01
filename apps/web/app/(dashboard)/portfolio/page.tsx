"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { AparixCard } from "@/components/aparix/AparixCard";
import { DemoDataBadge } from "@/components/aparix/AparixBadge";
import { AparixTable } from "@/components/aparix/AparixTable";
import { api, ApiError, type Holding } from "@/lib/api";
import { usePrimaryPortfolio } from "@/lib/use-portfolio";

const PIE_COLORS = ["#5b8ff9", "#3ecf7e", "#e0a542", "#f2555a", "#9b7bf0", "#4fd1c5", "#f0a3d0", "#8b93a1"];

function formatInr(value: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
    value
  );
}

export default function PortfolioPage() {
  const { portfolio, holdings } = usePrimaryPortfolio();
  const queryClient = useQueryClient();

  const securities = useQuery({ queryKey: ["securities"], queryFn: api.market.securities });
  const tradableSecurities = (securities.data ?? []).filter((s) => !s.is_index);

  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgPrice, setAvgPrice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onAddHolding(e: React.FormEvent) {
    e.preventDefault();
    if (!portfolio) return;
    setError(null);
    setSubmitting(true);
    try {
      await api.portfolios.addHolding(portfolio.id, {
        symbol,
        quantity: Number(quantity),
        avg_price: Number(avgPrice),
      });
      setSymbol("");
      setQuantity("");
      setAvgPrice("");
      // Prefix match invalidates analytics/holdings/risk in one call — see
      // the comment in lib/use-portfolio.ts on why they share a key prefix.
      await queryClient.invalidateQueries({ queryKey: ["portfolio", portfolio.id] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't add that holding.");
    } finally {
      setSubmitting(false);
    }
  }

  const rows = holdings.data ?? [];
  const pieData = rows.map((h) => ({ name: h.symbol, value: h.market_value }));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">{portfolio?.name ?? "Portfolio"}</h1>
        <DemoDataBadge />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <AparixCard title="Holdings" className="lg:col-span-2">
          <AparixTable<Holding>
            columns={[
              { header: "Symbol", render: (h) => <span className="font-medium">{h.symbol}</span> },
              { header: "Sector", render: (h) => <span className="text-muted-foreground">{h.sector}</span> },
              { header: "Qty", align: "right", render: (h) => h.quantity },
              { header: "Avg price", align: "right", render: (h) => formatInr(h.avg_price) },
              { header: "Last price", align: "right", render: (h) => formatInr(h.last_price) },
              { header: "Market value", align: "right", render: (h) => formatInr(h.market_value) },
              {
                header: "Unrealized P&L",
                align: "right",
                render: (h) => (
                  <span className={h.unrealized_pnl >= 0 ? "text-positive" : "text-negative"}>
                    {formatInr(h.unrealized_pnl)} ({h.unrealized_pnl_pct.toFixed(1)}%)
                  </span>
                ),
              },
            ]}
            rows={rows}
            keyFor={(h) => h.id}
            emptyMessage="No holdings yet — add one on the right."
          />
        </AparixCard>

        <AparixCard title="Allocation">
          {pieData.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing to show yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => formatInr(Number(value))} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </AparixCard>
      </div>

      <AparixCard title="Add holding (manual entry — broker sync is Phase 5)">
        <form onSubmit={onAddHolding} className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Symbol</label>
            <select
              required
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
            >
              <option value="" disabled>
                Select…
              </option>
              {tradableSecurities.map((s) => (
                <option key={s.id} value={s.symbol}>
                  {s.symbol} — {s.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Quantity</label>
            <input
              required
              type="number"
              min="0.0001"
              step="any"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-28 rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Avg. price (INR)</label>
            <input
              required
              type="number"
              min="0.01"
              step="any"
              value={avgPrice}
              onChange={(e) => setAvgPrice(e.target.value)}
              className="w-32 rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="rounded bg-accent px-4 py-1.5 text-sm font-medium text-accent-foreground disabled:opacity-50"
          >
            {submitting ? "Adding…" : "Add holding"}
          </button>
        </form>
        {error && <p className="mt-2 text-xs text-negative">{error}</p>}
      </AparixCard>
    </div>
  );
}
