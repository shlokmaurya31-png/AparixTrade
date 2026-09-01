import { clsx } from "clsx";

type BadgeTone = "neutral" | "positive" | "negative" | "warning" | "accent";

interface AparixBadgeProps {
  children: React.ReactNode;
  tone?: BadgeTone;
  className?: string;
}

const toneClasses: Record<BadgeTone, string> = {
  neutral: "border-border text-muted-foreground",
  positive: "border-positive/40 text-positive",
  negative: "border-negative/40 text-negative",
  warning: "border-warning/40 text-warning",
  accent: "border-accent/40 text-accent",
};

export function AparixBadge({ children, tone = "neutral", className }: AparixBadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider",
        toneClasses[tone],
        className
      )}
    >
      {children}
    </span>
  );
}

/** Non-negotiable per docs/ARCHITECTURE.md §6/§8: every mock-derived number
 * in the UI must carry this. */
export function DemoDataBadge({ className }: { className?: string }) {
  return (
    <AparixBadge tone="warning" className={className}>
      Demo data
    </AparixBadge>
  );
}

export function ComingSoonBadge({ className }: { className?: string }) {
  return (
    <AparixBadge tone="neutral" className={className}>
      Coming soon
    </AparixBadge>
  );
}
