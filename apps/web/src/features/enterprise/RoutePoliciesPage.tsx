import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { useT, useFormat } from '../../i18n';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
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

/**
 * Form contract: POST/GET /v1/routes/policies, PATCH /v1/routes/policies/{id}
 * (apps/api/app/schemas/route_policy.py — RoutePolicyCreate/Update carry
 * policy_name, description, priority, scope_id, source_zone_id, target_zone_id,
 * allowed_route_types, denied_route_types, require_approval, risk_level,
 * data_boundary_rules, enabled). The response keys fields `id`,
 * `policy_name`, `_zone_id` — there is no delete endpoint and no PUT.
 */
interface PolicyForm {
  policy_name: string;
  description: string;
  priority: string;
  source_zone_id: string;
  target_zone_id: string;
  allowed_route_types: string;
  denied_route_types: string;
  require_approval: boolean;
  risk_level: string;
  enabled: boolean;
}

const RISK_LEVELS = ['low', 'medium', 'high', 'critical'] as const;
const RISK_LABEL_KEYS: Record<string, string> = {
  low: 'enterprise.policies.risk.low',
  medium: 'enterprise.policies.risk.medium',
  high: 'enterprise.policies.risk.high',
  critical: 'enterprise.policies.risk.critical',
};

const emptyForm: PolicyForm = {
  policy_name: '',
  description: '',
  priority: '100',
  source_zone_id: '',
  target_zone_id: '',
  allowed_route_types: '',
  denied_route_types: '',
  require_approval: false,
  risk_level: 'low',
  enabled: true,
};

function splitList(raw: string): string[] | undefined {
  const items = raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  return items.length ? items : undefined;
}

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
      api.patch(`/v1/routes/policies/${id}`, body),
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

  const isMutating = createMutation.isPending || updateMutation.isPending;

  const handleOpenCreate = () => {
    setEditingId(null);
    setForm(emptyForm);
    setFormError(null);
    setFormOpen(true);
  };

  const handleOpenEdit = (row: any) => {
    setEditingId(row.id);
    const join = (v: unknown) =>
      Array.isArray(v) ? (v as string[]).join(', ') : '';
    setForm({
      policy_name: row.policy_name || '',
      description: row.description || '',
      priority: row.priority != null ? String(row.priority) : '',
      source_zone_id: row.source_zone_id || '',
      target_zone_id: row.target_zone_id || '',
      allowed_route_types: join(row.allowed_route_types),
      denied_route_types: join(row.denied_route_types),
      require_approval: !!row.require_approval,
      risk_level: row.risk_level || 'low',
      enabled: row.enabled ?? true,
    });
    setFormError(null);
    setFormOpen(true);
  };

  const handleSubmit = () => {
    const body: Record<string, unknown> = {
      policy_name: form.policy_name.trim(),
      priority: form.priority.trim() === '' ? 100 : Number(form.priority),
      require_approval: form.require_approval,
      enabled: form.enabled,
    };
    if (form.description.trim()) body.description = form.description.trim();
    if (form.source_zone_id.trim()) body.source_zone_id = form.source_zone_id.trim();
    if (form.target_zone_id.trim()) body.target_zone_id = form.target_zone_id.trim();
    const allowed = splitList(form.allowed_route_types);
    if (allowed) body.allowed_route_types = allowed;
    const denied = splitList(form.denied_route_types);
    if (denied) body.denied_route_types = denied;
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
            { key: 'policy_name', label: t('enterprise.table.name'), render: (r: any) => r.policy_name || '-' },
            { key: 'priority', label: t('enterprise.policies.table.priority'), render: (r: any) => r.priority ?? '-' },
            {
              key: 'source_zone_id',
              label: t('enterprise.policies.table.sourceZone'),
              render: (r: any) => (r.source_zone_id ? r.source_zone_id.slice(0, 8) + '…' : '-'),
            },
            {
              key: 'target_zone_id',
              label: t('enterprise.policies.table.targetZone'),
              render: (r: any) => (r.target_zone_id ? r.target_zone_id.slice(0, 8) + '…' : '-'),
            },
            {
              key: 'allowed_route_types',
              label: t('enterprise.policies.table.allowedTypes'),
              render: (r: any) => (
                <div className="flex flex-wrap gap-1">
                  {(r.allowed_route_types ?? []).length
                    ? (r.allowed_route_types as string[]).map((rt) => (
                        <NeutralChip key={rt}>{rt}</NeutralChip>
                      ))
                    : '-'}
                </div>
              ),
            },
            {
              key: 'denied_route_types',
              label: t('enterprise.policies.table.deniedTypes'),
              render: (r: any) => (
                <div className="flex flex-wrap gap-1">
                  {(r.denied_route_types ?? []).length
                    ? (r.denied_route_types as string[]).map((rt) => (
                        <NeutralChip key={rt}>{rt}</NeutralChip>
                      ))
                    : '-'}
                </div>
              ),
            },
            {
              key: 'risk_level',
              label: t('enterprise.policies.table.riskLevel'),
              render: (r: any) =>
                r.risk_level ? (
                  <NeutralChip>
                    {RISK_LABEL_KEYS[r.risk_level] ? t(RISK_LABEL_KEYS[r.risk_level]) : r.risk_level}
                  </NeutralChip>
                ) : (
                  '-'
                ),
            },
            {
              key: 'require_approval',
              label: t('enterprise.policies.table.requireApproval'),
              render: (r: any) => (
                <span className={r.require_approval ? PIXEL_CHIP.warn : PIXEL_CHIP.neutral}>
                  {r.require_approval ? t('enterprise.value.yes') : t('enterprise.value.no')}
                </span>
              ),
            },
            {
              key: 'enabled',
              label: t('enterprise.table.enabled'),
              render: (r: any) => (
                <button
                  onClick={() => toggleMutation.mutate({ id: r.id, enabled: !r.enabled })}
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
            value={form.policy_name}
            onChange={(e) => setForm({ ...form, policy_name: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.description')} htmlFor="rp-description">
          <input
            id="rp-description"
            type="text"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.priority')} htmlFor="rp-priority">
          <input
            id="rp-priority"
            type="number"
            min="0"
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.sourceZone')} htmlFor="rp-source-zone">
          <input
            id="rp-source-zone"
            type="text"
            value={form.source_zone_id}
            onChange={(e) => setForm({ ...form, source_zone_id: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.targetZone')} htmlFor="rp-dest-zone">
          <input
            id="rp-dest-zone"
            type="text"
            value={form.target_zone_id}
            onChange={(e) => setForm({ ...form, target_zone_id: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.allowedTypes')} htmlFor="rp-allowed">
          <input
            id="rp-allowed"
            type="text"
            value={form.allowed_route_types}
            onChange={(e) => setForm({ ...form, allowed_route_types: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.deniedTypes')} htmlFor="rp-denied">
          <input
            id="rp-denied"
            type="text"
            value={form.denied_route_types}
            onChange={(e) => setForm({ ...form, denied_route_types: e.target.value })}
            className={PIXEL_INPUT}
          />
        </PixelField>
        <PixelField label={t('enterprise.policies.form.riskLevel')} htmlFor="rp-risk">
          <select
            id="rp-risk"
            value={form.risk_level}
            onChange={(e) => setForm({ ...form, risk_level: e.target.value })}
            className={PIXEL_INPUT}
          >
            {RISK_LEVELS.map((rl) => (
              <option key={rl} value={rl}>
                {t(RISK_LABEL_KEYS[rl])}
              </option>
            ))}
          </select>
        </PixelField>
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="rp-approval"
            checked={form.require_approval}
            onChange={(e) => setForm({ ...form, require_approval: e.target.checked })}
            className="h-5 w-5 accent-pixel-accent"
          />
          <label
            htmlFor="rp-approval"
            className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted"
          >
            {t('enterprise.policies.form.requireApproval')}
          </label>
        </div>
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
    </div>
  );
}
