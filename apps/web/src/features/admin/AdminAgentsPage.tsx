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
  const t = useT();
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
      setActionError(err?.response?.data?.detail || t('admin.error.updateAgent'));
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
  if (isError) return <ErrorState message={t('admin.error.loadAgents')} />;

  return (
    <div>
      <PageHeader title={t('admin.title.agents')} />
      {actionError && <ActionErrorBanner message={actionError} />}
      {/* DataTable carries its own 2px pixel border + surface; the wrapper
          only adds the hard pixel-step shadow. */}
      <div className="shadow-pixel-sm">
        <DataTable
          columns={[
            { key: 'name', label: t('admin.agents.table.name') },
            { key: 'agent_number', label: t('admin.agents.table.agentNumber') },
            {
              key: 'details',
              label: '',
              render: (r: any) => (
                <DetailLink to={`/admin/agents/${r.agent_id}`}>{t('admin.action.view')}</DetailLink>
              ),
            },
            { key: 'owner_username', label: t('admin.table.owner') },
            { key: 'status', label: t('admin.table.status'), render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'runtime', label: t('admin.agents.table.runtime') },
            { key: 'inbound_policy', label: t('admin.agents.table.policy') },
            { key: 'tasks_24h', label: t('admin.agents.table.tasks24h') },
            { key: 'failed_tasks_24h', label: t('admin.agents.table.failed') },
            {
              key: 'actions',
              label: t('admin.table.actions'),
              render: (r: any) => (
                <div className="flex gap-2">
                  {isSuperAdmin ? (
                    <PixelActionButton
                      onClick={() => setPendingAction({
                        type: r.status === 'offline' ? 'enable' : 'disable',
                        agentId: r.agent_id,
                        agentName: r.name || r.agent_number,
                      })}
                      disabled={toggleMutation.isPending}
                      variant={r.status === 'offline' ? 'accent' : 'danger'}
                    >
                      {r.status === 'offline' ? t('admin.action.enable') : t('admin.action.disable')}
                    </PixelActionButton>
                  ) : (
                    <span className="text-base text-pixel-muted">{t('admin.hint.superAdminRequired')}</span>
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
        title={pendingAction?.type === 'disable' ? t('admin.agents.confirm.disableTitle') : t('admin.agents.confirm.enableTitle')}
        message={
          pendingAction?.type === 'disable'
            ? t('admin.agents.confirm.disableMessage', { name: pendingAction?.agentName ?? '' })
            : t('admin.agents.confirm.enableMessage', { name: pendingAction?.agentName ?? '' })
        }
        variant={pendingAction?.type === 'disable' ? 'danger' : 'default'}
        confirmLabel={pendingAction?.type === 'disable' ? t('admin.action.disable') : t('admin.action.enable')}
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
