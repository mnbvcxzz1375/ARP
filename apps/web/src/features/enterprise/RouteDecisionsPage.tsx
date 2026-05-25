import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import RiskBadge from '../../components/RiskBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function RouteDecisionsPage() {
  const [page, setPage] = useState(1);
  const [taskIdFilter, setTaskIdFilter] = useState('');
  const [appliedFilter, setAppliedFilter] = useState<string | undefined>(undefined);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['route-decisions', page, limit, appliedFilter],
    queryFn: () =>
      api
        .get('/v1/routes/decisions', {
          params: {
            offset: (page - 1) * limit,
            limit,
            task_id: appliedFilter || undefined,
          },
        })
        .then((r) => r.data),
  });

  const handleSearch = () => {
    setAppliedFilter(taskIdFilter || undefined);
    setPage(1);
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load route decisions" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Route Decisions</h2>

      <div className="mb-4 flex gap-2">
        <input
          type="text"
          value={taskIdFilter}
          onChange={(e) => setTaskIdFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Filter by Task ID"
          className="px-3 py-1.5 text-sm border rounded bg-white"
        />
        <button
          onClick={handleSearch}
          className="px-3 py-1.5 text-sm font-medium text-white bg-gray-900 rounded hover:bg-gray-800"
        >
          Search
        </button>
        {appliedFilter && (
          <button
            onClick={() => {
              setTaskIdFilter('');
              setAppliedFilter(undefined);
              setPage(1);
            }}
            className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50"
          >
            Clear
          </button>
        )}
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'task_id', label: 'Task ID', render: (r: any) => r.task_id?.slice(0, 8) ?? '-' },
            { key: 'selected_route_type', label: 'Route Type' },
            { key: 'risk_level', label: 'Risk', render: (r: any) => <RiskBadge level={r.risk_level ?? 'low'} /> },
            { key: 'fallback_from_route', label: 'Fallback From', render: (r: any) => r.fallback_from_route || '-' },
            { key: 'fallback_reason', label: 'Fallback Reason', render: (r: any) => r.fallback_reason || '-' },
            {
              key: 'shadow_mode',
              label: 'Shadow',
              render: (r: any) => (
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  r.shadow_mode ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-600'
                }`}>
                  {r.shadow_mode ? 'Yes' : 'No'}
                </span>
              ),
            },
            {
              key: 'decision_time_ms',
              label: 'Decision (ms)',
              render: (r: any) => r.decision_time_ms != null ? `${r.decision_time_ms}` : '-',
            },
            {
              key: 'created_at',
              label: 'Created',
              render: (r: any) => r.created_at ? new Date(r.created_at).toLocaleString() : '-',
            },
          ]}
          data={data?.decisions ?? []}
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
