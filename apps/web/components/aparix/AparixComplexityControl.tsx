import { clsx } from "clsx";

export const COMPLEXITY_LEVELS = [
  { level: 1, name: "Simple", description: "Portfolio value, P&L, plain-English risk." },
  { level: 2, name: "Informed", description: "Sector exposure, volatility, correlations, drawdowns." },
  { level: 3, name: "Advanced", description: "VaR, CVaR, Sharpe, Sortino, factor exposure." },
  { level: 4, name: "Quant", description: "Monte Carlo, regime models, option Greeks, backtests." },
  { level: 5, name: "Institutional", description: "Full decomposition, scenario trees, liquidity analytics." },
] as const;

interface AparixComplexityControlProps {
  value: number;
  onChange: (level: number) => void;
  disabled?: boolean;
}

export function AparixComplexityControl({ value, onChange, disabled }: AparixComplexityControlProps) {
  const current = COMPLEXITY_LEVELS.find((l) => l.level === value) ?? COMPLEXITY_LEVELS[0];

  return (
    <div>
      <div className="flex gap-1">
        {COMPLEXITY_LEVELS.map((l) => (
          <button
            key={l.level}
            type="button"
            disabled={disabled}
            onClick={() => onChange(l.level)}
            className={clsx(
              "flex-1 rounded border py-1.5 text-xs font-medium transition-colors disabled:opacity-50",
              l.level === value
                ? "border-accent bg-accent text-accent-foreground"
                : "border-border text-muted-foreground hover:bg-surface-hover"
            )}
          >
            {l.level}
          </button>
        ))}
      </div>
      <div className="mt-2">
        <div className="text-sm font-medium">{current.name}</div>
        <div className="text-xs text-muted-foreground">{current.description}</div>
        {value >= 3 && (
          <div className="mt-1 text-xs text-warning">
            Levels 3–5 show the metrics Phase 1 can compute today; deeper quant metrics (VaR, Monte Carlo, factor
            models) are marked Coming soon until the Phase 2 risk engine ships.
          </div>
        )}
      </div>
    </div>
  );
}
