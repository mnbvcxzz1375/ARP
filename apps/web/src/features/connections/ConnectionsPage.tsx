import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import ConfirmDialog from '../../components/ConfirmDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import {
  ErrorBanner,
  PageTitle,
  PixelPanel,
  PixButton,
  PIXEL_SELECT_COMPACT,
} from './pixel-ui';
import { PIXEL_CHIP } from '../../lib/tokens';
import { useT } from '../../i18n';

interface DialogState {
  connectionId: string;
  action: 'accept' | 'reject';
}

const POLICY_OPTIONS = ['private', 'contacts_only', 'request_approval', 'public'];

/** Map a raw inbound-policy enum value to its locale label. */
const POLICY_LABEL_KEYS: Record<string, string> = {
  private: 'connections.policy.private',
  contacts_only: 'connections.policy.contactsOnly',
  request_approval: 'connections.policy.requestApproval',
  public: 'connections.policy.public',
};

export default function ConnectionsPage() {
  const t = useT();
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
      setError(detail || (err as any)?.message || t('connections.error.acceptFailed'));
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
      setError(detail || (err as any)?.message || t('connections.error.rejectFailed'));
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
      setError(detail || (err as any)?.message || t('connections.error.firewallFailed'));
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
  if (isQueryError) return <ErrorState message={t('connections.error.load')} />;

  return (
    <div>
      <PageTitle>{t('connections.page.title')}</PageTitle>

      {error && <ErrorBanner message={error} />}

      <PixelPanel title={t('connections.panel.agents')} className="mb-6">
        <DataTable
          className="border-0"
          columns={[
            { key: 'agent_number', label: t('connections.table.agentNumber') },
            {
              key: 'inbound_policy',
              label: t('connections.table.inboundPolicy'),
              render: (r: any) => {
                const isSaving = savingAgentIds.has(r.agent_id);
                const displayValue = r.agent_id in policyEdits ? policyEdits[r.agent_id] : r.inbound_policy;
                return (
                  <div className="flex items-center gap-2">
                    <select
                      value={displayValue}
                      onChange={(e) => handlePolicyChange(r.agent_id, e.target.value)}
                      disabled={isSaving}
                      className={PIXEL_SELECT_COMPACT}
                    >
                      {POLICY_OPTIONS.map((opt) => (
                        <option key={opt} value={opt}>
                          {t(POLICY_LABEL_KEYS[opt])}
                        </option>
                      ))}
                    </select>
                    {/* Saving is status feedback carried by the amber LED chip
                        itself. Static by design: the steps(1) blink primitive
                        is not in the CSS (see index.css note), so nothing
                        pulses. */}
                    {isSaving && (
                      <span
                        className={`inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none ${PIXEL_CHIP.warn}`}
                      >
                        {t('connections.status.saving')}
                      </span>
                    )}
                  </div>
                );
              },
            },
            { key: 'pending_requests', label: t('connections.table.pending') },
            { key: 'accepted_connections', label: t('connections.table.accepted') },
            { key: 'rejected_connections', label: t('connections.table.rejected') },
          ]}
          data={data?.agents ?? []}
        />
      </PixelPanel>

      <PixelPanel title={t('connections.panel.pendingRequests')}>
        <DataTable
          className="border-0"
          columns={[
            { key: 'connection_id', label: t('connections.table.connectionId'), render: (r: any) => r.connection_id?.slice(0, 8) },
            { key: 'agent_number', label: t('connections.table.agent') },
            { key: 'requester_agent', label: t('connections.table.requester'), render: (r: any) => r.requester_agent?.slice(0, 8) },
            {
              key: 'requested_policy',
              label: t('connections.table.requestedPolicy'),
              render: (r: any) =>
                POLICY_LABEL_KEYS[r.requested_policy]
                  ? t(POLICY_LABEL_KEYS[r.requested_policy])
                  : r.requested_policy || '-',
            },
            { key: 'created_at', label: t('connections.table.created') },
            {
              key: 'actions',
              label: t('connections.table.actions'),
              render: (r: any) => (
                <div className="flex gap-2">
                  <PixButton
                    variant="ok"
                    compact
                    onClick={() => handleDialogOpen(r.connection_id, 'accept')}
                    disabled={isMutating}
                  >
                    {acceptMutation.isPending ? t('connections.button.accepting') : t('connections.button.accept')}
                  </PixButton>
                  <PixButton
                    variant="danger"
                    compact
                    onClick={() => handleDialogOpen(r.connection_id, 'reject')}
                    disabled={isMutating}
                  >
                    {rejectMutation.isPending ? t('connections.button.rejecting') : t('connections.button.reject')}
                  </PixButton>
                </div>
              ),
            },
          ]}
          data={data?.pending_requests ?? []}
        />
      </PixelPanel>

      <ConfirmDialog
        open={dialogState !== null}
        title={dialogState?.action === 'accept' ? t('connections.dialog.acceptTitle') : t('connections.dialog.rejectTitle')}
        message={
          dialogState?.action === 'accept'
            ? t('connections.dialog.acceptMessage')
            : t('connections.dialog.rejectMessage')
        }
        variant={dialogState?.action === 'accept' ? 'default' : 'danger'}
        confirmLabel={dialogState?.action === 'accept' ? t('connections.dialog.acceptConfirm') : t('connections.dialog.rejectConfirm')}
        onConfirm={handleConfirm}
        onCancel={handleDialogCancel}
      />
    </div>
  );
}
