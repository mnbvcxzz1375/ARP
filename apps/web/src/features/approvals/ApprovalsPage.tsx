import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import RiskBadge from '../../components/RiskBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function ApprovalsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['approvals'],
    queryFn: () => api.get('/v1/dashboard/approvals').then((r) => r.data),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load approvals" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Approvals</h2>
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'approval_id', label: 'ID', render: (r: any) => r.approval_id?.slice(0, 8) },
            { key: 'type', label: 'Type' },
            { key: 'status', label: 'Status', render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'risk_level', label: 'Risk', render: (r: any) => <RiskBadge level={r.risk_level} /> },
            { key: 'action_kind', label: 'Action' },
            { key: 'created_at', label: 'Created' },
          ]}
          data={data?.approvals ?? []}
        />
      </div>
    </div>
  );
}
