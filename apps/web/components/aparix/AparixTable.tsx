interface Column<T> {
  header: string;
  align?: "left" | "right";
  render: (row: T) => React.ReactNode;
}

interface AparixTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  keyFor: (row: T) => string;
  emptyMessage?: string;
}

export function AparixTable<T>({ columns, rows, keyFor, emptyMessage = "No data yet." }: AparixTableProps<T>) {
  if (rows.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
            {columns.map((col) => (
              <th key={col.header} className={col.align === "right" ? "py-2 pr-2 text-right" : "py-2 pr-2"}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={keyFor(row)} className="border-b border-border/60 last:border-0">
              {columns.map((col) => (
                <td
                  key={col.header}
                  className={col.align === "right" ? "font-mono-nums py-2 pr-2 text-right tabular-nums" : "py-2 pr-2"}
                >
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
