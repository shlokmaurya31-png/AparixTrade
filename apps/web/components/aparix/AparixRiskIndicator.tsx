import { clsx } from "clsx";

const LABELS: Record<number, string> = {
  1: "Low",
  2: "Fairly low",
  3: "Moderate",
  4: "Elevated",
  5: "High",
};

const TONES: Record<number, string> = {
  1: "bg-positive",
  2: "bg-positive",
  3: "bg-warning",
  4: "bg-negative",
  5: "bg-negative",
};

export function AparixRiskIndicator({ score }: { score: number }) {
  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="font-mono-nums text-xl font-semibold">{score}/5</span>
        <span className="text-sm text-muted-foreground">{LABELS[score] ?? "Unknown"}</span>
      </div>
      <div className="mt-2 flex gap-1">
        {[1, 2, 3, 4, 5].map((level) => (
          <div
            key={level}
            className={clsx("h-1.5 flex-1 rounded-full", level <= score ? TONES[score] : "bg-border")}
          />
        ))}
      </div>
    </div>
  );
}
