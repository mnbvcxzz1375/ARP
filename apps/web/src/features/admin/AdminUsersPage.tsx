import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import RoleBadge from '../../components/RoleBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import ConfirmDialog from '../../components/ConfirmDialog';
import StepUpDialog from '../../components/StepUpDialog';

type PendingUserAction = {
  type: 'disable' | 'enable' | 'force_revoke';
  userId: string;
  username: string;
} | null;

function isStepUpNeeded(stepUpUntil: string | null | undefined): boolean {
  if (!stepUpUntil) return true;
  return new Date(stepUpUntil) <= new Date();
}

export default function AdminUsersPage() {
  const [page, setPage] = useState(1);
  const limit = 20;
  const queryClient = useQueryClient();
  const { data: auth } = useAuth();
  const isSuperAdmin = auth?.role === 'super_admin';

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/users', page, limit],
    queryFn: () => api.get('/v1/dashboard/admin/users', { params: { offset: (page - 1) * limit, limit } }).then((r) => r.data),
    refetchInterval: 30000,
  });

  const [pendingAction, setPendingAction] = useState<PendingUserAction>(null);
  const [showStepUp, setShowStepUp] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const disableMutation = useMutation({
    mutationFn: ({ userId, isDisabled }: { userId: string; isDisabled: boolean }) =>
      api.post(`/v1/dashboard/admin/users/${userId}/disable`, { is_disabled: isDisabled }),
    onSuccess: () => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['admin/users'] });
      queryClient.invalidateQueries({ queryKey: ['admin/overview'] });
    },
    onError: (err: any) => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(err?.response?.data?.detail || 'Failed to update user');
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (userId: string) =>
      api.post(`/v1/dashboard/admin/users/${userId}/force-revoke-keys`),
    onSuccess: () => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['admin/users'] });
      queryClient.invalidateQueries({ queryKey: ['admin/overview'] });
      queryClient.invalidateQueries({ queryKey: ['auth/me'] });
    },
    onError: (err: any) => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(err?.response?.data?.detail || 'Failed to revoke keys');
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

  const executeAction = (action: NonNullable<PendingUserAction>) => {
    switch (action.type) {
      case 'disable':
        disableMutation.mutate({ userId: action.userId, isDisabled: true });
        break;
      case 'enable':
        disableMutation.mutate({ userId: action.userId, isDisabled: false });
        break;
      case 'force_revoke':
        revokeMutation.mutate(action.userId);
        break;
    }
  };

  const handleStepUpSuccess = () => {
    setShowStepUp(false);
    if (pendingAction) {
      executeAction(pendingAction);
    }
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load users" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Users</h2>
      {actionError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700" data-testid="action-error">
          {actionError}
        </div>
      )}
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'username', label: 'Username' },
            {
              key: 'details',
              label: '',
              render: (r: any) => (
                <Link to={`/admin/users/${r.user_id}`} className="text-blue-600 hover:underline text-xs font-medium">
                  View
                </Link>
              ),
            },
            { key: 'role', label: 'Role', render: (r: any) => <RoleBadge role={r.role} /> },
            { key: 'is_disabled', label: 'Disabled', render: (r: any) => r.is_disabled ? 'Yes' : 'No' },
            { key: 'agents_count', label: 'Agents' },
            { key: 'active_api_keys_count', label: 'API Keys' },
            { key: 'tasks_24h', label: 'Tasks (24h)' },
            { key: 'failed_tasks_24h', label: 'Failed' },
            { key: 'created_at', label: 'Created' },
            {
              key: 'actions',
              label: 'Actions',
              render: (r: any) => (
                <div className="flex gap-2">
                  {isSuperAdmin ? (
                    <>
                      <button
                        onClick={() => setPendingAction({
                          type: r.is_disabled ? 'enable' : 'disable',
                          userId: r.user_id,
                          username: r.username,
                        })}
                        disabled={disableMutation.isPending || revokeMutation.isPending}
                        className={`px-2 py-1 text-xs font-medium rounded ${
                          r.is_disabled
                            ? 'text-green-700 bg-green-50 border border-green-200 hover:bg-green-100'
                            : 'text-yellow-700 bg-yellow-50 border border-yellow-200 hover:bg-yellow-100'
                        } disabled:opacity-50`}
                      >
                        {r.is_disabled ? 'Enable' : 'Disable'}
                      </button>
                      <button
                        onClick={() => setPendingAction({
                          type: 'force_revoke',
                          userId: r.user_id,
                          username: r.username,
                        })}
                        disabled={disableMutation.isPending || revokeMutation.isPending}
                        className="px-2 py-1 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded hover:bg-red-100 disabled:opacity-50"
                      >
                        Revoke Keys
                      </button>
                    </>
                  ) : (
                    <span className="text-xs text-gray-400">Super admin required</span>
                  )}
                </div>
              ),
            },
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

      <ConfirmDialog
        open={pendingAction !== null && !showStepUp}
        title={
          pendingAction?.type === 'force_revoke'
            ? 'Force Revoke API Keys'
            : pendingAction?.type === 'disable'
            ? 'Disable User'
            : 'Enable User'
        }
        message={
          pendingAction?.type === 'force_revoke'
            ? `Revoke all API keys for user "${pendingAction?.username}"? This will invalidate all their API keys immediately.`
            : pendingAction?.type === 'disable'
            ? `Disable user "${pendingAction?.username}"? They will be unable to log in or use the platform.`
            : `Enable user "${pendingAction?.username}"? They will regain access to the platform.`
        }
        variant={pendingAction?.type === 'enable' ? 'default' : 'danger'}
        confirmLabel={
          pendingAction?.type === 'force_revoke'
            ? 'Revoke Keys'
            : pendingAction?.type === 'disable'
            ? 'Disable'
            : 'Enable'
        }
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
