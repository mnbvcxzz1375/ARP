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

export default function AgentsPage() {
  const t = useT();
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['agents', page, limit],
    queryFn: () => api.get('/v1/dashboard/agents', { params: { page, page_size: limit } }).then((r) => r.data),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('agents.error.load')} />;

  return (
    <div>
      <h2 className="font-display text-pixel-xl text-pixel-fg mb-6">{t('agents.page.title')}</h2>
      {/* Surface panel with a hard pixel shadow; the DataTable and the
          attached Pagination bar carry their own 2px borders. */}
      <div className="bg-pixel-surface shadow-pixel-sm">
        <DataTable
          columns={[
            { key: 'name', label: t('agents.table.name') },
            { key: 'agent_number', label: t('agents.table.agentNumber'), render: (r: any) => <span className="font-mono">{r.agent_number}</span> },
            {
              key: 'details',
              label: '',
              render: (r: any) => (
                // Accent solid chip with dark text: 5.36:1 in both themes (AA).
                <Link
                  to={`/app/agents/${r.agent_id}`}
                  className="inline-flex items-center px-2 py-1 font-pixel text-pixel-sm bg-pixel-accent text-[#191a26] border-2 border-[#191a26] hover:underline"
                >
                  {t('agents.table.view')}
                </Link>
              ),
            },
            { key: 'runtime', label: t('agents.table.runtime') },
            { key: 'status', label: t('agents.table.status'), render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'inbound_policy', label: t('agents.table.policy') },
            { key: 'created_at', label: t('agents.table.created'), render: (r: any) => <span className="font-mono">{r.created_at}</span> },
          ]}
          data={data?.agents ?? []}
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
