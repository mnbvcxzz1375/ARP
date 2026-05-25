import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import ConfirmDialog from '../../components/ConfirmDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';

interface DialogState {
  requestId: string;
  action: 'approve' | 'reject';
}

interface ProvisionedResult {
  request_id: string;
  status: string;
  reviewed_by: string;
  user_id: string;
  api_key: string;
  scope_id?: string;
}

export default function AccessRequestsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [dialogState, setDialogState] = useState<DialogState | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectError, setRejectError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [provisionedResult, setProvisionedResult] = useState<ProvisionedResult | null>(null);
  const [copied, setCopied] = useState(false);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/access-requests', page, limit, statusFilter],
    queryFn: () =>
      api
        .get('/v1/dashboard/admin/access-requests', {
          params: { offset: (page - 1) * limit, limit, status_filter: statusFilter || undefined },
        })
        .then((r) => r.data),
  });

  const approveMutation = useMutation({
    mutationFn: (requestId: string) =>
      api.post(`/v1/dashboard/admin/access-requests/${requestId}/approve`),
    onSuccess: (response) => {
      setDialogState(null);
      setError(null);
      setProvisionedResult(response.data);
      setCopied(false);
      queryClient.invalidateQueries({ queryKey: ['admin/access-requests'] });
    },
    onError: (err: unknown) => {
      setDialogState(null);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || 'Failed to approve request');
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ requestId, reason }: { requestId: string; reason: string }) =>
      api.post(`/v1/dashboard/admin/access-requests/${requestId}/reject`, {
        review_notes: reason,
      }),
    onSuccess: () => {
      setDialogState(null);
      setRejectReason('');
      setRejectError(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['admin/access-requests'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.error?.message;
      setError(detail || (err as any)?.message || 'Failed to reject request');
      // Keep dialog open on error so user can fix
    },
  });

  const isMutating = approveMutation.isPending || rejectMutation.isPending;

  const handleDialogOpen = (requestId: string, action: 'approve' | 'reject') => {
    setError(null);
    setRejectReason('');
    setRejectError(null);
    setDialogState({ requestId, action });
  };

  const handleDialogCancel = () => {
    setDialogState(null);
    setRejectReason('');
    setRejectError(null);
    setError(null);
  };

  const handleConfirm = () => {
    if (!dialogState || isMutating) return;
    if (dialogState.action === 'approve') {
      approveMutation.mutate(dialogState.requestId);
    } else {
      if (!rejectReason.trim()) {
        setRejectError('Rejection reason is required.');
        return;
      }
      rejectMutation.mutate({ requestId: dialogState.requestId, reason: rejectReason });
    }
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load access requests" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Access Requests</h2>

      {provisionedResult && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-md">
          <h3 className="text-sm font-semibold text-green-800 mb-2">
            Access Request Approved -- User Provisioned
          </h3>
          <div className="space-y-2 text-sm">
            <div>
              <span className="text-gray-500">User ID:</span>{' '}
              <span className="font-mono text-xs">{provisionedResult.user_id}</span>
            </div>
            {provisionedResult.scope_id && (
              <div>
                <span className="text-gray-500">Scope ID:</span>{' '}
                <span className="font-mono text-xs">{provisionedResult.scope_id}</span>
              </div>
            )}
            <div>
              <span className="text-gray-500">API Key (shown once):</span>{' '}
              <code className="font-mono text-xs bg-white px-2 py-0.5 border rounded select-all">
                {provisionedResult.api_key}
              </code>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(provisionedResult.api_key);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                className="ml-2 text-xs text-blue-600 hover:text-blue-800 underline"
              >
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <p className="text-xs text-green-700 mt-1">
              Provide this API key to the applicant. It will not be shown again.
            </p>
          </div>
          <button
            onClick={() => setProvisionedResult(null)}
            className="mt-2 text-xs text-gray-500 hover:text-gray-700 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded">
          {error}
        </div>
      )}

      <div className="mb-4 flex gap-2">
        {['all', 'pending', 'approved', 'rejected', 'expired'].map((s) => (
          <button
            key={s}
            onClick={() => {
              setStatusFilter(s === 'all' ? undefined : s);
              setPage(1);
            }}
            className={`px-3 py-1.5 text-xs font-medium rounded border ${
              (s === 'all' && !statusFilter) || statusFilter === s
                ? 'bg-gray-900 text-white border-gray-900'
                : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
            }`}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        {data?.access_requests?.length === 0 ? (
          <EmptyState message="No access requests found" />
        ) : (
          <DataTable
            columns={[
              { key: 'request_id', label: 'ID', render: (r: any) => r.request_id?.slice(0, 8) },
              { key: 'applicant_name', label: 'Name' },
              { key: 'applicant_email', label: 'Email' },
              { key: 'organization', label: 'Org', render: (r: any) => r.organization || '-' },
              { key: 'requested_mode', label: 'Mode', render: (r: any) => (
                <span className="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                  {r.requested_mode}
                </span>
              )},
              { key: 'status', label: 'Status', render: (r: any) => <StatusBadge status={r.status} /> },
              { key: 'created_at', label: 'Submitted', render: (r: any) => new Date(r.created_at).toLocaleDateString() },
              {
                key: 'actions',
                label: '',
                render: (r: any) =>
                  r.status === 'pending' ? (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleDialogOpen(r.request_id, 'approve')}
                        disabled={isMutating}
                        className="px-3 py-1 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleDialogOpen(r.request_id, 'reject')}
                        disabled={isMutating}
                        className="px-3 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  ) : (
                    <span className="text-xs text-gray-400">
                      {r.reviewed_at ? new Date(r.reviewed_at).toLocaleDateString() : ''}
                    </span>
                  ),
              },
            ]}
            data={data?.access_requests ?? []}
          />
        )}
        <Pagination
          offset={(page - 1) * limit}
          limit={limit}
          total={data?.total ?? 0}
          onPageChange={(offset) => setPage(Math.floor(offset / limit) + 1)}
        />
      </div>

      <ConfirmDialog
        open={dialogState !== null}
        title={dialogState?.action === 'approve' ? 'Approve Access Request' : 'Reject Access Request'}
        message={
          dialogState?.action === 'approve'
            ? 'Are you sure you want to approve this access request? The applicant will be granted access after approval.'
            : 'Are you sure you want to reject this access request? The applicant will need to reapply.'
        }
        variant={dialogState?.action === 'approve' ? 'default' : 'danger'}
        confirmLabel={dialogState?.action === 'approve' ? 'Approve' : 'Reject'}
        onConfirm={handleConfirm}
        onCancel={handleDialogCancel}
      >
        {dialogState?.action === 'reject' && (
          <div className="mt-3">
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Rejection Reason <span className="text-red-500">*</span>
            </label>
            <textarea
              value={rejectReason}
              onChange={(e) => {
                setRejectReason(e.target.value);
                if (rejectError) setRejectError(null);
              }}
              rows={2}
              className={`w-full px-3 py-2 border rounded text-sm ${rejectError ? 'border-red-400' : ''}`}
              placeholder="Reason for rejection (required)"
            />
            {rejectError && (
              <p className="mt-1 text-xs text-red-600">{rejectError}</p>
            )}
          </div>
        )}
      </ConfirmDialog>
    </div>
  );
}