import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import RiskBadge from '../../components/RiskBadge';
import ConfirmDialog from '../../components/ConfirmDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

interface DialogState {
  approvalId: string;
  action: 'accept' | 'reject';
}

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  const [dialogState, setDialogState] = useState<DialogState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, isError: isQueryError } = useQuery({
    queryKey: ['approvals'],
    queryFn: () => api.get('/v1/dashboard/approvals').then((r) => r.data),
  });

  const acceptMutation = useMutation({
    mutationFn: (approvalId: string) =>
      api.post(`/v1/dashboard/approvals/${approvalId}/accept`),
    onSuccess: () => {
      setDialogState(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard/overview'] });
    },
    onError: (err: unknown) => {
      setDialogState(null);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || 'Failed to accept approval');
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (approvalId: string) =>
      api.post(`/v1/dashboard/approvals/${approvalId}/reject`),
    onSuccess: () => {
      setDialogState(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard/overview'] });
    },
    onError: (err: unknown) => {
      setDialogState(null);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || 'Failed to reject approval');
    },
  });

  const isMutating = acceptMutation.isPending || rejectMutation.isPending;

  const handleDialogOpen = (approvalId: string, action: 'accept' | 'reject') => {
    setError(null);
    setDialogState({ approvalId, action });
  };

  const handleDialogCancel = () => {
    setDialogState(null);
    setError(null);
  };

  const handleConfirm = () => {
    if (!dialogState || isMutating) return;
    if (dialogState.action === 'accept') {
      acceptMutation.mutate(dialogState.approvalId);
    } else {
      rejectMutation.mutate(dialogState.approvalId);
    }
  };

  if (isLoading) return <LoadingState />;
  if (isQueryError) return <ErrorState message="Failed to load approvals" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Approvals</h2>

      {error && (
        <div className="mb-4 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'approval_id', label: 'ID', render: (r: any) => r.approval_id?.slice(0, 8) },
            { key: 'type', label: 'Type' },
            { key: 'status', label: 'Status', render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'risk_level', label: 'Risk', render: (r: any) => <RiskBadge level={r.risk_level} /> },
            { key: 'action_kind', label: 'Action' },
            { key: 'created_at', label: 'Created' },
            {
              key: 'actions',
              label: 'Actions',
              render: (r: any) => {
                if (r.status !== 'pending') return null;
                const isAcceptPending = acceptMutation.isPending;
                const isRejectPending = rejectMutation.isPending;
                return (
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDialogOpen(r.approval_id, 'accept')}
                      disabled={isMutating}
                      className="px-3 py-1 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isAcceptPending ? 'Accepting...' : 'Accept'}
                    </button>
                    <button
                      onClick={() => handleDialogOpen(r.approval_id, 'reject')}
                      disabled={isMutating}
                      className="px-3 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isRejectPending ? 'Rejecting...' : 'Reject'}
                    </button>
                  </div>
                );
              },
            },
          ]}
          data={data?.approvals ?? []}
        />
      </div>

      <ConfirmDialog
        open={dialogState !== null}
        title={dialogState?.action === 'accept' ? 'Accept Approval' : 'Reject Approval'}
        message={
          dialogState?.action === 'accept'
            ? 'Are you sure you want to accept this approval request?'
            : 'Are you sure you want to reject this approval request?'
        }
        variant={dialogState?.action === 'accept' ? 'default' : 'danger'}
        confirmLabel={dialogState?.action === 'accept' ? 'Accept' : 'Reject'}
        onConfirm={handleConfirm}
        onCancel={handleDialogCancel}
      />
    </div>
  );
}
