"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/lib/api";
import { isSwitchablePortfolio } from "@/lib/use-portfolio";
import { useAppStore } from "@/store/app-store";

const KIND_LABELS: Record<string, string> = {
  long_term: "Long term",
  trading: "Trading",
  options: "Options",
  experimental: "Experimental",
};

/** Header-level picker for which of the user's own portfolios /portfolio,
 * /risk, /events, and /ai are scoped to (usePrimaryPortfolio,
 * lib/use-portfolio.ts) — Phase 6 multi-portfolio support. Paper trading
 * and broker accounts aren't included; they have their own dedicated pages
 * and a different account shape. */
export function PortfolioSwitcher() {
  const queryClient = useQueryClient();
  const portfolios = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios.list });
  const selectedId = useAppStore((s) => s.selectedPortfolioId);
  const setSelectedId = useAppStore((s) => s.setSelectedPortfolioId);

  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState("long_term");
  const [submitting, setSubmitting] = useState(false);

  const switchable = (portfolios.data ?? []).filter(isSwitchablePortfolio);
  const activeId = selectedId && switchable.some((p) => p.id === selectedId) ? selectedId : switchable[0]?.id;

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setSubmitting(true);
    try {
      const created = await api.portfolios.create({ name: newName.trim(), kind: newKind });
      await queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      setSelectedId(created.id);
      setNewName("");
      setCreating(false);
    } finally {
      setSubmitting(false);
    }
  }

  if (switchable.length === 0) return null;

  return (
    <div className="flex items-center gap-1.5">
      <select
        value={activeId ?? ""}
        onChange={(e) => setSelectedId(e.target.value)}
        className="rounded border border-border bg-transparent px-2 py-1 text-xs outline-none focus:border-accent"
      >
        {switchable.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name} ({KIND_LABELS[p.kind] ?? p.kind})
          </option>
        ))}
      </select>

      {!creating && (
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-surface-hover"
        >
          + New
        </button>
      )}

      {creating && (
        <form onSubmit={onCreate} className="flex items-center gap-1.5">
          <input
            autoFocus
            required
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Portfolio name"
            className="w-32 rounded border border-border bg-transparent px-2 py-1 text-xs outline-none focus:border-accent"
          />
          <select
            value={newKind}
            onChange={(e) => setNewKind(e.target.value)}
            className="rounded border border-border bg-transparent px-2 py-1 text-xs outline-none focus:border-accent"
          >
            {Object.entries(KIND_LABELS).map(([kind, label]) => (
              <option key={kind} value={kind}>
                {label}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={submitting}
            className="rounded bg-accent px-2 py-1 text-xs font-medium text-accent-foreground disabled:opacity-50"
          >
            {submitting ? "…" : "Create"}
          </button>
          <button
            type="button"
            onClick={() => setCreating(false)}
            className="text-xs text-muted-foreground hover:underline"
          >
            Cancel
          </button>
        </form>
      )}
    </div>
  );
}
