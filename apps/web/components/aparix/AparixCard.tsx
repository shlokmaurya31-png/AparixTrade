import { clsx } from "clsx";

interface AparixCardProps {
  title?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export function AparixCard({ title, action, children, className }: AparixCardProps) {
  return (
    <div className={clsx("rounded-md border border-border bg-surface", className)}>
      {(title || action) && (
        <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
          {title && (
            <h3 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{title}</h3>
          )}
          {action}
        </div>
      )}
      {/* flex-1/min-h-0 only take effect when a caller makes the card itself
          a flex column (e.g. a scrollable chat panel) — otherwise they're a
          no-op and this behaves like a plain block wrapper. */}
      <div className="flex min-h-0 flex-1 flex-col p-4">{children}</div>
    </div>
  );
}
