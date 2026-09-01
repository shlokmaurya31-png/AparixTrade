"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { AparixCommandBar } from "@/components/aparix/AparixCommandBar";
import { PortfolioSwitcher } from "@/components/aparix/PortfolioSwitcher";
import { useLogout, useRequireAuth } from "@/lib/use-auth";
import { useAppStore } from "@/store/app-store";

const NAV_ITEMS = [
  { href: "/home", label: "Home" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/options", label: "Options" },
  { href: "/paper", label: "Paper Trading" },
  { href: "/broker", label: "Broker" },
  { href: "/risk", label: "Risk" },
  { href: "/events", label: "Events" },
  { href: "/ai", label: "AI Terminal" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { data: user } = useRequireAuth();
  const pathname = usePathname();
  const logout = useLogout();
  const setCommandBarOpen = useAppStore((s) => s.setCommandBarOpen);

  // The /admin route itself still enforces access server-side (403 on the
  // API calls) — hiding the link is a UX nicety for non-admins, not the
  // access control (see docs/ARCHITECTURE.md Phase 3 trade-offs).
  const navItems = user?.is_admin ? [...NAV_ITEMS, { href: "/admin", label: "Admin" }] : NAV_ITEMS;

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-surface">
        <div className="px-4 py-4">
          <span className="text-lg font-semibold tracking-tight">Aparix</span>
        </div>
        <nav className="flex-1 space-y-0.5 px-2">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded px-3 py-2 text-sm ${
                  active ? "bg-accent/10 text-accent" : "text-muted-foreground hover:bg-surface-hover"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border p-3 text-xs text-muted-foreground">
          <div className="truncate">{user?.email}</div>
          <button onClick={logout} className="mt-1 text-accent hover:underline">
            Log out
          </button>
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-border px-6 py-3">
          <button
            onClick={() => setCommandBarOpen(true)}
            className="w-80 rounded border border-border bg-transparent px-3 py-1.5 text-left text-sm text-muted-foreground hover:bg-surface-hover"
          >
            Ask Aparix anything…{" "}
            <kbd className="float-right text-[10px] text-muted-foreground">⌘K</kbd>
          </button>
          <div className="flex items-center gap-3">
            <PortfolioSwitcher />
            <span className="text-xs text-muted-foreground">
              Complexity level {user?.preferences.complexity_level ?? 1}
            </span>
          </div>
        </header>
        <main className="flex-1 bg-background p-6">{children}</main>
      </div>

      <AparixCommandBar />
    </div>
  );
}
