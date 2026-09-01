interface AparixHeatmapProps {
  symbols: string[];
  matrix: Record<string, Record<string, number | null>>;
  format?: (value: number) => string;
  /** Values are expected roughly in [-scale, scale] — correlation defaults to 1. */
  scale?: number;
}

function colorFor(value: number | null, scale: number): string {
  if (value === null) return "transparent";
  const clamped = Math.max(-scale, Math.min(scale, value)) / scale;
  const alpha = Math.abs(clamped) * 0.55 + 0.05;
  return clamped >= 0 ? `rgba(91, 143, 249, ${alpha})` : `rgba(242, 85, 90, ${alpha})`;
}

export function AparixHeatmap({ symbols, matrix, format = (v) => v.toFixed(2), scale = 1 }: AparixHeatmapProps) {
  return (
    <div className="overflow-x-auto">
      <table className="text-xs">
        <thead>
          <tr>
            <th className="px-2 py-1" />
            {symbols.map((s) => (
              <th key={s} className="font-mono-nums px-2 py-1 font-medium text-muted-foreground">
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((row) => (
            <tr key={row}>
              <th className="font-mono-nums px-2 py-1 text-right font-medium text-muted-foreground">{row}</th>
              {symbols.map((col) => {
                const value = matrix[row]?.[col] ?? null;
                return (
                  <td
                    key={col}
                    className="font-mono-nums px-2 py-1 text-center tabular-nums"
                    style={{ background: colorFor(value, scale) }}
                  >
                    {value !== null ? format(value) : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
