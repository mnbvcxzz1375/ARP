import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { useT, useFormat } from '../../i18n';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import ConfirmDialog from '../../components/ConfirmDialog';
import FormDialog from '../../components/FormDialog';
import StepUpDialog from '../../components/StepUpDialog';
import {
  ErrorBanner,
  NeutralChip,
  PageTitleRow,
  PixelField,
  PixelPanel,
  PixButton,
  YesNoChip,
  PIXEL_INPUT,
} from '../connections/pixel-ui';

/**
 * Row + form contract: /v1/dashboard/admin/dedicated-channels
 * (apps/api/app/routers/dedicated_channels.py, response model
 * DedicatedChannelResponse: id / channel_name / channel_type /
 * source_agent_id / target_agent_id / connection_config / encryption_config
 * / bandwidth_mbps / latency_target_ms / enabled / created_at / updated_at).
 * The response never carries a `status` or `last_health_check` field — the
 * enabled column and the health-check action cover those concerns.
 */
interface ChannelForm {
  channel_name: string;
  channel_type: string;
  source_agent_id: string;
  target_agent_id: string;
  connection_config: string;
  encryption_config: string;
  bandwidth_mbps: string;
  latency_target_ms: string;
}

const CHANNEL_TYPES = ['vpn', 'private_link', 'p2p', 'direct_connect'] as const;

/** Every write on this router is behind require_high_risk("super_admin:write"),
 * which returns 403 STEP_UP_REQUIRED unless the session has stepped up. */
function isStepUpNeeded(stepUpUntil: string | null | undefined): boolean {
  if (!stepUpUntil) return true;
  return new Date(stepUpUntil) <= new Date();
}

/** Server error detail extractor: backend messages are dynamic data and
 * are surfaced verbatim, falling back to a translated message. */
function extractDomainError(err: any, fallback: string): string {
  const data = err?.response?.data;
  if (data?.error?.message) return data.error.message;
  if (data?.error?.detail) return data.error.detail;
  if (data?.detail) return data.detail;
  if (data?.message) return data.message;
  return err?.message || fallback;
}

type PendingAction =
  | { type: 'create' }
  | { type: 'update'; id: string }
  | { type: 'delete'; id: string }
  | { type: 'health-check'; id: string }
  | null;

const emptyForm: ChannelForm = {
  channel_name: '',
  channel_type: 'vpn',
  source_agent_id: '',
  target_agent_id: '',
  connection_config: '{}',
  encryption_config: '',
  bandwidth_mbps: '',
  latency_target_ms: '',
};

export default function DedicatedChannelsPage() {
  const queryClient = useQueryClient();
  const t = useT();
  const { formatDateTime } = useFormat();
  const { data: auth } = useAuth();
  const [page, setPage] = useState(1);
  const limit = 20;

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ChannelForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleteId, setDeleteId] = useState<string | null>(null);

  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [showStepUp, setShowStepUp] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['dedicated-channels', page, limit],
    queryFn: () =>
      api
        .get('/v1/dashboard/admin/dedicated-channels', {
          params: { offset: (page - 1) * limit, limit },
        })
        .then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: object) => api.post('/v1/dashboard/admin/dedicated-channels', body),
    onSuccess: () => {
      setFormOpen(false);
      setFormError(null);
      setPendingAction(null);
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
    onError: (err: unknown) => {
      setFormError(extractDomainError(err, t('enterprise.channels.error.create')));
      setPendingAction(null);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: object }) =>
      api.patch(`/v1/dashboard/admin/dedicated-channels/${id}`, body),
    onSuccess: () => {
      setFormOpen(false);
      setEditingId(null);
      setFormError(null);
      setPendingAction(null);
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
    onError: (err: unknown) => {
      setFormError(extractDomainError(err, t('enterprise.channels.error.update')));
      setPendingAction(null);
    },
  });

  const healthCheckMutation = useMutation({
    mutationFn: (id: string) =>
      api.post(`/v1/dashboard/admin/dedicated-channels/${id}/health-check`),
    onSuccess: () => {
      setPendingAction(null);
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/dashboard/admin/dedicated-channels/${id}`),
    onSuccess: () => {
      setDeleteId(null);
      setPendingAction(null);
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
  });

  const isMutating = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  const handleOpenCreate = () => {
    if (isStepUpNeeded(auth?.step_up_until)) {
      setPendingAction({ type: 'create' });
      setShowStepUp(true);
      return;
    }
    openCreateForm();
  };

  const openCreateForm = () => {
    setEditingId(null);
    setForm(emptyForm);
    setFormError(null);
    setFormOpen(true);
  };

  const handleOpenEdit = (row: any) => {
    if (isStepUpNeeded(auth?.step_up_until)) {
      setPendingAction({ type: 'update', id: row.id });
      setShowStepUp(true);
      return;
    }
    openEditForm(row);
  };

  const openEditForm = (row: any) => {
    setEditingId(row.id);
    setForm({
      channel_name: row.channel_name || '',
      channel_type: (CHANNEL_TYPES as readonly string[]).includes(row.channel_type)
        ? row.channel_type
        : 'vpn',
      source_agent_id: row.source_agent_id || '',
      target_agent_id: row.target_agent_id || '',
      connection_config: row.connection_config ? JSON.stringify(row.connection_config, null, 2) : '{}',
      encryption_config: row.encryption_config ? JSON.stringify(row.encryption_config, null, 2) : '',
      bandwidth_mbps: row.bandwidth_mbps != null ? String(row.bandwidth_mbps) : '',
      latency_target_ms: row.latency_target_ms != null ? String(row.latency_target_ms) : '',
    });
    setFormError(null);
    setFormOpen(true);
  };

  const handleSubmit = () => {
    let connectionConfig: object;
    try {
      connectionConfig = JSON.parse(form.connection_config);
    } catch {
      setFormError(t('enterprise.channels.error.invalidJson'));
      return;
    }
    let encryptionConfig: object | undefined;
    if (form.encryption_config.trim()) {
      try {
        encryptionConfig = JSON.parse(form.encryption_config);
      } catch {
        setFormError(t('enterprise.channels.error.invalidJson'));
        return;
      }
    }
    const bandwidth = form.bandwidth_mbps.trim();
    const latency = form.latency_target_ms.trim();
    if (editingId) {
      // DedicatedChannelUpdate only carries the mutable fields; type and
      // agent endpoints are fixed after creation.
      const body: Record<string, unknown> = {
        channel_name: form.channel_name.trim(),
        connection_config: connectionConfig,
      };
      if (encryptionConfig !== undefined) body.encryption_config = encryptionConfig;
      if (bandwidth !== '') body.bandwidth_mbps = Number(bandwidth);
      if (latency !== '') body.latency_target_ms = Number(latency);
      updateMutation.mutate({ id: editingId, body });
      return;
    }
    const body: Record<string, unknown> = {
      channel_name: form.channel_name.trim(),
      channel_type: form.channel_type,
      source_agent_id: form.source_agent_id.trim(),
      target_agent_id: form.target_agent_id.trim(),
      connection_config: connectionConfig,
    };
    if (encryptionConfig !== undefined) body.encryption_config = encryptionConfig;
    if (bandwidth !== '') body.bandwidth_mbps = Number(bandwidth);
    if (latency !== '') body.latency_target_ms = Number(latency);
    createMutation.mutate(body);
  };

  // After a successful step-up, replay whichever write the operator
  // originally requested.
  function handleStepUpSuccess() {
    setShowStepUp(false);
    if (!pendingAction) return;
    const action = pendingAction;
    const channels = data?.channels ?? [];
    switch (action.type) {
      case 'create':
        openCreateForm();
        break;
      case 'update': {
        const row = channels.find((c: any) => c.id === action.id);
        if (row) openEditForm(row);
        break;
      }
      case 'delete':
        setDeleteId(action.id);
        break;
      case 'health-check':
        healthCheckMutation.mutate(action.id);
        break;
    }
    setPendingAction(null);
  }

  function handleHealthCheck(row: any) {
    if (isStepUpNeeded(auth?.step_up_until)) {
      setPendingAction({ type: 'health-check', id: row.id });
      setShowStepUp(true);
      return;
    }
    healthCheckMutation.mutate(row.id);
  }

  function handleRequestDelete(row: any) {
    if (isStepUpNeeded(auth?.step_up_until)) {
      setPendingAction({ type: 'delete', id: row.id });
      setShowStepUp(true);
      return;
    }
    setDeleteId(row.id);
  }

  function handleStepUpCancel() {
    setShowStepUp(false);
    setPendingAction(null);
  }

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('enterprise.channels.error.load')} />;

  return (
    <div>
      <PageTitleRow
        title={t('enterprise.channels.title')}
        actions={
          <PixButton onClick={handleOpenCreate}>{t('enterprise.channels.action.add')}</PixButton>
        }
      />

      <PixelPanel>
        <DataTable
          className="border-0"
          columns={[
            { key: 'channel_name', label: t('enterprise.table.name'), render: (r: any) => r.channel_name || '-' },
            {
              key: 'channel_type',
              label: t('enterprise.table.type'),
              render: (r: any) => <NeutralChip>{r.channel_type || '-'}</NeutralChip>,
            },
            {
              key: 'source_agent_id',
              label: t('enterprise.channels.table.sourceAgent'),
              render: (r: any) =>
                r.source_agent_id ? r.source_agent_id.slice(0, 8) + '...' : '-',
            },
            {
              key: 'target_agent_id',
              label: t('enterprise.channels.table.targetAgent'),
              render: (r: any) =>
                r.target_agent_id ? r.target_agent_id.slice(0, 8) + '...' : '-',
            },
            {
              key: 'enabled',
              label: t('enterprise.table.enabled'),
              render: (r: any) => <YesNoChip value={!!r.enabled} />,
            },
            {
              key: 'created_at',
              label: t('enterprise.table.created'),
              render: (r: any) =>
                r.created_at ? formatDateTime(r.created_at) : '-',
            },
            {
              key: 'actions',
              label: '',
              render: (r: any) => (
                <div className="flex gap-2">
                  <PixButton variant="ghost" compact onClick={() => handleOpenEdit(r)}>
                    {t('enterprise.action.edit')}
                  </PixButton>
                  <PixButton
                    variant="ok"
                    compact
                    onClick={() => handleHealthCheck(r)}
                    disabled={healthCheckMutation.isPending}
                  >
                    {t('enterprise.action.healthCheck')}
                  </PixButton>
                  <PixButton variant="danger" compact onClick={() => handleRequestDelete(r)}>
                    {t('enterprise.action.delete')}
                  </PixButton>
                </div>
              ),
            },
          ]}
          data={data?.channels ?? []}
        />
        <Pagination
          offset={(page - 1) * limit}
          limit={limit}
          total={data?.total ?? 0}
          onPageChange={(offset) => setPage(Math.floor(offset / limit) + 1)}
        />
      </PixelPanel>

      <FormDialog
        open={formOpen}
        title={editingId ? t('enterprise.channels.form.editTitle') : t('enterprise.channels.form.createTitle')}
        onClose={() => {
          setFormOpen(false);
          setEditingId(null);
          setFormError(null);
        }}
        onSubmit={handleSubmit}
        loading={isMutating}
      >
        {formError && <ErrorBanner message={formError} className="mb-0" />}
        <PixelField label={t('enterprise.channels.form.name')} htmlFor="dc-name">
          <input
            id="dc-name"
            type="text"
            value={form.channel_name}
            onChange={(e) => setForm({ ...form, channel_name: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.channels.form.sourceAgentId')} htmlFor="dc-source-agent">
          <input
            id="dc-source-agent"
            type="text"
            value={form.source_agent_id}
            onChange={(e) => setForm({ ...form, source_agent_id: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.channels.form.targetAgentId')} htmlFor="dc-target-agent">
          <input
            id="dc-target-agent"
            type="text"
            value={form.target_agent_id}
            onChange={(e) => setForm({ ...form, target_agent_id: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.channels.form.channelType')} htmlFor="dc-channel-type">
          <select
            id="dc-channel-type"
            value={form.channel_type}
            onChange={(e) => setForm({ ...form, channel_type: e.target.value })}
            className={PIXEL_INPUT}
          >
            {CHANNEL_TYPES.map((ct) => (
              <option key={ct} value={ct}>
                {ct}
              </option>
            ))}
          </select>
        </PixelField>
        <PixelField label={t('enterprise.channels.form.connectionConfig')} htmlFor="dc-conn-config">
          <textarea
            id="dc-conn-config"
            value={form.connection_config}
            onChange={(e) => setForm({ ...form, connection_config: e.target.value })}
            rows={4}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.channels.form.encryptionConfig')} htmlFor="dc-enc-config">
          <textarea
            id="dc-enc-config"
            value={form.encryption_config}
            onChange={(e) => setForm({ ...form, encryption_config: e.target.value })}
            rows={3}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.channels.form.bandwidth')} htmlFor="dc-bandwidth">
          <input
            id="dc-bandwidth"
            type="number"
            min="0"
            value={form.bandwidth_mbps}
            onChange={(e) => setForm({ ...form, bandwidth_mbps: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.channels.form.latencyTarget')} htmlFor="dc-latency">
          <input
            id="dc-latency"
            type="number"
            min="0"
            value={form.latency_target_ms}
            onChange={(e) => setForm({ ...form, latency_target_ms: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
      </FormDialog>

      <ConfirmDialog
        open={deleteId !== null}
        title={t('enterprise.channels.confirm.deleteTitle')}
        message={t('enterprise.channels.confirm.deleteMessage')}
        variant="danger"
        confirmLabel={t('enterprise.action.delete')}
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        onCancel={() => setDeleteId(null)}
      />

      <StepUpDialog
        open={showStepUp}
        onSuccess={handleStepUpSuccess}
        onCancel={handleStepUpCancel}
      />
    </div>
  );
}
