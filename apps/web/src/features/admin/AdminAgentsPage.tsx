import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function AdminAgentsPage() {
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/agents', page, limit],
    queryFn: () => api.get('/v1/admin/agents', { params: { offset: (page - 1) * limit, limit } }).then((r) => r.data),
    refetchInterval: 30000,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load agents" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Agents</h2>
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'name', label: 'Name' },
            { key: 'agent_number', label: 'Agent Number' },
            { key: 'owner_username', label: 'Owner' },
            { key: 'status', label: 'Status', render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'runtime', label: 'Runtime' },
            { key: 'inbound_policy', label: 'Policy' },
            { key: 'tasks_24h', label: 'Tasks (24h)' },
            { key: 'failed_tasks_24h', label: 'Failed' },
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
