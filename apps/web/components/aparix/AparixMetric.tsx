import { clsx } from "clsx";

interface AparixMetricProps {
  label: string;
  value: string;
  delta?: { value: string; positive: boolean } | null;
  hint?: string;
  size?: "md" | "lg";
}

export function AparixMetric({ label, value, delta, hint, size = "md" }: AparixMetricProps) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div
        className={clsx(
          "font-mono-nums mt-1 font-semibold tabular-nums",
          size === "lg" ? "text-3xl" : "text-xl"
        )}
      >
        {value}
      </div>
      {delta && (
        <div
          className={clsx(
            "font-mono-nums mt-0.5 text-sm tabular-nums",
            delta.positive ? "text-positive" : "text-negative"
          )}
        >
          {delta.value}
        </div>
      )}
      {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}
