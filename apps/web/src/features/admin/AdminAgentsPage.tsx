import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import ConfirmDialog from '../../components/ConfirmDialog';
import StepUpDialog from '../../components/StepUpDialog';

type PendingAgentAction = {
  type: 'disable' | 'enable';
  agentId: string;
  agentName: string;
} | null;

function isStepUpNeeded(stepUpUntil: string | null | undefined): boolean {
  if (!stepUpUntil) return true;
  return new Date(stepUpUntil) <= new Date();
}

export default function AdminAgentsPage() {
  const [page, setPage] = useState(1);
  const limit = 20;
  const queryClient = useQueryClient();
  const { data: auth } = useAuth();
  const isSuperAdmin = auth?.role === 'super_admin';

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/agents', page, limit],
    queryFn: () => api.get('/v1/dashboard/admin/agents', { params: { offset: (page - 1) * limit, limit } }).then((r) => r.data),
    refetchInterval: 30000,
  });

  const [pendingAction, setPendingAction] = useState<PendingAgentAction>(null);
  const [showStepUp, setShowStepUp] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const toggleMutation = useMutation({
    mutationFn: ({ agentId, status }: { agentId: string; status: string }) =>
      api.post(`/v1/dashboard/admin/agents/${agentId}/disable`, { status }),
    onSuccess: () => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['admin/agents'] });
      queryClient.invalidateQueries({ queryKey: ['admin/overview'] });
    },
    onError: (err: any) => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(err?.response?.data?.detail || 'Failed to update agent');
    },
  });

  const handleConfirmAction = () => {
    if (!pendingAction) return;
    setActionError(null);
    if (isStepUpNeeded(auth?.step_up_until)) {
      setShowStepUp(true);
    } else {
      executeAction(pendingAction);
    }
  };

  const executeAction = (action: NonNullable<PendingAgentAction>) => {
    const newStatus = action.type === 'disable' ? 'offline' : 'online';
    toggleMutation.mutate({ agentId: action.agentId, status: newStatus });
  };

  const handleStepUpSuccess = () => {
    setShowStepUp(false);
    if (pendingAction) {
      executeAction(pendingAction);
    }
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load agents" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Agents</h2>
      {actionError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700" data-testid="action-error">
          {actionError}
        </div>
      )}
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'name', label: 'Name' },
            { key: 'agent_number', label: 'Agent Number' },
            {
              key: 'details',
              label: '',
              render: (r: any) => (
                <Link to={`/admin/agents/${r.agent_id}`} className="text-blue-600 hover:underline text-xs font-medium">
                  View
                </Link>
              ),
            },
            { key: 'owner_username', label: 'Owner' },
            { key: 'status', label: 'Status', render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'runtime', label: 'Runtime' },
            { key: 'inbound_policy', label: 'Policy' },
            { key: 'tasks_24h', label: 'Tasks (24h)' },
            { key: 'failed_tasks_24h', label: 'Failed' },
            {
              key: 'actions',
              label: 'Actions',
              render: (r: any) => (
                <div className="flex gap-2">
                  {isSuperAdmin ? (
                    <button
                      onClick={() => setPendingAction({
                        type: r.status === 'offline' ? 'enable' : 'disable',
                        agentId: r.agent_id,
                        agentName: r.name || r.agent_number,
                      })}
                      disabled={toggleMutation.isPending}
                      className={`px-2 py-1 text-xs font-medium rounded ${
                        r.status === 'offline'
                          ? 'text-green-700 bg-green-50 border border-green-200 hover:bg-green-100'
                          : 'text-yellow-700 bg-yellow-50 border border-yellow-200 hover:bg-yellow-100'
                      } disabled:opacity-50`}
                    >
                      {r.status === 'offline' ? 'Enable' : 'Disable'}
                    </button>
                  ) : (
                    <span className="text-xs text-gray-400">Super admin required</span>
                  )}
                </div>
              ),
            },
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

      <ConfirmDialog
        open={pendingAction !== null && !showStepUp}
        title={pendingAction?.type === 'disable' ? 'Disable Agent' : 'Enable Agent'}
        message={
          pendingAction?.type === 'disable'
            ? `Disable agent "${pendingAction?.agentName}"? It will go offline and stop accepting tasks.`
            : `Enable agent "${pendingAction?.agentName}"? It will be able to come online and accept tasks.`
        }
        variant={pendingAction?.type === 'disable' ? 'danger' : 'default'}
        confirmLabel={pendingAction?.type === 'disable' ? 'Disable' : 'Enable'}
        onConfirm={handleConfirmAction}
        onCancel={() => {
          setPendingAction(null);
          setActionError(null);
        }}
      />

      <StepUpDialog
        open={showStepUp}
        onSuccess={handleStepUpSuccess}
        onCancel={() => {
          setShowStepUp(false);
          setPendingAction(null);
          setActionError(null);
        }}
      />
    </div>
  );
}
