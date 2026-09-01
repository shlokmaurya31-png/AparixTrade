import { create } from "zustand";

interface AppState {
  commandBarOpen: boolean;
  setCommandBarOpen: (open: boolean) => void;
  toggleCommandBar: () => void;
  // The user's chosen portfolio (Phase 6 multi-portfolio switcher, see
  // components/aparix/PortfolioSwitcher.tsx). null means "no explicit
  // choice yet" — usePrimaryPortfolio (lib/use-portfolio.ts) falls back to
  // the first portfolio in that case. Deliberately not persisted to
  // localStorage: a stale portfolio id surviving a full reload after the
  // portfolio list changes (e.g. it was renamed on another device) is a
  // worse failure mode than just re-defaulting to the first one.
  selectedPortfolioId: string | null;
  setSelectedPortfolioId: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  commandBarOpen: false,
  setCommandBarOpen: (open) => set({ commandBarOpen: open }),
  toggleCommandBar: () => set((state) => ({ commandBarOpen: !state.commandBarOpen })),
  selectedPortfolioId: null,
  setSelectedPortfolioId: (id) => set({ selectedPortfolioId: id }),
}));
