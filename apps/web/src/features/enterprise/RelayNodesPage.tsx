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
  YesNoChip,
  PIXEL_INPUT,
} from '../connections/pixel-ui';
import { cn } from '../../lib/utils';

interface RelayNodeForm {
  name: string;
  endpoint: string;
  zone: string;
  relay_type: string;
  capacity: number | '';
}

const emptyForm: RelayNodeForm = {
  name: '',
  endpoint: '',
  zone: '',
  relay_type: 'central_relay',
  capacity: '',
};

/**
 * Translation keys for the node_type column. The backend vocabulary is wider
 * than the page's own filter/form options, so unknown values fall back to
 * the raw string instead of a missing-key warning.
 */
const NODE_TYPE_LABEL_KEYS: Record<string, string> = {
  central: 'enterprise.relayNodes.nodeType.central',
  central_relay: 'enterprise.relayNodes.nodeType.central_relay',
  edge: 'enterprise.relayNodes.nodeType.edge',
  local_edge: 'enterprise.relayNodes.nodeType.local_edge',
  personal_edge: 'enterprise.relayNodes.nodeType.personal_edge',
  regional: 'enterprise.relayNodes.nodeType.regional',
  egress: 'enterprise.relayNodes.nodeType.egress',
  dedicated: 'enterprise.relayNodes.nodeType.dedicated',
};

export default function RelayNodesPage() {
  const queryClient = useQueryClient();
  const t = useT();
  const { formatDateTime } = useFormat();
  const [page, setPage] = useState(1);
  const [nodeType, setNodeType] = useState<string | undefined>(undefined);
  const [status, setStatus] = useState<string | undefined>(undefined);
  const limit = 20;

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<RelayNodeForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['relay-nodes', page, limit, nodeType, status],
    queryFn: () =>
      api
        .get('/v1/routes/relay-nodes', {
          params: {
            offset: (page - 1) * limit,
            limit,
            node_type: nodeType || undefined,
            status: status || undefined,
          },
        })
        .then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: object) => api.post('/v1/routes/relay-nodes', body),
    onSuccess: () => {
      setFormOpen(false);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['relay-nodes'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setFormError(detail || (err as any)?.message || t('enterprise.relayNodes.error.create'));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: object }) =>
      api.put(`/v1/routes/relay-nodes/${id}`, body),
    onSuccess: () => {
      setFormOpen(false);
      setEditingId(null);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['relay-nodes'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setFormError(detail || (err as any)?.message || t('enterprise.relayNodes.error.update'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/routes/relay-nodes/${id}`),
    onSuccess: () => {
      setDeleteId(null);
      queryClient.invalidateQueries({ queryKey: ['relay-nodes'] });
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
    setEditingId(row.node_id);
    setForm({
      name: row.node_name || '',
      endpoint: row.endpoint || '',
      zone: row.zone || '',
      relay_type: row.node_type || 'central_relay',
      capacity: row.capacity ?? '',
    });
    setFormError(null);
    setFormOpen(true);
  };

  const handleSubmit = () => {
    const body = {
      name: form.name,
      endpoint: form.endpoint,
      zone: form.zone,
      relay_type: form.relay_type,
      capacity: form.capacity === '' ? undefined : Number(form.capacity),
    };
    if (editingId) {
      updateMutation.mutate({ id: editingId, body });
    } else {
      createMutation.mutate(body);
    }
  };

  // The header renders before/while the query resolves: an error or a slow
  // backend must not hide the page identity (PageTitleRow) — the loading and
  // error states render inline instead, same as the sibling scopes/zones
  // pages, so the page itself is always reachable and identifiable.
  const errorMessage = isError
    ? (error as any)?.response?.status === 403
      ? t('enterprise.error.accessDenied')
      : t('enterprise.relayNodes.error.load')
    : null;

  return (
    <div>
      <PageTitleRow
        title={t('enterprise.relayNodes.title')}
        actions={
          <PixButton onClick={handleOpenCreate}>{t('enterprise.relayNodes.action.add')}</PixButton>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <select
          value={nodeType ?? ''}
          onChange={(e) => {
            setNodeType(e.target.value || undefined);
            setPage(1);
          }}
          className={cn(PIXEL_INPUT, 'w-full sm:w-auto')}
        >
          <option value="">{t('enterprise.relayNodes.filter.allTypes')}</option>
          <option value="relay">{t('enterprise.relayNodes.filter.typeRelay')}</option>
          <option value="edge">{t('enterprise.relayNodes.filter.typeEdge')}</option>
          <option value="personal_edge">
            {t('enterprise.relayNodes.filter.typePersonalEdge')}
          </option>
        </select>
        <select
          value={status ?? ''}
          onChange={(e) => {
            setStatus(e.target.value || undefined);
            setPage(1);
          }}
          className={cn(PIXEL_INPUT, 'w-full sm:w-auto')}
        >
          <option value="">{t('enterprise.relayNodes.filter.allStatuses')}</option>
          <option value="healthy">{t('common.statusLabel.healthy')}</option>
          <option value="degraded">{t('common.statusLabel.degraded')}</option>
          <option value="down">{t('common.statusLabel.down')}</option>
        </select>
      </div>

      {isLoading && <LoadingState />}
      {isError && errorMessage !== null && <ErrorState message={errorMessage} />}

      {!isLoading && !isError && (
        <PixelPanel>
          <DataTable
            className="border-0"
            columns={[
            { key: 'node_name', label: t('enterprise.table.name') },
            {
              key: 'node_type',
              label: t('enterprise.table.type'),
              render: (r: any) => (
                <NeutralChip>
                  {r.node_type && NODE_TYPE_LABEL_KEYS[r.node_type]
                    ? t(NODE_TYPE_LABEL_KEYS[r.node_type])
                    : r.node_type || '-'}
                </NeutralChip>
              ),
            },
            { key: 'status', label: t('enterprise.table.status'), render: (r: any) => <StatusBadge status={r.status} /> },
            {
              key: 'current_load',
              label: t('enterprise.relayNodes.table.load'),
              render: (r: any) => (r.current_load != null ? `${r.current_load}%` : '-'),
            },
            { key: 'queue_depth', label: t('enterprise.relayNodes.table.queue') },
            {
              key: 'avg_latency_ms',
              label: t('enterprise.relayNodes.table.latency'),
              render: (r: any) => (r.avg_latency_ms != null ? `${r.avg_latency_ms}` : '-'),
            },
            {
              key: 'success_rate',
              label: t('enterprise.relayNodes.table.successRate'),
              render: (r: any) => (r.success_rate != null ? `${r.success_rate}%` : '-'),
            },
            { key: 'region', label: t('enterprise.relayNodes.table.region'), render: (r: any) => r.region || '-' },
            { key: 'zone', label: t('enterprise.relayNodes.table.zone'), render: (r: any) => r.zone || '-' },
            {
              key: 'enabled',
              label: t('enterprise.table.enabled'),
              render: (r: any) => <YesNoChip value={!!r.enabled} />,
            },
            {
              key: 'last_heartbeat_at',
              label: t('enterprise.relayNodes.table.lastHeartbeat'),
              render: (r: any) =>
                r.last_heartbeat_at ? formatDateTime(r.last_heartbeat_at) : '-',
            },
            {
              key: 'actions',
              label: '',
              render: (r: any) => (
                <div className="flex gap-2">
                  <PixButton variant="ghost" compact onClick={() => handleOpenEdit(r)}>
                    {t('enterprise.action.edit')}
                  </PixButton>
                  <PixButton variant="danger" compact onClick={() => setDeleteId(r.node_id)}>
                    {t('enterprise.action.delete')}
                  </PixButton>
                </div>
              ),
            },
          ]}
          data={data?.relay_nodes ?? []}
        />
          <Pagination
            offset={(page - 1) * limit}
            limit={limit}
            total={data?.total ?? 0}
            onPageChange={(offset) => setPage(Math.floor(offset / limit) + 1)}
          />
        </PixelPanel>
      )}

      <FormDialog
        open={formOpen}
        title={editingId ? t('enterprise.relayNodes.form.editTitle') : t('enterprise.relayNodes.form.createTitle')}
        onClose={() => {
          setFormOpen(false);
          setEditingId(null);
          setFormError(null);
        }}
        onSubmit={handleSubmit}
        loading={isMutating}
      >
        {formError && <ErrorBanner message={formError} className="mb-0" />}
        <PixelField label={t('enterprise.relayNodes.form.name')} htmlFor="rn-name">
          <input
            id="rn-name"
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.relayNodes.form.endpoint')} htmlFor="rn-endpoint">
          <input
            id="rn-endpoint"
            type="url"
            value={form.endpoint}
            onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.relayNodes.form.zone')} htmlFor="rn-zone">
          <input
            id="rn-zone"
            type="text"
            value={form.zone}
            onChange={(e) => setForm({ ...form, zone: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.relayNodes.form.relayType')} htmlFor="rn-relay-type">
          <select
            id="rn-relay-type"
            value={form.relay_type}
            onChange={(e) => setForm({ ...form, relay_type: e.target.value })}
            className={PIXEL_INPUT}
          >
            <option value="central_relay">{t('enterprise.relayNodes.relayType.centralRelay')}</option>
            <option value="edge">{t('enterprise.relayNodes.relayType.edge')}</option>
          </select>
        </PixelField>
        <PixelField label={t('enterprise.relayNodes.form.capacity')} htmlFor="rn-capacity">
          <input
            id="rn-capacity"
            type="number"
            value={form.capacity}
            onChange={(e) =>
              setForm({ ...form, capacity: e.target.value === '' ? '' : Number(e.target.value) })
            }
            className={PIXEL_INPUT}
          />
        </PixelField>
      </FormDialog>

      <ConfirmDialog
        open={deleteId !== null}
        title={t('enterprise.relayNodes.confirm.deleteTitle')}
        message={t('enterprise.relayNodes.confirm.deleteMessage')}
        variant="danger"
        confirmLabel={t('enterprise.action.delete')}
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
}
