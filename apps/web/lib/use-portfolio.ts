"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type Portfolio } from "@/lib/api";
import { useAppStore } from "@/store/app-store";

// GET /portfolios returns every portfolio row for the user, including the
// lazily-created "paper" and "broker" singleton accounts (domains/paper_trading,
// domains/broker) — those have their own dedicated pages (/paper, /broker)
// and a different shape (cash-based / broker-synced), so they're excluded
// from "my portfolios" here and in the switcher (PortfolioSwitcher.tsx).
export function isSwitchablePortfolio(p: Portfolio): boolean {
  return p.kind !== "paper" && p.kind !== "broker";
}

/** Onboarding creates one default portfolio, but a user can create more
 * (Phase 6 — see components/aparix/PortfolioSwitcher.tsx). This hook
 * resolves the "active" one: whichever the switcher selected, or the first
 * (switchable) portfolio in the list if nothing's been explicitly chosen
 * yet (or the selected one no longer exists, e.g. it was on another
 * device). */
export function usePrimaryPortfolio() {
  const portfolios = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios.list });
  const switchable = (portfolios.data ?? []).filter(isSwitchablePortfolio);
  const selectedId = useAppStore((s) => s.selectedPortfolioId);
  const selected = selectedId ? switchable.find((p) => p.id === selectedId) : undefined;
  const primary = selected ?? switchable[0] ?? null;

  // All portfolio-derived queries share the ["portfolio", id, ...] prefix
  // specifically so a mutation (e.g. adding a holding) can invalidate every
  // one of them in a single call — queryClient.invalidateQueries({ queryKey:
  // ["portfolio", id] }) does a prefix match. Keying them independently was
  // tried first and caused a real bug: a new query added later (risk) was
  // forgotten in the invalidation call, so /risk silently showed pre-holding
  // data until the next 15s poll. Don't go back to independent keys.
  const analytics = useQuery({
    queryKey: ["portfolio", primary?.id, "analytics"],
    queryFn: () => api.portfolios.analytics(primary!.id),
    enabled: Boolean(primary),
    refetchInterval: 15_000,
  });

  const holdings = useQuery({
    queryKey: ["portfolio", primary?.id, "holdings"],
    queryFn: () => api.portfolios.holdings(primary!.id),
    enabled: Boolean(primary),
    refetchInterval: 15_000,
  });

  const risk = useQuery({
    queryKey: ["portfolio", primary?.id, "risk"],
    queryFn: () => api.risk.profile(primary!.id),
    enabled: Boolean(primary),
    refetchInterval: 15_000,
  });

  return {
    portfolio: primary,
    isLoading: portfolios.isLoading,
    analytics,
    holdings,
    risk,
  };
}
