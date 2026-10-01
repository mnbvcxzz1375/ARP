import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { useT } from '../../i18n';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import RoleBadge from '../../components/RoleBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import ConfirmDialog from '../../components/ConfirmDialog';
import StepUpDialog from '../../components/StepUpDialog';
import {
  PageHeader,
  PixelActionButton,
  ActionErrorBanner,
  DetailLink,
} from './PixelKit';
import { shortUserId } from '../../lib/utils';

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
  const t = useT();
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
      setActionError(err?.response?.data?.detail || t('admin.error.updateUser'));
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
      setActionError(err?.response?.data?.detail || t('admin.error.revokeKeys'));
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
  if (isError) return <ErrorState message={t('admin.error.loadUsers')} />;

  return (
    <div>
      <PageHeader title={t('admin.title.users')} />
      {actionError && <ActionErrorBanner message={actionError} />}
      {/* DataTable carries its own 2px pixel border + surface; the wrapper
          only adds the hard pixel-step shadow. */}
      <div className="shadow-pixel-sm">
        <DataTable
          columns={[
            {
              key: 'username',
              label: t('admin.users.table.username'),
              // Usernames are non-unique display labels; the short user_id
              // suffix keeps same-named users distinguishable.
              render: (r: any) => (
                <span>
                  {r.username}{' '}
                  <span className="font-mono text-pixel-muted">· {shortUserId(r.user_id)}</span>
                </span>
              ),
            },
            {
              key: 'details',
              label: '',
              render: (r: any) => (
                <DetailLink to={`/admin/users/${r.user_id}`}>{t('admin.action.view')}</DetailLink>
              ),
            },
            { key: 'role', label: t('admin.users.table.role'), render: (r: any) => <RoleBadge role={r.role} /> },
            { key: 'is_disabled', label: t('admin.users.table.disabled'), render: (r: any) => r.is_disabled ? t('admin.value.yes') : t('admin.value.no') },
            { key: 'agents_count', label: t('admin.users.table.agents') },
            { key: 'active_api_keys_count', label: t('admin.users.table.apiKeys') },
            { key: 'tasks_24h', label: t('admin.agents.table.tasks24h') },
            { key: 'failed_tasks_24h', label: t('admin.users.table.failed') },
            { key: 'created_at', label: t('admin.table.created') },
            {
              key: 'actions',
              label: t('admin.table.actions'),
              render: (r: any) => (
                <div className="flex flex-wrap gap-2">
                  {isSuperAdmin ? (
                    <>
                      <PixelActionButton
                        onClick={() => setPendingAction({
                          type: r.is_disabled ? 'enable' : 'disable',
                          userId: r.user_id,
                          username: r.username,
                        })}
                        disabled={disableMutation.isPending || revokeMutation.isPending}
                        variant={r.is_disabled ? 'accent' : 'danger'}
                      >
                        {r.is_disabled ? t('admin.action.enable') : t('admin.action.disable')}
                      </PixelActionButton>
                      <PixelActionButton
                        onClick={() => setPendingAction({
                          type: 'force_revoke',
                          userId: r.user_id,
                          username: r.username,
                        })}
                        disabled={disableMutation.isPending || revokeMutation.isPending}
                        variant="danger"
                      >
                        {t('admin.action.revokeKeys')}
                      </PixelActionButton>
                    </>
                  ) : (
                    <span className="text-base text-pixel-muted">{t('admin.hint.superAdminRequired')}</span>
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
            ? t('admin.users.confirm.revokeTitle')
            : pendingAction?.type === 'disable'
            ? t('admin.users.confirm.disableTitle')
            : t('admin.users.confirm.enableTitle')
        }
        message={
          pendingAction?.type === 'force_revoke'
            ? t('admin.users.confirm.revokeMessage', { name: pendingAction?.username ?? '' })
            : pendingAction?.type === 'disable'
            ? t('admin.users.confirm.disableMessage', { name: pendingAction?.username ?? '' })
            : t('admin.users.confirm.enableMessage', { name: pendingAction?.username ?? '' })
        }
        variant={pendingAction?.type === 'enable' ? 'default' : 'danger'}
        confirmLabel={
          pendingAction?.type === 'force_revoke'
            ? t('admin.action.revokeKeys')
            : pendingAction?.type === 'disable'
            ? t('admin.action.disable')
            : t('admin.action.enable')
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
