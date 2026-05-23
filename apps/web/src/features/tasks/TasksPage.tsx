import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function TasksPage() {
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['tasks', page, limit],
    queryFn: () => api.get('/v1/dashboard/tasks', { params: { offset: (page - 1) * limit, limit } }).then((r) => r.data),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load tasks" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Tasks</h2>
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'task_id', label: 'ID', render: (r: any) => r.task_id?.slice(0, 8) },
            {
              key: 'details',
              label: '',
              render: (r: any) => (
                <Link to={`/app/tasks/${r.task_id}`} className="text-blue-600 hover:underline text-xs font-medium">
                  View
                </Link>
              ),
            },
            { key: 'status', label: 'Status', render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'sender_agent', label: 'Sender', render: (r: any) => r.sender_agent?.slice(0, 8) },
            { key: 'target_agent', label: 'Target', render: (r: any) => r.target_agent?.slice(0, 8) },
            { key: 'created_at', label: 'Created' },
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
