import { useT } from '../i18n';
import { cn } from '../lib/utils';

interface DataTableProps<T> {
  columns: { key: string; label: string; render?: (row: T) => React.ReactNode }[];
  data: T[];
  className?: string;
}

export default function DataTable<T extends object>({
  columns,
  data,
  className,
}: DataTableProps<T>) {
  const t = useT();
  return (
    <div
      className={cn(
        'overflow-x-auto border-2 border-pixel-line bg-pixel-surface',
        className,
      )}
    >
      <table className="min-w-full">
        <thead className="border-b-2 border-pixel-line bg-pixel-raised">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className="px-4 py-2 text-left font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        {/* NOTE: Tailwind 3 silently drops divide-pixel-line/60 (opacity
            modifier on a var() color produces no rule at all), which would
            fall back to preflight #e5e7eb and draw light lines on the dark
            surface. Bare divide-pixel-line generates correctly. */}
        <tbody className="divide-y divide-pixel-line">
          {data.map((row, idx) => (
            <tr key={idx} className="hover:bg-pixel-raised">
              {columns.map((col) => (
                <td
                  key={col.key}
                  className="px-4 py-2 text-base leading-relaxed text-pixel-fg"
                >
                  {col.render ? col.render(row) : String((row as Record<string, any>)[col.key] ?? '')}
                </td>
              ))}
            </tr>
          ))}
          {data.length === 0 && (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-8 text-center text-base text-pixel-muted"
              >
                {t('common.status.noData')}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
