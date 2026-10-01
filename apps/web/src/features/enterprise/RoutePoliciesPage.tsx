import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { useT, useFormat } from '../../i18n';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
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
import { cn } from '../../lib/utils';
import { PIXEL_CHIP } from '../../lib/tokens';

interface PolicyForm {
  name: string;
  source_zone: string;
  dest_zone: string;
  priority: number | '';
  relay_type_preference: string;
  enabled: boolean;
}

const emptyForm: PolicyForm = {
  name: '',
  source_zone: '',
  dest_zone: '',
  priority: '',
  relay_type_preference: 'central_relay',
  enabled: true,
};

export default function RoutePoliciesPage() {
  const queryClient = useQueryClient();
  const t = useT();
  const { formatDateTime } = useFormat();
  const [page, setPage] = useState(1);
  const limit = 20;

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<PolicyForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['route-policies', page, limit],
    queryFn: () =>
      api
        .get('/v1/routes/policies', {
          params: { offset: (page - 1) * limit, limit },
        })
        .then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: object) => api.post('/v1/routes/policies', body),
    onSuccess: () => {
      setFormOpen(false);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['route-policies'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setFormError(detail || (err as any)?.message || t('enterprise.policies.error.create'));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: object }) =>
      api.put(`/v1/routes/policies/${id}`, body),
    onSuccess: () => {
      setFormOpen(false);
      setEditingId(null);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['route-policies'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setFormError(detail || (err as any)?.message || t('enterprise.policies.error.update'));
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patch(`/v1/routes/policies/${id}`, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['route-policies'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/routes/policies/${id}`),
    onSuccess: () => {
      setDeleteId(null);
      queryClient.invalidateQueries({ queryKey: ['route-policies'] });
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
    setEditingId(row.policy_id);
    setForm({
      name: row.name || '',
      source_zone: row.source_zone || '',
      dest_zone: row.dest_zone || '',
      priority: row.priority ?? '',
      relay_type_preference: row.relay_type_preference || 'central_relay',
      enabled: row.enabled ?? true,
    });
    setFormError(null);
    setFormOpen(true);
  };

  const handleSubmit = () => {
    const body = {
      name: form.name,
      source_zone: form.source_zone,
      dest_zone: form.dest_zone,
      priority: form.priority === '' ? undefined : Number(form.priority),
      relay_type_preference: form.relay_type_preference,
      enabled: form.enabled,
    };
    if (editingId) {
      updateMutation.mutate({ id: editingId, body });
    } else {
      createMutation.mutate(body);
    }
  };

  if (isLoading) return <LoadingState />;
  if (isError) {
    const statusCode = (error as any)?.response?.status;
    if (statusCode === 403) {
      return <ErrorState message={t('enterprise.error.accessDenied')} />;
    }
    return <ErrorState message={t('enterprise.policies.error.load')} />;
  }

  return (
    <div>
      <PageTitleRow
        title={t('enterprise.policies.title')}
        actions={
          <PixButton onClick={handleOpenCreate}>{t('enterprise.policies.action.add')}</PixButton>
        }
      />

      <PixelPanel>
        <DataTable
          className="border-0"
          columns={[
            { key: 'name', label: t('enterprise.table.name') },
            { key: 'source_zone', label: t('enterprise.policies.table.sourceZone'), render: (r: any) => r.source_zone || '-' },
            { key: 'dest_zone', label: t('enterprise.policies.table.destZone'), render: (r: any) => r.dest_zone || '-' },
            { key: 'priority', label: t('enterprise.policies.table.priority'), render: (r: any) => r.priority ?? '-' },
            {
              key: 'relay_type_preference',
              label: t('enterprise.policies.table.relayType'),
              render: (r: any) => <NeutralChip>{r.relay_type_preference || '-'}</NeutralChip>,
            },
            {
              key: 'enabled',
              label: t('enterprise.table.enabled'),
              render: (r: any) => (
                <button
                  onClick={() =>
                    toggleMutation.mutate({ id: r.policy_id, enabled: !r.enabled })
                  }
                  className={cn(
                    'inline-flex cursor-pointer items-center px-2 py-0.5 font-pixel text-sm leading-none border-2 border-[#191a26]',
                    r.enabled ? PIXEL_CHIP.ok : PIXEL_CHIP.neutral,
                  )}
                >
                  {r.enabled ? t('enterprise.value.yes') : t('enterprise.value.no')}
                </button>
              ),
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
                  <PixButton variant="danger" compact onClick={() => setDeleteId(r.policy_id)}>
                    {t('enterprise.action.delete')}
                  </PixButton>
                </div>
              ),
            },
          ]}
          data={data?.policies ?? []}
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
        title={editingId ? t('enterprise.policies.form.editTitle') : t('enterprise.policies.form.createTitle')}
        onClose={() => {
          setFormOpen(false);
          setEditingId(null);
          setFormError(null);
        }}
        onSubmit={handleSubmit}
        loading={isMutating}
      >
        {formError && <ErrorBanner message={formError} className="mb-0" />}
        <PixelField label={t('enterprise.policies.form.name')} htmlFor="rp-name">
          <input
            id="rp-name"
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.sourceZone')} htmlFor="rp-source-zone">
          <input
            id="rp-source-zone"
            type="text"
            value={form.source_zone}
            onChange={(e) => setForm({ ...form, source_zone: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.destZone')} htmlFor="rp-dest-zone">
          <input
            id="rp-dest-zone"
            type="text"
            value={form.dest_zone}
            onChange={(e) => setForm({ ...form, dest_zone: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.priority')} htmlFor="rp-priority">
          <input
            id="rp-priority"
            type="number"
            value={form.priority}
            onChange={(e) =>
              setForm({ ...form, priority: e.target.value === '' ? '' : Number(e.target.value) })
            }
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.relayTypePreference')} htmlFor="rp-relay-type">
          <select
            id="rp-relay-type"
            value={form.relay_type_preference}
            onChange={(e) => setForm({ ...form, relay_type_preference: e.target.value })}
            className={PIXEL_INPUT}
          >
            <option value="central_relay">{t('enterprise.policies.relayType.centralRelay')}</option>
            <option value="edge">{t('enterprise.policies.relayType.edge')}</option>
            <option value="dedicated">{t('enterprise.policies.relayType.dedicated')}</option>
          </select>
        </PixelField>
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="rp-enabled"
            checked={form.enabled}
            onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            className="h-5 w-5 accent-pixel-accent"
          />
          <label
            htmlFor="rp-enabled"
            className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted"
          >
            {t('enterprise.policies.form.enabled')}
          </label>
        </div>
      </FormDialog>

      <ConfirmDialog
        open={deleteId !== null}
        title={t('enterprise.policies.confirm.deleteTitle')}
        message={t('enterprise.policies.confirm.deleteMessage')}
        variant="danger"
        confirmLabel={t('enterprise.action.delete')}
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
}
