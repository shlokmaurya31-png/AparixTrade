"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/** Phase 1 gives every user a single default portfolio (created during
 * onboarding — see app/onboarding/page.tsx). Multi-portfolio comparison is
 * Phase 6 (§36 of the product spec); this hook just returns the first one. */
export function usePrimaryPortfolio() {
  const portfolios = useQuery({ queryKey: ["portfolios"], queryFn: api.portfolios.list });
  const primary = portfolios.data?.[0] ?? null;

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
