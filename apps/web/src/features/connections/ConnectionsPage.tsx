import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function ConnectionsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['connections'],
    queryFn: () => api.get('/v1/dashboard/connections').then((r) => r.data),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load connections" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Connections & Firewall</h2>

      <div className="bg-white rounded-lg border overflow-hidden mb-6">
        <div className="px-4 py-3 border-b bg-gray-50">
          <h3 className="text-sm font-medium text-gray-700">Agents</h3>
        </div>
        <DataTable
          columns={[
            { key: 'agent_number', label: 'Agent Number' },
            { key: 'inbound_policy', label: 'Inbound Policy' },
            { key: 'pending_requests', label: 'Pending' },
            { key: 'accepted_connections', label: 'Accepted' },
            { key: 'rejected_connections', label: 'Rejected' },
          ]}
          data={data?.agents ?? []}
        />
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        <div className="px-4 py-3 border-b bg-gray-50">
          <h3 className="text-sm font-medium text-gray-700">Pending Requests</h3>
        </div>
        <DataTable
          columns={[
            { key: 'connection_id', label: 'ID', render: (r: any) => r.connection_id?.slice(0, 8) },
            { key: 'agent_number', label: 'Agent' },
            { key: 'requester_agent', label: 'Requester', render: (r: any) => r.requester_agent?.slice(0, 8) },
            { key: 'requested_policy', label: 'Requested Policy' },
            { key: 'created_at', label: 'Created' },
          ]}
          data={data?.pending_requests ?? []}
        />
      </div>
    </div>
  );
}
