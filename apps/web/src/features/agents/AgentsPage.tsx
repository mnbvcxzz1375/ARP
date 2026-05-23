import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function AgentsPage() {
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['agents', page, limit],
    queryFn: () => api.get('/v1/dashboard/agents', { params: { page, page_size: limit } }).then((r) => r.data),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load agents" />;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Agents</h2>
      </div>
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'name', label: 'Name' },
            { key: 'agent_number', label: 'Agent Number' },
            {
              key: 'details',
              label: '',
              render: (r: any) => (
                <Link to={`/app/agents/${r.agent_id}`} className="text-blue-600 hover:underline text-xs font-medium">
                  View
                </Link>
              ),
            },
            { key: 'runtime', label: 'Runtime' },
            { key: 'status', label: 'Status', render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'inbound_policy', label: 'Policy' },
            { key: 'created_at', label: 'Created' },
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
