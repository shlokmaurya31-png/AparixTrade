"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { AparixBadge, DemoDataBadge } from "@/components/aparix/AparixBadge";
import { AparixCard } from "@/components/aparix/AparixCard";
import { AparixMetric } from "@/components/aparix/AparixMetric";
import { AparixTable } from "@/components/aparix/AparixTable";
import { api, ApiError, type BrokerHolding } from "@/lib/api";

function formatInr(value: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
    value
  );
}

export default function BrokerPage() {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["broker-status"], queryFn: api.broker.status });
  const portfolio = useQuery({
    queryKey: ["broker-portfolio"],
    queryFn: api.broker.portfolio,
    enabled: Boolean(status.data?.connected),
  });

  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<{ synced: number; skipped: string[] } | null>(null);

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["broker-status"] });
    await queryClient.invalidateQueries({ queryKey: ["broker-portfolio"] });
  }

  async function connect() {
    setBusy(true);
    setActionError(null);
    try {
      // Mock provider (the checked-in default) connects unconditionally —
      // no real login redirect needed. A real Zerodha connection would
      // instead send the user to api.broker.loginUrl() first and land back
      // here with a request_token from /broker/callback.
      await api.broker.connect();
      setLastSync(null);
      await refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Couldn't connect.");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    setActionError(null);
    try {
      await api.broker.disconnect();
      setLastSync(null);
      await refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Couldn't disconnect.");
    } finally {
      setBusy(false);
    }
  }

  async function sync() {
    setBusy(true);
    setActionError(null);
    try {
      const result = await api.broker.sync();
      setLastSync({ synced: result.synced_holdings, skipped: result.skipped_symbols });
      await refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Couldn't sync holdings.");
    } finally {
      setBusy(false);
    }
  }

  const isMock = portfolio.data?.is_mock ?? status.data?.broker === "mock";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Broker</h1>
        {status.data?.connected && <DemoDataBadge />}
      </div>

      <AparixCard title="Connection">
        {!status.data?.connected ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              No broker is connected. Connecting syncs your real holdings from a brokerage account into Aparix —
              this is read-only: holdings here always mirror the broker, never editable by hand.
            </p>
            <button
              onClick={connect}
              disabled={busy}
              className="rounded bg-accent px-4 py-1.5 text-sm font-medium text-accent-foreground disabled:opacity-50"
            >
              {busy ? "Connecting…" : "Connect broker (demo)"}
            </button>
            <p className="text-xs text-muted-foreground">
              This connects a <strong>simulated</strong> broker account with a fixed demo holdings set — no real
              Zerodha account is contacted. See{" "}
              <code className="rounded bg-surface-hover px-1 py-0.5">docs/ARCHITECTURE.md</code> Phase 5 for how to
              wire in real Kite Connect credentials.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <AparixBadge tone="positive">{status.data.status}</AparixBadge>
              <span className="text-muted-foreground">
                {status.data.broker} · account {status.data.broker_user_id}
              </span>
              {isMock && <AparixBadge tone="warning">Simulated connection</AparixBadge>}
            </div>
            {status.data.last_synced_at && (
              <p className="text-xs text-muted-foreground">
                Last synced {new Date(status.data.last_synced_at).toLocaleString()}
              </p>
            )}
            <div className="flex gap-2">
              <button
                onClick={sync}
                disabled={busy}
                className="rounded border border-border px-4 py-1.5 text-sm font-medium hover:bg-surface-hover disabled:opacity-50"
              >
                {busy ? "Working…" : "Sync holdings"}
              </button>
              <button
                onClick={disconnect}
                disabled={busy}
                className="rounded border border-negative/40 px-4 py-1.5 text-sm font-medium text-negative hover:bg-surface-hover disabled:opacity-50"
              >
                Disconnect
              </button>
            </div>
            {lastSync && (
              <p className="text-xs text-muted-foreground">
                Synced {lastSync.synced} holdings.
                {lastSync.skipped.length > 0 &&
                  ` Skipped (outside this app's tracked universe): ${lastSync.skipped.join(", ")}.`}
              </p>
            )}
            {!status.data.live_trading_enabled && (
              <p className="text-xs text-muted-foreground">
                Live order placement through this connection is disabled (
                <code className="rounded bg-surface-hover px-1 py-0.5">BROKER_LIVE_TRADING_ENABLED=false</code>) —
                a deliberate default, not a bug. This account is sync-only until that&apos;s explicitly turned on.
              </p>
            )}
          </div>
        )}
        {actionError && <p className="mt-2 text-xs text-negative">{actionError}</p>}
      </AparixCard>

      {status.data?.connected && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <AparixCard>
              <AparixMetric label="Total value" value={formatInr(portfolio.data?.total_value ?? 0)} size="lg" />
            </AparixCard>
            <AparixCard>
              <AparixMetric label="Positions" value={String(portfolio.data?.holdings.length ?? 0)} />
            </AparixCard>
            <AparixCard>
              <AparixMetric label="Broker" value={status.data.broker ?? "—"} />
            </AparixCard>
          </div>

          <AparixCard title="Broker holdings (read-only)">
            <AparixTable<BrokerHolding>
              columns={[
                { header: "Symbol", render: (h) => <span className="font-medium">{h.symbol}</span> },
                { header: "Sector", render: (h) => h.sector },
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
              rows={portfolio.data?.holdings ?? []}
              keyFor={(h) => h.symbol}
              emptyMessage="No holdings synced yet — click Sync holdings above."
            />
          </AparixCard>

          <p className="text-xs text-muted-foreground">
            <Link href="/ai?q=what%27s%20in%20my%20broker%20account" className="text-accent hover:underline">
              Ask the AI about your broker account →
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
