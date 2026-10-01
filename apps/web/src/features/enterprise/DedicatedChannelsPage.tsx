import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { useT, useFormat } from '../../i18n';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import ConfirmDialog from '../../components/ConfirmDialog';
import FormDialog from '../../components/FormDialog';
import {
  ErrorBanner,
  NeutralChip,
  PageTitleRow,
  PixelField,
  PixelPanel,
  PixButton,
  PIXEL_INPUT,
} from '../connections/pixel-ui';

interface ChannelForm {
  name: string;
  target_agent_id: string;
  channel_type: string;
  config: string;
}

const emptyForm: ChannelForm = {
  name: '',
  target_agent_id: '',
  channel_type: 'kafka',
  config: '{}',
};

export default function DedicatedChannelsPage() {
  const queryClient = useQueryClient();
  const t = useT();
  const { formatDateTime } = useFormat();
  const [page, setPage] = useState(1);
  const limit = 20;

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ChannelForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['dedicated-channels', page, limit],
    queryFn: () =>
      api
        .get('/v1/egress/dedicated-channels', {
          params: { offset: (page - 1) * limit, limit },
        })
        .then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: object) => api.post('/v1/egress/dedicated-channels', body),
    onSuccess: () => {
      setFormOpen(false);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setFormError(detail || (err as any)?.message || t('enterprise.channels.error.create'));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: object }) =>
      api.put(`/v1/egress/dedicated-channels/${id}`, body),
    onSuccess: () => {
      setFormOpen(false);
      setEditingId(null);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setFormError(detail || (err as any)?.message || t('enterprise.channels.error.update'));
    },
  });

  const healthCheckMutation = useMutation({
    mutationFn: (id: string) =>
      api.post(`/v1/egress/dedicated-channels/${id}/health-check`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/egress/dedicated-channels/${id}`),
    onSuccess: () => {
      setDeleteId(null);
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
  });

  const isMutating = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  const handleOpenCreate = () => {
    setEditingId(null);
    setForm(emptyForm);
    setFormError(null);
    setFormOpen(true);
  };

  const handleOpenEdit = (row: any) => {
    setEditingId(row.channel_id);
    setForm({
      name: row.name || '',
      target_agent_id: row.target_agent_id || '',
      channel_type: row.channel_type || 'kafka',
      config: row.config ? JSON.stringify(row.config, null, 2) : '{}',
    });
    setFormError(null);
    setFormOpen(true);
  };

  const handleSubmit = () => {
    let parsedConfig: object;
    try {
      parsedConfig = JSON.parse(form.config);
    } catch {
      setFormError(t('enterprise.channels.error.invalidJson'));
      return;
    }
    const body = {
      name: form.name,
      target_agent_id: form.target_agent_id,
      channel_type: form.channel_type,
      config: parsedConfig,
    };
    if (editingId) {
      updateMutation.mutate({ id: editingId, body });
    } else {
      createMutation.mutate(body);
    }
  };

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
            { key: 'name', label: t('enterprise.table.name'), render: (r: any) => r.name || '-' },
            {
              key: 'channel_type',
              label: t('enterprise.table.type'),
              render: (r: any) => <NeutralChip>{r.channel_type || '-'}</NeutralChip>,
            },
            {
              key: 'status',
              label: t('enterprise.table.status'),
              render: (r: any) => <StatusBadge status={r.status} />,
            },
            {
              key: 'target_agent_id',
              label: t('enterprise.channels.table.targetAgent'),
              render: (r: any) =>
                r.target_agent_id ? r.target_agent_id.slice(0, 8) + '...' : '-',
            },
            {
              key: 'last_health_check',
              label: t('enterprise.channels.table.lastHealthCheck'),
              render: (r: any) =>
                r.last_health_check
                  ? formatDateTime(r.last_health_check)
                  : '-',
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
                    onClick={() => healthCheckMutation.mutate(r.channel_id)}
                    disabled={healthCheckMutation.isPending}
                  >
                    {t('enterprise.action.healthCheck')}
                  </PixButton>
                  <PixButton variant="danger" compact onClick={() => setDeleteId(r.channel_id)}>
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
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
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
            <option value="kafka">Kafka</option>
            <option value="rabbitmq">RabbitMQ</option>
            <option value="grpc">gRPC</option>
          </select>
        </PixelField>
        <PixelField label={t('enterprise.channels.form.config')} htmlFor="dc-config">
          <textarea
            id="dc-config"
            value={form.config}
            onChange={(e) => setForm({ ...form, config: e.target.value })}
            rows={4}
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
    </div>
  );
}
