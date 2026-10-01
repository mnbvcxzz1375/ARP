import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { useT } from '../../i18n';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
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

type PendingTaskAction = {
  type: 'cancel';
  taskId: string;
  isRunning: boolean;
} | {
  type: 'expire';
  taskId: string;
} | null;

function isStepUpNeeded(stepUpUntil: string | null | undefined): boolean {
  if (!stepUpUntil) return true;
  return new Date(stepUpUntil) <= new Date();
}

export default function AdminTasksPage() {
  const [page, setPage] = useState(1);
  const limit = 20;
  const queryClient = useQueryClient();
  const { data: auth } = useAuth();
  const t = useT();
  const isSuperAdmin = auth?.role === 'super_admin';
  const isAdmin = auth?.role === 'admin' || isSuperAdmin;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/tasks', page, limit],
    queryFn: () => api.get('/v1/dashboard/admin/tasks', { params: { offset: (page - 1) * limit, limit } }).then((r) => r.data),
  });

  const [pendingAction, setPendingAction] = useState<PendingTaskAction>(null);
  const [showStepUp, setShowStepUp] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const cancelMutation = useMutation({
    mutationFn: (taskId: string) =>
      api.post(`/v1/dashboard/admin/tasks/${taskId}/cancel`),
    onSuccess: () => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['admin/tasks'] });
      queryClient.invalidateQueries({ queryKey: ['admin/overview'] });
    },
    onError: (err: any) => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(err?.response?.data?.detail || t('admin.error.cancelTask'));
    },
  });

  const expireMutation = useMutation({
    mutationFn: (taskId: string) =>
      api.post(`/v1/dashboard/admin/tasks/${taskId}/expire`),
    onSuccess: () => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['admin/tasks'] });
      queryClient.invalidateQueries({ queryKey: ['admin/overview'] });
    },
    onError: (err: any) => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(err?.response?.data?.detail || t('admin.error.expireTask'));
    },
  });

  const handleConfirmAction = () => {
    if (!pendingAction) return;
    setActionError(null);
    if (pendingAction.type === 'expire') {
      // Expire always requires step-up
      setShowStepUp(true);
    } else if (pendingAction.isRunning && isStepUpNeeded(auth?.step_up_until)) {
      setShowStepUp(true);
    } else {
      cancelMutation.mutate(pendingAction.taskId);
    }
  };

  const handleStepUpSuccess = () => {
    setShowStepUp(false);
    if (!pendingAction) return;
    if (pendingAction.type === 'expire') {
      expireMutation.mutate(pendingAction.taskId);
    } else {
      cancelMutation.mutate(pendingAction.taskId);
    }
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('admin.error.loadTasks')} />;

  return (
    <div>
      <PageHeader title={t('admin.title.tasks')} />
      {actionError && <ActionErrorBanner message={actionError} />}
      {/* DataTable carries its own 2px pixel border + surface; the wrapper
          only adds the hard pixel-step shadow. */}
      <div className="shadow-pixel-sm">
        <DataTable
          columns={[
            { key: 'task_id', label: t('admin.tasks.table.id'), render: (r: any) => r.task_id?.slice(0, 8) },
            {
              key: 'details',
              label: '',
              render: (r: any) => (
                <DetailLink to={`/admin/tasks/${r.task_id}`}>{t('admin.action.view')}</DetailLink>
              ),
            },
            { key: 'status', label: t('admin.table.status'), render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'owner_username', label: t('admin.table.owner') },
            { key: 'sender_agent', label: t('admin.tasks.table.sender'), render: (r: any) => r.sender_agent?.slice(0, 8) },
            { key: 'target_agent', label: t('admin.tasks.table.target'), render: (r: any) => r.target_agent?.slice(0, 8) },
            { key: 'created_at', label: t('admin.table.created') },
            {
              key: 'actions',
              label: t('admin.table.actions'),
              render: (r: any) => {
                const taskStatus = r.status;
                const isTerminal = ['completed', 'failed', 'cancelled', 'expired'].includes(taskStatus);
                if (taskStatus === 'pending') {
                  if (!isAdmin) {
                    return <span className="text-base text-pixel-muted">{t('admin.hint.adminRequired')}</span>;
                  }
                  return (
                    <div className="flex flex-wrap gap-2">
                      <PixelActionButton
                        onClick={() => setPendingAction({ type: 'cancel', taskId: r.task_id, isRunning: false })}
                        disabled={cancelMutation.isPending}
                        variant="danger"
                      >
                        {t('admin.action.cancel')}
                      </PixelActionButton>
                      {isSuperAdmin && (
                        <PixelActionButton
                          onClick={() => setPendingAction({ type: 'expire', taskId: r.task_id })}
                          disabled={expireMutation.isPending}
                          variant="accent"
                        >
                          {t('admin.action.expire')}
                        </PixelActionButton>
                      )}
                    </div>
                  );
                }
                if (taskStatus === 'running') {
                  if (!isSuperAdmin) {
                    return <span className="text-base text-pixel-muted">{t('admin.hint.superAdminRequired')}</span>;
                  }
                  return (
                    <div className="flex flex-wrap gap-2">
                      <PixelActionButton
                        onClick={() => setPendingAction({ type: 'cancel', taskId: r.task_id, isRunning: true })}
                        disabled={cancelMutation.isPending}
                        variant="danger"
                      >
                        {t('admin.action.cancel')}
                      </PixelActionButton>
                      <PixelActionButton
                        onClick={() => setPendingAction({ type: 'expire', taskId: r.task_id })}
                        disabled={expireMutation.isPending}
                        variant="accent"
                      >
                        {t('admin.action.expire')}
                      </PixelActionButton>
                    </div>
                  );
                }
                if (!isTerminal && isSuperAdmin) {
                  return (
                    <PixelActionButton
                      onClick={() => setPendingAction({ type: 'expire', taskId: r.task_id })}
                      disabled={expireMutation.isPending}
                      variant="accent"
                    >
                      {t('admin.action.expire')}
                    </PixelActionButton>
                  );
                }
                return <span className="text-base text-pixel-muted">-</span>;
              },
            },
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

      <ConfirmDialog
        open={pendingAction !== null && !showStepUp}
        title={
          pendingAction?.type === 'expire' ? t('admin.tasks.confirm.expireTitle') : t('admin.tasks.confirm.cancelTitle')
        }
        message={
          pendingAction?.type === 'expire'
            ? t('admin.tasks.confirm.expireMessage', { id: pendingAction?.taskId?.slice(0, 8) ?? '' })
            : pendingAction?.isRunning
              ? t('admin.tasks.confirm.cancelRunningMessage', { id: pendingAction?.taskId?.slice(0, 8) ?? '' })
              : t('admin.tasks.confirm.cancelPendingMessage', { id: pendingAction?.taskId?.slice(0, 8) ?? '' })
        }
        variant="danger"
        confirmLabel={
          pendingAction?.type === 'expire' ? t('admin.tasks.confirm.expireLabel') : t('admin.tasks.confirm.cancelLabel')
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
