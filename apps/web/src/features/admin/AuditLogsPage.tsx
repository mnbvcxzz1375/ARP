import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function AuditLogsPage() {
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/audit', page, limit],
    queryFn: () => api.get('/v1/admin/audit-logs', { params: { offset: (page - 1) * limit, limit } }).then((r) => r.data),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load audit logs" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Audit Logs</h2>
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'audit_id', label: 'ID', render: (r: any) => r.audit_id?.slice(0, 8) },
            { key: 'actor_type', label: 'Actor Type' },
            { key: 'actor_id', label: 'Actor', render: (r: any) => r.actor_id?.slice(0, 12) },
            { key: 'action', label: 'Action' },
            { key: 'resource_type', label: 'Resource' },
            { key: 'created_at', label: 'Created' },
          ]}
          data={data?.audit_logs ?? []}
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
