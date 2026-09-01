"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useLogout } from "@/lib/use-auth";
import { useAppStore } from "@/store/app-store";

interface Command {
  id: string;
  label: string;
  hint: string;
  run: (router: ReturnType<typeof useRouter>, logout: () => void) => void;
}

const COMMANDS: Command[] = [
  { id: "home", label: "Go to Home", hint: "Command center", run: (r) => r.push("/home") },
  { id: "portfolio", label: "Go to Portfolio", hint: "Holdings & analytics", run: (r) => r.push("/portfolio") },
  { id: "risk", label: "Go to Risk & Simulation", hint: "VaR, Monte Carlo, stress test, backtest", run: (r) => r.push("/risk") },
  { id: "events", label: "Go to Market Events", hint: "Event feed & portfolio impact", run: (r) => r.push("/events") },
  { id: "ai", label: "Open AI Terminal", hint: "Ask Aparix", run: (r) => r.push("/ai") },
  { id: "logout", label: "Log out", hint: "End session", run: (_r, logout) => logout() },
];

export function AparixCommandBar() {
  const open = useAppStore((s) => s.commandBarOpen);
  const setOpen = useAppStore((s) => s.setCommandBarOpen);
  const [query, setQuery] = useState("");
  const router = useRouter();
  const logout = useLogout();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setOpen]);

  const filtered = useMemo(
    () => COMMANDS.filter((c) => c.label.toLowerCase().includes(query.toLowerCase())),
    [query]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[15vh]"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-lg rounded-md border border-border bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask Aparix anything, or jump to a page…"
          className="w-full border-b border-border bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground"
        />
        <div className="max-h-80 overflow-y-auto p-1.5">
          {filtered.map((cmd) => (
            <button
              key={cmd.id}
              onClick={() => {
                cmd.run(router, logout);
                setOpen(false);
                setQuery("");
              }}
              className="flex w-full items-center justify-between rounded px-3 py-2 text-left text-sm hover:bg-surface-hover"
            >
              <span>{cmd.label}</span>
              <span className="text-xs text-muted-foreground">{cmd.hint}</span>
            </button>
          ))}
          {filtered.length === 0 && (
            <p className="px-3 py-4 text-sm text-muted-foreground">
              No matching command. Free-text AI search is Phase 3 — try the AI Terminal instead.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
