"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { AparixCard } from "@/components/aparix/AparixCard";
import { DemoDataBadge } from "@/components/aparix/AparixBadge";
import { AparixMetric } from "@/components/aparix/AparixMetric";
import { AparixTable } from "@/components/aparix/AparixTable";
import { api, type CorporateAction, type FinancialStatement } from "@/lib/api";

const ACTION_TYPE_LABELS: Record<CorporateAction["action_type"], string> = {
  dividend: "Dividend",
  split: "Stock split",
  bonus: "Bonus issue",
  rights: "Rights issue",
  buyback: "Buyback",
  merger: "Merger",
  demerger: "Demerger",
  symbol_change: "Symbol change",
  isin_change: "ISIN change",
  delisting: "Delisting",
};

function formatCrore(value: number): string {
  return `₹${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(value)} cr`;
}

function formatRatio(value: number | null, suffix = ""): string {
  return value === null ? "—" : `${value.toFixed(2)}${suffix}`;
}

export default function FundamentalsPage() {
  const securities = useQuery({ queryKey: ["securities"], queryFn: api.market.securities });
  const [symbolChoice, setSymbolChoice] = useState<string | null>(null);
  const [periodType, setPeriodType] = useState<"annual" | "quarterly">("annual");

  const defaultSymbol = useMemo(() => {
    const list = securities.data ?? [];
    return (list.find((s) => !s.is_index) ?? list[0])?.symbol ?? null;
  }, [securities.data]);
  const symbol = symbolChoice ?? defaultSymbol;

  const latest = useQuery({
    queryKey: ["fundamentals-latest", symbol, periodType],
    queryFn: () => api.fundamentals.latest(symbol!, periodType),
    enabled: Boolean(symbol),
    retry: false,
  });
  const ratios = useQuery({
    queryKey: ["fundamentals-ratios", symbol, periodType],
    queryFn: () => api.fundamentals.ratios(symbol!, periodType),
    enabled: Boolean(symbol),
    retry: false,
  });
  const history = useQuery({
    queryKey: ["fundamentals-history", symbol, periodType],
    queryFn: () => api.fundamentals.history(symbol!, periodType),
    enabled: Boolean(symbol),
  });
  const corporateActions = useQuery({
    queryKey: ["corporate-actions", symbol],
    queryFn: () => api.corporateActions.list(symbol!),
    enabled: Boolean(symbol),
  });

  const r = ratios.data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">Fundamentals</h1>
        <DemoDataBadge />
      </div>
      <p className="text-xs text-muted-foreground">
        Synthetic financial statements and computed ratios — not a real company&apos;s actual financials.
        Point-in-time: results only reflect what would have actually been announced by the selected date.
      </p>

      <AparixCard title="Statement">
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs text-muted-foreground">Symbol</label>
            <select
              value={symbol ?? ""}
              onChange={(e) => setSymbolChoice(e.target.value)}
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
            <label className="mb-1 block text-xs text-muted-foreground">Period</label>
            <select
              value={periodType}
              onChange={(e) => setPeriodType(e.target.value as "annual" | "quarterly")}
              className="rounded border border-border bg-transparent px-2 py-1.5 text-sm outline-none focus:border-accent"
            >
              <option value="annual">Annual</option>
              <option value="quarterly">Quarterly</option>
            </select>
          </div>
        </div>

        {latest.isError && (
          <p className="text-sm text-negative">No fundamentals available for this symbol/period yet.</p>
        )}

        {latest.data && (
          <>
            <p className="mb-3 text-xs text-muted-foreground">
              FY{latest.data.fiscal_year}, period ended {latest.data.period_end} — announced{" "}
              {latest.data.announcement_date}. Figures in {latest.data.unit} {latest.data.currency}.
            </p>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <AparixMetric label="Revenue" value={formatCrore(latest.data.revenue)} />
              <AparixMetric label="EBITDA" value={formatCrore(latest.data.ebitda)} />
              <AparixMetric label="PAT" value={formatCrore(latest.data.pat)} />
              <AparixMetric label="EPS" value={`₹${latest.data.eps.toFixed(2)}`} />
              <AparixMetric label="Total equity" value={formatCrore(latest.data.total_equity)} />
              <AparixMetric label="Total debt" value={formatCrore(latest.data.total_debt)} />
              <AparixMetric label="Free cash flow" value={formatCrore(latest.data.free_cash_flow)} />
              <AparixMetric
                label="Shares outstanding"
                value={latest.data.shares_outstanding ? `${latest.data.shares_outstanding.toFixed(1)} cr` : "—"}
              />
            </div>
          </>
        )}
      </AparixCard>

      <AparixCard title="Ratios">
        {r ? (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <AparixMetric label="ROE" value={formatRatio(r.roe_pct, "%")} />
              <AparixMetric label="ROCE" value={formatRatio(r.roce_pct, "%")} />
              <AparixMetric label="ROA" value={formatRatio(r.roa_pct, "%")} />
              <AparixMetric label="Debt / Equity" value={formatRatio(r.debt_to_equity)} />
              <AparixMetric label="Interest coverage" value={formatRatio(r.interest_coverage)} />
              <AparixMetric label="Current ratio" value={formatRatio(r.current_ratio)} />
              <AparixMetric label="P/E" value={formatRatio(r.pe_ratio)} />
              <AparixMetric label="P/B" value={formatRatio(r.pb_ratio)} />
              <AparixMetric label="EV/EBITDA" value={formatRatio(r.ev_to_ebitda)} />
              <AparixMetric label="EV/Sales" value={formatRatio(r.ev_to_sales)} />
              <AparixMetric label="FCF yield" value={formatRatio(r.fcf_yield_pct, "%")} />
              <AparixMetric
                label="Market cap"
                value={r.market_cap ? formatCrore(r.market_cap) : "—"}
              />
            </div>
            <p className="mt-3 text-xs text-muted-foreground">{r.assumptions}</p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">No ratios available.</p>
        )}
      </AparixCard>

      <AparixCard title={`${periodType === "annual" ? "Annual" : "Quarterly"} history`}>
        <AparixTable<FinancialStatement>
          columns={[
            { header: "FY", render: (s) => s.fiscal_year },
            { header: "Period end", render: (s) => s.period_end },
            { header: "Revenue", align: "right", render: (s) => formatCrore(s.revenue) },
            { header: "PAT", align: "right", render: (s) => formatCrore(s.pat) },
            { header: "EPS", align: "right", render: (s) => `₹${s.eps.toFixed(2)}` },
          ]}
          rows={history.data ?? []}
          keyFor={(s) => `${s.period_end}-${s.period_type}`}
          emptyMessage="No history available."
        />
      </AparixCard>

      <AparixCard title="Corporate actions">
        <AparixTable<CorporateAction>
          columns={[
            { header: "Type", render: (a) => ACTION_TYPE_LABELS[a.action_type] },
            {
              header: "Detail",
              render: (a) =>
                a.ratio != null
                  ? `Ratio ${a.ratio.toFixed(2)}`
                  : a.amount != null
                    ? `₹${a.amount.toFixed(2)}/share`
                    : "—",
            },
            { header: "Ex-date", render: (a) => a.ex_date },
            { header: "Announced", render: (a) => a.announcement_date },
          ]}
          rows={corporateActions.data ?? []}
          keyFor={(a) => a.id}
          emptyMessage="No corporate actions on record for this symbol."
        />
      </AparixCard>
    </div>
  );
}
