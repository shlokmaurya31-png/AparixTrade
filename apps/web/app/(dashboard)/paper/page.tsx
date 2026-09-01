"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { AparixBadge, DemoDataBadge } from "@/components/aparix/AparixBadge";
import { AparixCard } from "@/components/aparix/AparixCard";
import { AparixMetric } from "@/components/aparix/AparixMetric";
import { AparixTable } from "@/components/aparix/AparixTable";
import { api, ApiError, type Holding, type PaperOrder, type TradePreview } from "@/lib/api";

function formatInr(value: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
    value
  );
}

export default function PaperTradingPage() {
  const queryClient = useQueryClient();

  const paperPortfolio = useQuery({ queryKey: ["paper-portfolio"], queryFn: api.paperTrading.portfolio });
  const holdings = useQuery({
    queryKey: ["paper-holdings", paperPortfolio.data?.id],
    queryFn: () => api.portfolios.holdings(paperPortfolio.data!.id),
    enabled: Boolean(paperPortfolio.data),
  });
  const orders = useQuery({ queryKey: ["paper-orders"], queryFn: api.paperTrading.orders });
  const securities = useQuery({ queryKey: ["securities"], queryFn: api.market.securities });
  const tradableSecurities = (securities.data ?? []).filter((s) => !s.is_index);

  const [symbol, setSymbol] = useState("");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState("");
  const [preview, setPreview] = useState<TradePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [placing, setPlacing] = useState(false);
  const [lastOrder, setLastOrder] = useState<PaperOrder | null>(null);

  const holdingsValue = (holdings.data ?? []).reduce((sum, h) => sum + h.market_value, 0);
  const cash = paperPortfolio.data?.cash_balance ?? 0;
  const totalValue = cash + holdingsValue;

  async function refreshAll() {
    await queryClient.invalidateQueries({ queryKey: ["paper-portfolio"] });
    await queryClient.invalidateQueries({ queryKey: ["paper-holdings"] });
    await queryClient.invalidateQueries({ queryKey: ["paper-orders"] });
  }

  async function runPreview(e: React.FormEvent) {
    e.preventDefault();
    if (!symbol || !quantity) return;
    setPreviewError(null);
    setPreviewLoading(true);
    setPreview(null);
    setLastOrder(null);
    try {
      setPreview(await api.paperTrading.preview({ symbol, side, quantity: Number(quantity) }));
    } catch (err) {
      setPreviewError(err instanceof ApiError ? err.message : "Couldn't preview that trade.");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function placeOrder() {
    if (!symbol || !quantity) return;
    setPlacing(true);
    try {
      const order = await api.paperTrading.placeOrder({ symbol, side, quantity: Number(quantity) });
      setLastOrder(order);
      setPreview(null);
      await refreshAll();
    } catch (err) {
      setPreviewError(err instanceof ApiError ? err.message : "Couldn't place that order.");
    } finally {
      setPlacing(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Paper Trading</h1>
        <DemoDataBadge />
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <AparixCard>
          <AparixMetric label="Total value" value={formatInr(totalValue)} size="lg" />
        </AparixCard>
        <AparixCard>
          <AparixMetric label="Cash" value={formatInr(cash)} />
        </AparixCard>
        <AparixCard>
          <AparixMetric label="Holdings value" value={formatInr(holdingsValue)} />
        </AparixCard>
        <AparixCard>
          <AparixMetric label="Open positions" value={String((holdings.data ?? []).length)} />
        </AparixCard>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <AparixCard title="Holdings">
          <AparixTable<Holding>
            columns={[
              { header: "Symbol", render: (h) => <span className="font-medium">{h.symbol}</span> },
              { header: "Qty", align: "right", render: (h) => h.quantity },
              { header: "Avg price", align: "right", render: (h) => formatInr(h.avg_price) },
              { header: "Market value", align: "right", render: (h) => formatInr(h.market_value) },
              {
                header: "P&L",
                align: "right",
                render: (h) => (
                  <span className={h.unrealized_pnl >= 0 ? "text-positive" : "text-negative"}>
                    {formatInr(h.unrealized_pnl)}
                  </span>
                ),
              },
            ]}
            rows={holdings.data ?? []}
            keyFor={(h) => h.id}
            emptyMessage="No paper positions yet — place an order below."
          />
        </AparixCard>

        <AparixCard title="Order ticket">
          <form onSubmit={runPreview} className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">Symbol</label>
              <select
                required
                value={symbol}
                onChange={(e) => {
                  setSymbol(e.target.value);
                  setPreview(null);
                }}
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
              <label className="mb-1 block text-xs text-muted-foreground">Side</label>
              <select
                value={side}
                onChange={(e) => {
                  setSide(e.target.value as "buy" | "sell");
                  setPreview(null);
                }}
                className="rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted-foreground">Quantity</label>
              <input
                required
                type="number"
                min="1"
                step="1"
                value={quantity}
                onChange={(e) => {
                  setQuantity(e.target.value);
                  setPreview(null);
                }}
                className="w-24 rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
              />
            </div>
            <button
              type="submit"
              disabled={previewLoading}
              className="rounded border border-border px-4 py-1.5 text-sm font-medium hover:bg-surface-hover disabled:opacity-50"
            >
              {previewLoading ? "Previewing…" : "Preview"}
            </button>
          </form>

          {previewError && <p className="mt-2 text-xs text-negative">{previewError}</p>}

          {preview && (
            <div className="mt-3 space-y-2 border-t border-border pt-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Est. fill price</span>
                <span className="font-mono-nums">
                  {formatInr(preview.estimated_fill_price)} (slippage {preview.estimated_slippage_pct.toFixed(3)}%)
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Brokerage</span>
                <span className="font-mono-nums">{formatInr(preview.estimated_brokerage)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Cash after</span>
                <span className="font-mono-nums">
                  {formatInr(preview.cash_before)} → {formatInr(preview.cash_after)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Concentration score</span>
                <span className="font-mono-nums">
                  {preview.concentration_score_before.toFixed(0)} → {preview.concentration_score_after.toFixed(0)}/100
                </span>
              </div>
              {!preview.affordable && (
                <p className="text-xs text-negative">
                  Not affordable — insufficient {side === "buy" ? "cash" : "holding"} for this order.
                </p>
              )}
              <button
                onClick={placeOrder}
                disabled={placing || !preview.affordable}
                className="mt-1 w-full rounded bg-accent py-1.5 text-sm font-medium text-accent-foreground disabled:opacity-50"
              >
                {placing ? "Placing…" : `${side === "buy" ? "Buy" : "Sell"} ${quantity} ${symbol}`}
              </button>
            </div>
          )}

          {lastOrder && (
            <div className="mt-3 border-t border-border pt-3 text-sm">
              {lastOrder.status === "filled" ? (
                <p className="text-positive">
                  Filled {lastOrder.quantity} {lastOrder.symbol} @ {formatInr(lastOrder.fill_price ?? 0)}.
                </p>
              ) : (
                <p className="text-negative">Rejected: {lastOrder.rejection_reason}</p>
              )}
              <Link
                href={`/ai?q=${encodeURIComponent(`How was my ${lastOrder.symbol} ${lastOrder.side} order?`)}`}
                className="mt-1 inline-block text-xs text-accent hover:underline"
              >
                Ask the AI coach about this trade →
              </Link>
            </div>
          )}
        </AparixCard>
      </div>

      <AparixCard title="Order history">
        <AparixTable<PaperOrder>
          columns={[
            { header: "Symbol", render: (o) => o.symbol },
            {
              header: "Side",
              render: (o) => <AparixBadge tone={o.side === "buy" ? "positive" : "negative"}>{o.side}</AparixBadge>,
            },
            { header: "Qty", align: "right", render: (o) => o.quantity },
            { header: "Fill price", align: "right", render: (o) => (o.fill_price != null ? formatInr(o.fill_price) : "—") },
            {
              header: "Status",
              render: (o) => (
                <AparixBadge tone={o.status === "filled" ? "positive" : "negative"}>{o.status}</AparixBadge>
              ),
            },
            { header: "When", render: (o) => new Date(o.created_at).toLocaleString() },
            {
              header: "",
              render: (o) => (
                <Link
                  href={`/ai?q=${encodeURIComponent(`How was my ${o.symbol} ${o.side} order?`)}`}
                  className="text-xs text-accent hover:underline"
                >
                  Ask coach
                </Link>
              ),
            },
          ]}
          rows={orders.data ?? []}
          keyFor={(o) => o.id}
          emptyMessage="No orders placed yet."
        />
      </AparixCard>
    </div>
  );
}
