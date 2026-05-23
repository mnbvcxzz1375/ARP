import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import ConfirmDialog from '../../components/ConfirmDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

interface DialogState {
  connectionId: string;
  action: 'accept' | 'reject';
}

const POLICY_OPTIONS = ['private', 'contacts_only', 'request_approval', 'public'];

export default function ConnectionsPage() {
  const queryClient = useQueryClient();
  const [dialogState, setDialogState] = useState<DialogState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingAgentIds, setSavingAgentIds] = useState<Set<string>>(new Set());
  const [policyEdits, setPolicyEdits] = useState<Record<string, string>>({});

  const { data, isLoading, isError: isQueryError } = useQuery({
    queryKey: ['connections'],
    queryFn: () => api.get('/v1/dashboard/connections').then((r) => r.data),
  });

  const acceptMutation = useMutation({
    mutationFn: (connectionId: string) =>
      api.post(`/v1/dashboard/connections/${connectionId}/accept`),
    onSuccess: () => {
      setDialogState(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['connections'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard/overview'] });
    },
    onError: (err: unknown) => {
      setDialogState(null);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || 'Failed to accept connection');
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (connectionId: string) =>
      api.post(`/v1/dashboard/connections/${connectionId}/reject`),
    onSuccess: () => {
      setDialogState(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['connections'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard/overview'] });
    },
    onError: (err: unknown) => {
      setDialogState(null);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || 'Failed to reject connection');
    },
  });

  const firewallMutation = useMutation({
    mutationFn: ({ agentId, inboundPolicy }: { agentId: string; inboundPolicy: string }) =>
      api.patch(`/v1/dashboard/agents/${agentId}/firewall`, { inbound_policy: inboundPolicy }),
    onSuccess: (_data, variables) => {
      const { agentId } = variables;
      setSavingAgentIds((prev) => {
        const next = new Set(prev);
        next.delete(agentId);
        return next;
      });
      setPolicyEdits((prev) => {
        const next = { ...prev };
        delete next[agentId];
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ['connections'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard/overview'] });
    },
    onError: (err: unknown, variables) => {
      const { agentId } = variables;
      setSavingAgentIds((prev) => {
        const next = new Set(prev);
        next.delete(agentId);
        return next;
      });
      setPolicyEdits((prev) => {
        const next = { ...prev };
        delete next[agentId];
        return next;
      });
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || 'Failed to update firewall policy');
    },
  });

  const isMutating = acceptMutation.isPending || rejectMutation.isPending;

  const handleDialogOpen = (connectionId: string, action: 'accept' | 'reject') => {
    setError(null);
    setDialogState({ connectionId, action });
  };

  const handleDialogCancel = () => {
    setDialogState(null);
    setError(null);
  };

  const handleConfirm = () => {
    if (!dialogState || isMutating) return;
    if (dialogState.action === 'accept') {
      acceptMutation.mutate(dialogState.connectionId);
    } else {
      rejectMutation.mutate(dialogState.connectionId);
    }
  };

  const handlePolicyChange = (agentId: string, newPolicy: string) => {
    setError(null);
    setSavingAgentIds((prev) => new Set(prev).add(agentId));
    setPolicyEdits((prev) => ({ ...prev, [agentId]: newPolicy }));
    firewallMutation.mutate({ agentId, inboundPolicy: newPolicy });
  };

  if (isLoading) return <LoadingState />;
  if (isQueryError) return <ErrorState message="Failed to load connections" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Connections & Firewall</h2>

      {error && (
        <div className="mb-4 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border overflow-hidden mb-6">
        <div className="px-4 py-3 border-b bg-gray-50">
          <h3 className="text-sm font-medium text-gray-700">Agents</h3>
        </div>
        <DataTable
          columns={[
            { key: 'agent_number', label: 'Agent Number' },
            {
              key: 'inbound_policy',
              label: 'Inbound Policy',
              render: (r: any) => {
                const isSaving = savingAgentIds.has(r.agent_id);
                const displayValue = r.agent_id in policyEdits ? policyEdits[r.agent_id] : r.inbound_policy;
                return (
                  <div className="flex items-center gap-2">
                    <select
                      value={displayValue}
                      onChange={(e) => handlePolicyChange(r.agent_id, e.target.value)}
                      disabled={isSaving}
                      className="text-sm border rounded px-2 py-1 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {POLICY_OPTIONS.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                    {isSaving && (
                      <span className="text-xs text-gray-500 animate-pulse">Saving...</span>
                    )}
                  </div>
                );
              },
            },
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
            {
              key: 'actions',
              label: 'Actions',
              render: (r: any) => (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleDialogOpen(r.connection_id, 'accept')}
                    disabled={isMutating}
                    className="px-3 py-1 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {acceptMutation.isPending ? 'Accepting...' : 'Accept'}
                  </button>
                  <button
                    onClick={() => handleDialogOpen(r.connection_id, 'reject')}
                    disabled={isMutating}
                    className="px-3 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {rejectMutation.isPending ? 'Rejecting...' : 'Reject'}
                  </button>
                </div>
              ),
            },
          ]}
          data={data?.pending_requests ?? []}
        />
      </div>

      <ConfirmDialog
        open={dialogState !== null}
        title={dialogState?.action === 'accept' ? 'Accept Connection' : 'Reject Connection'}
        message={
          dialogState?.action === 'accept'
            ? 'Are you sure you want to accept this connection request?'
            : 'Are you sure you want to reject this connection request?'
        }
        variant={dialogState?.action === 'accept' ? 'default' : 'danger'}
        confirmLabel={dialogState?.action === 'accept' ? 'Accept' : 'Reject'}
        onConfirm={handleConfirm}
        onCancel={handleDialogCancel}
      />
    </div>
  );
}
