import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { useT } from '../../i18n';

export default function TasksPage() {
  const t = useT();
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['tasks', page, limit],
    queryFn: () => api.get('/v1/dashboard/tasks', { params: { offset: (page - 1) * limit, limit } }).then((r) => r.data),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('tasks.error.load')} />;

  return (
    <div>
      <h2 className="font-display text-pixel-xl text-pixel-fg mb-6">{t('tasks.page.title')}</h2>
      {/* Surface panel with a hard pixel shadow; the DataTable and the
          attached Pagination bar carry their own 2px borders. */}
      <div className="bg-pixel-surface shadow-pixel-sm">
        <DataTable
          columns={[
            { key: 'task_id', label: t('tasks.table.id'), render: (r: any) => <span className="font-mono">{r.task_id?.slice(0, 8)}</span> },
            {
              key: 'details',
              label: '',
              render: (r: any) => (
                // Accent solid chip with dark text: 5.36:1 in both themes (AA).
                <Link
                  to={`/app/tasks/${r.task_id}`}
                  className="inline-flex items-center px-2 py-1 font-pixel text-pixel-sm bg-pixel-accent text-[#191a26] border-2 border-[#191a26] hover:underline"
                >
                  {t('tasks.table.view')}
                </Link>
              ),
            },
            { key: 'status', label: t('tasks.table.status'), render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'sender_agent', label: t('tasks.table.sender'), render: (r: any) => <span className="font-mono">{r.sender_agent?.slice(0, 8)}</span> },
            { key: 'target_agent', label: t('tasks.table.target'), render: (r: any) => <span className="font-mono">{r.target_agent?.slice(0, 8)}</span> },
            { key: 'created_at', label: t('tasks.table.created'), render: (r: any) => <span className="font-mono">{r.created_at}</span> },
          ]}
          data={data?.tasks ?? []}
        />
        <Pagination
          offset={(page - 1) * limit}
          limit={limit}
          total={data?.total ?? 0}
          onPageChange={(offset) => setPage(Math.floor(offset / limit) + 1)}
        />
      </div>
    </div>
  );
}
