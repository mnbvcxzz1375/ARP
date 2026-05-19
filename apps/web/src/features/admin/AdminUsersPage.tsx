import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import RoleBadge from '../../components/RoleBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function AdminUsersPage() {
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/users', page, limit],
    queryFn: () => api.get('/v1/admin/users', { params: { offset: (page - 1) * limit, limit } }).then((r) => r.data),
    refetchInterval: 30000,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load users" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Users</h2>
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'username', label: 'Username' },
            { key: 'role', label: 'Role', render: (r: any) => <RoleBadge role={r.role} /> },
            { key: 'is_disabled', label: 'Disabled', render: (r: any) => r.is_disabled ? 'Yes' : 'No' },
            { key: 'agents_count', label: 'Agents' },
            { key: 'active_api_keys_count', label: 'API Keys' },
            { key: 'tasks_24h', label: 'Tasks (24h)' },
            { key: 'failed_tasks_24h', label: 'Failed' },
            { key: 'created_at', label: 'Created' },
          ]}
          data={data?.users ?? []}
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
