import { create } from "zustand";

interface AppState {
  commandBarOpen: boolean;
  setCommandBarOpen: (open: boolean) => void;
  toggleCommandBar: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  commandBarOpen: false,
  setCommandBarOpen: (open) => set({ commandBarOpen: open }),
  toggleCommandBar: () => set((state) => ({ commandBarOpen: !state.commandBarOpen })),
}));
