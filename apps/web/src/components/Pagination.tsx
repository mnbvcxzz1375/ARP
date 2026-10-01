import { useT } from '../i18n';

interface PaginationProps {
  offset: number;
  limit: number;
  total: number;
  onPageChange: (offset: number) => void;
}

export default function Pagination({ offset, limit, total, onPageChange }: PaginationProps) {
  const t = useT();
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));

  if (totalPages <= 1) return null;

  // Plain hyphen only (no en-dash / em-dash anywhere in UI copy).
  const rangeText = t('common.pagination.range', {
    start: offset + 1,
    end: Math.min(offset + limit, total),
    total,
  });

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3 border-t-2 border-pixel-line bg-pixel-surface">
      <p className="text-lg text-pixel-muted">{rangeText}</p>
      <div className="flex items-center gap-2">
        <button
          disabled={currentPage <= 1}
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          className="min-h-[44px] min-w-[44px] px-3 py-1 font-pixel text-pixel-base border-2 border-pixel-line text-pixel-fg hover:bg-pixel-raised disabled:opacity-40"
        >
          {t('common.pagination.prev')}
        </button>
        <span className="px-2 font-mono text-lg text-pixel-muted">
          {currentPage} / {totalPages}
        </span>
        <button
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(offset + limit)}
          className="min-h-[44px] min-w-[44px] px-3 py-1 font-pixel text-pixel-base border-2 border-pixel-line text-pixel-fg hover:bg-pixel-raised disabled:opacity-40"
        >
          {t('common.pagination.next')}
        </button>
      </div>
    </div>
  );
}
