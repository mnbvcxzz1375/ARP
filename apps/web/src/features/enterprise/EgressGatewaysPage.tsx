import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { useT, useFormat } from '../../i18n';
import DataTable from '../../components/DataTable';
import FormDialog from '../../components/FormDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import StepUpDialog from '../../components/StepUpDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import {
  ErrorBanner,
  NeutralChip,
  PageTitleRow,
  PixelField,
  PixButton,
  PIXEL_INPUT,
} from '../connections/pixel-ui';
import { cn } from '../../lib/utils';
import { PIXEL_CHIP } from '../../lib/tokens';

/**
 * Egress gateways console (full CRUD).
 *
 * Contract: /v1/egress/gateways (apps/api/app/routers/gateways.py).
 * Reads need admin:read; create/update/delete need super_admin:write plus
 * step-up auth and CSRF (the axios client sets X-CSRF-Token on mutations).
 * The list ships every row newest-first — the catalog is an admin-curated
 * policy set in the low dozens — so filtering happens client-side.
 */
const GATEWAY_TYPES = ['api', 'model', 'github', 'deployment', 'mcp'] as const;
type GatewayType = (typeof GATEWAY_TYPES)[number];

interface GatewayRow {
  id: string;
  scope_id: string;
  gateway_name: string;
  gateway_type: string;
  domain_allowlist: string[];
  secret_store_ref: string | null;
  rate_limit_config: Record<string, unknown> | null;
  cache_config: Record<string, unknown> | null;
  cost_tracking: boolean;
  enabled: boolean;
  // M4 egress policy point: default-deny baseline opt-in
  // (EgressGatewayResponse.allow_internal_egress, NOT NULL, default false).
  allow_internal_egress: boolean;
  created_at: string;
  updated_at: string;
}

interface GatewayListResponse {
  gateways: GatewayRow[];
  total: number;
}

interface ScopeRow {
  scope_id: string;
  scope_name: string;
  scope_type: string;
  username: string | null;
}

interface GatewayForm {
  scope_id: string;
  gateway_name: string;
  gateway_type: GatewayType;
  domain_allowlist: string;
  secret_store_ref: string;
  cost_tracking: boolean;
  enabled: boolean;
  // Default false: the backend's default-deny baseline
  // (EgressGatewayCreate.allow_internal_egress).
  allow_internal_egress: boolean;
}

const emptyForm: GatewayForm = {
  scope_id: '',
  gateway_name: '',
  gateway_type: 'api',
  domain_allowlist: '',
  secret_store_ref: '',
  cost_tracking: true,
  enabled: true,
  allow_internal_egress: false,
};

/** Split the comma-separated domains input into a clean allowlist. */
function parseDomains(raw: string): string[] {
  return raw
    .split(',')
    .map((d) => d.trim())
    .filter((d) => d.length > 0);
}

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
  | { type: 'toggle'; id: string; enabled: boolean }
  | null;

export default function EgressGatewaysPage() {
  const qc = useQueryClient();
  const t = useT();
  const { formatDateTime } = useFormat();
  const { data: auth } = useAuth();
  const isSuperAdmin = auth?.role === 'super_admin';

  const [textFilter, setTextFilter] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<GatewayForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [showStepUp, setShowStepUp] = useState(false);

  const { data, isLoading, isError } = useQuery<GatewayListResponse>({
    queryKey: ['egress-gateways'],
    queryFn: () => api.get('/v1/egress/gateways').then((r) => r.data),
    refetchInterval: 30000,
  });

  // Scopes for the create/edit form select (admin read).
  const { data: scopesData } = useQuery<{ scopes: ScopeRow[]; total: number }>({
    queryKey: ['egress-gateways/scopes'],
    queryFn: () =>
      api
        .get('/v1/dashboard/admin/network/scopes', { params: { offset: 0, limit: 200 } })
        .then((r) => r.data),
    enabled: isSuperAdmin,
  });

  const createMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post('/v1/egress/gateways', body),
    onSuccess: () => {
      setFormOpen(false);
      setFormError(null);
      setPendingAction(null);
      qc.invalidateQueries({ queryKey: ['egress-gateways'] });
    },
    onError: (err: any) => {
      setFormError(extractDomainError(err, t('enterprise.egress.error.create')));
      setPendingAction(null);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      api.patch(`/v1/egress/gateways/${id}`, body),
    onSuccess: () => {
      setFormOpen(false);
      setEditingId(null);
      setFormError(null);
      setPendingAction(null);
      qc.invalidateQueries({ queryKey: ['egress-gateways'] });
    },
    onError: (err: any) => {
      setFormError(extractDomainError(err, t('enterprise.egress.error.update')));
      setPendingAction(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/egress/gateways/${id}`),
    onSuccess: () => {
      setDeleteId(null);
      setDeleteError(null);
      setPendingAction(null);
      qc.invalidateQueries({ queryKey: ['egress-gateways'] });
    },
    onError: (err: any) => {
      setDeleteError(extractDomainError(err, t('enterprise.egress.error.delete')));
      setPendingAction(null);
    },
  });

  function handleOpenCreate() {
    if (isStepUpNeeded(auth?.step_up_until)) {
      setPendingAction({ type: 'create' });
      setShowStepUp(true);
      return;
    }
    openCreateForm();
  }

  function openCreateForm() {
    const scopes = scopesData?.scopes ?? [];
    setEditingId(null);
    setForm({ ...emptyForm, scope_id: scopes[0]?.scope_id ?? '' });
    setFormError(null);
    setFormOpen(true);
  }

  function handleOpenEdit(row: GatewayRow) {
    if (isStepUpNeeded(auth?.step_up_until)) {
      setPendingAction({ type: 'update', id: row.id });
      setShowStepUp(true);
      return;
    }
    openEditForm(row);
  }

  function openEditForm(row: GatewayRow) {
    setEditingId(row.id);
    setForm({
      scope_id: row.scope_id,
      gateway_name: row.gateway_name,
      gateway_type: (GATEWAY_TYPES as readonly string[]).includes(row.gateway_type)
        ? (row.gateway_type as GatewayType)
        : 'api',
      domain_allowlist: row.domain_allowlist.join(', '),
      secret_store_ref: row.secret_store_ref ?? '',
      cost_tracking: row.cost_tracking,
      enabled: row.enabled,
      allow_internal_egress: row.allow_internal_egress ?? false,
    });
    setFormError(null);
    setFormOpen(true);
  }

  function handleToggle(row: GatewayRow) {
    if (isStepUpNeeded(auth?.step_up_until)) {
      setPendingAction({ type: 'toggle', id: row.id, enabled: !row.enabled });
      setShowStepUp(true);
      return;
    }
    updateMutation.mutate({ id: row.id, body: { enabled: !row.enabled } });
  }

  function handleRequestDelete(row: GatewayRow) {
    if (isStepUpNeeded(auth?.step_up_until)) {
      setPendingAction({ type: 'delete', id: row.id });
      setShowStepUp(true);
      return;
    }
    setDeleteId(row.id);
    setDeleteError(null);
  }

  function handleSubmit() {
    if (!form.gateway_name.trim()) {
      setFormError(t('enterprise.egress.form.error.nameRequired'));
      return;
    }
    if (!form.scope_id) {
      setFormError(t('enterprise.egress.form.error.scopeRequired'));
      return;
    }
    const body: Record<string, unknown> = {
      gateway_name: form.gateway_name.trim(),
      gateway_type: form.gateway_type,
      domain_allowlist: parseDomains(form.domain_allowlist),
      secret_store_ref: form.secret_store_ref.trim() || null,
      cost_tracking: form.cost_tracking,
      allow_internal_egress: form.allow_internal_egress,
    };
    if (editingId) {
      body.enabled = form.enabled;
      updateMutation.mutate({ id: editingId, body });
    } else {
      body.scope_id = form.scope_id;
      createMutation.mutate(body);
    }
  }

  // After a successful step-up, replay whichever write the operator
  // originally requested.
  function handleStepUpSuccess() {
    setShowStepUp(false);
    if (!pendingAction) return;
    const action = pendingAction;
    const gateways = data?.gateways ?? [];
    switch (action.type) {
      case 'create':
        openCreateForm();
        break;
      case 'update': {
        const row = gateways.find((g) => g.id === action.id);
        if (row) openEditForm(row);
        break;
      }
      case 'delete':
        setDeleteId(action.id);
        setDeleteError(null);
        break;
      case 'toggle':
        updateMutation.mutate({ id: action.id, body: { enabled: action.enabled } });
        break;
    }
    setPendingAction(null);
  }

  function handleStepUpCancel() {
    setShowStepUp(false);
    setPendingAction(null);
  }

  const gateways: GatewayRow[] = data?.gateways ?? [];
  const filter = textFilter.trim().toLowerCase();
  const filtered = filter
    ? gateways.filter(
        (g) =>
          g.gateway_name.toLowerCase().includes(filter) ||
          g.domain_allowlist.some((d) => d.toLowerCase().includes(filter)) ||
          g.gateway_type.toLowerCase().includes(filter),
      )
    : gateways;

  const scopeLabel = (scopeId: string) => {
    const scope = (scopesData?.scopes ?? []).find((s) => s.scope_id === scopeId);
    return scope ? scope.scope_name : scopeId.slice(0, 8);
  };

  return (
    <div>
      <PageTitleRow
        title={t('enterprise.egress.title')}
        actions={
          isSuperAdmin ? (
            <PixButton onClick={handleOpenCreate}>{t('enterprise.egress.action.add')}</PixButton>
          ) : undefined
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          type="text"
          value={textFilter}
          onChange={(e) => setTextFilter(e.target.value)}
          placeholder={t('enterprise.egress.filter.placeholder')}
          className={cn(PIXEL_INPUT, 'w-full sm:w-72')}
        />
        {textFilter && (
          <PixButton variant="ghost" onClick={() => setTextFilter('')}>
            {t('enterprise.action.clear')}
          </PixButton>
        )}
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message={t('enterprise.egress.error.load')} />}

      {!isLoading && !isError && (
        <div className="border-2 border-pixel-line bg-pixel-surface">
          <DataTable
            className="border-0"
            columns={[
              { key: 'gateway_name', label: t('enterprise.table.name') },
              {
                key: 'gateway_type',
                label: t('enterprise.table.type'),
                render: (r: GatewayRow) => <NeutralChip>{r.gateway_type}</NeutralChip>,
              },
              {
                key: 'scope_id',
                label: t('enterprise.egress.table.scope'),
                render: (r: GatewayRow) => scopeLabel(r.scope_id),
              },
              {
                key: 'domain_allowlist',
                label: t('enterprise.egress.table.allowedDomains'),
                render: (r: GatewayRow) =>
                  Array.isArray(r.domain_allowlist) && r.domain_allowlist.length > 0
                    ? r.domain_allowlist.join(', ')
                    : '-',
              },
              {
                key: 'cost_tracking',
                label: t('enterprise.egress.table.costTracking'),
                render: (r: GatewayRow) => (
                  <span
                    className={cn(
                      'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none border-2 border-[#191a26]',
                      r.cost_tracking ? PIXEL_CHIP.ok : PIXEL_CHIP.neutral,
                    )}
                  >
                    {r.cost_tracking ? t('enterprise.value.yes') : t('enterprise.value.no')}
                  </span>
                ),
              },
              {
                // M4: amber when opted in — internal egress is a
                // security-relevant privilege on top of the default-deny
                // baseline, so it merits attention rather than a pass.
                key: 'allow_internal_egress',
                label: t('enterprise.egress.table.internalEgress'),
                render: (r: GatewayRow) => (
                  <span
                    className={cn(
                      'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none border-2 border-[#191a26]',
                      r.allow_internal_egress ? PIXEL_CHIP.warn : PIXEL_CHIP.neutral,
                    )}
                  >
                    {r.allow_internal_egress ? t('enterprise.value.yes') : t('enterprise.value.no')}
                  </span>
                ),
              },
              {
                key: 'enabled',
                label: t('enterprise.table.enabled'),
                render: (r: GatewayRow) =>
                  isSuperAdmin ? (
                    <button
                      type="button"
                      onClick={() => handleToggle(r)}
                      className={cn(
                        'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none border-2 border-[#191a26]',
                        r.enabled ? PIXEL_CHIP.ok : PIXEL_CHIP.neutral,
                      )}
                      aria-label={t('enterprise.egress.action.toggle', { name: r.gateway_name })}
                    >
                      {r.enabled ? t('enterprise.value.yes') : t('enterprise.value.no')}
                    </button>
                  ) : (
                    <span
                      className={cn(
                        'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none border-2 border-[#191a26]',
                        r.enabled ? PIXEL_CHIP.ok : PIXEL_CHIP.neutral,
                      )}
                    >
                      {r.enabled ? t('enterprise.value.yes') : t('enterprise.value.no')}
                    </span>
                  ),
              },
              {
                key: 'created_at',
                label: t('enterprise.table.created'),
                render: (r: GatewayRow) => (r.created_at ? formatDateTime(r.created_at) : '-'),
              },
              {
                key: 'actions',
                label: '',
                render: (r: GatewayRow) =>
                  isSuperAdmin ? (
                    <div className="flex gap-2">
                      <PixButton variant="ghost" compact onClick={() => handleOpenEdit(r)}>
                        {t('enterprise.action.edit')}
                      </PixButton>
                      <PixButton
                        variant="danger"
                        compact
                        onClick={() => handleRequestDelete(r)}
                      >
                        {t('enterprise.action.delete')}
                      </PixButton>
                    </div>
                  ) : null,
              },
            ]}
            data={filtered}
          />
        </div>
      )}

      <FormDialog
        open={formOpen}
        title={editingId ? t('enterprise.egress.form.editTitle') : t('enterprise.egress.form.createTitle')}
        onClose={() => {
          setFormOpen(false);
          setEditingId(null);
        }}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      >
        <div className="space-y-4">
          <PixelField label={t('enterprise.egress.form.scope')} htmlFor="gateway-scope">
            <select
              id="gateway-scope"
              className={PIXEL_INPUT}
              value={form.scope_id}
              onChange={(e) => setForm({ ...form, scope_id: e.target.value })}
              disabled={!!editingId}
            >
              {(scopesData?.scopes ?? []).map((scope) => (
                <option key={scope.scope_id} value={scope.scope_id}>
                  {scope.scope_name} ({scope.scope_type})
                </option>
              ))}
            </select>
          </PixelField>
          <PixelField label={t('enterprise.egress.form.name')} htmlFor="gateway-name">
            <input
              id="gateway-name"
              className={PIXEL_INPUT}
              value={form.gateway_name}
              onChange={(e) => setForm({ ...form, gateway_name: e.target.value })}
            />
          </PixelField>
          <PixelField label={t('enterprise.egress.form.type')} htmlFor="gateway-type">
            <select
              id="gateway-type"
              className={PIXEL_INPUT}
              value={form.gateway_type}
              onChange={(e) => setForm({ ...form, gateway_type: e.target.value as GatewayType })}
            >
              {GATEWAY_TYPES.map((gt) => (
                <option key={gt} value={gt}>
                  {gt}
                </option>
              ))}
            </select>
          </PixelField>
          <PixelField label={t('enterprise.egress.form.allowedDomains')} htmlFor="gateway-domains">
            <input
              id="gateway-domains"
              className={PIXEL_INPUT}
              value={form.domain_allowlist}
              onChange={(e) => setForm({ ...form, domain_allowlist: e.target.value })}
              placeholder={t('enterprise.egress.form.domainsPlaceholder')}
            />
          </PixelField>
          <PixelField label={t('enterprise.egress.form.secretRef')} htmlFor="gateway-secret">
            <input
              id="gateway-secret"
              className={PIXEL_INPUT}
              value={form.secret_store_ref}
              onChange={(e) => setForm({ ...form, secret_store_ref: e.target.value })}
              placeholder={t('enterprise.egress.form.secretRefPlaceholder')}
            />
          </PixelField>
          <PixelField label={t('enterprise.egress.form.costTracking')} htmlFor="gateway-cost">
            <label className="flex items-center gap-2 font-pixel text-sm text-pixel-fg">
              <input
                id="gateway-cost"
                type="checkbox"
                className="h-4 w-4 accent-pixel-accent"
                checked={form.cost_tracking}
                onChange={(e) => setForm({ ...form, cost_tracking: e.target.checked })}
              />
              {t('enterprise.egress.form.costTrackingHint')}
            </label>
          </PixelField>
          <PixelField label={t('enterprise.egress.form.internalEgress')} htmlFor="gateway-internal">
            <label className="flex items-center gap-2 font-pixel text-sm text-pixel-fg">
              <input
                id="gateway-internal"
                type="checkbox"
                className="h-4 w-4 accent-pixel-accent"
                checked={form.allow_internal_egress}
                onChange={(e) => setForm({ ...form, allow_internal_egress: e.target.checked })}
              />
              {t('enterprise.egress.form.internalEgressHint')}
            </label>
          </PixelField>
          {editingId && (
            <PixelField label={t('enterprise.egress.form.enabled')} htmlFor="gateway-enabled">
              <label className="flex items-center gap-2 font-pixel text-sm text-pixel-fg">
                <input
                  id="gateway-enabled"
                  type="checkbox"
                  className="h-4 w-4 accent-pixel-accent"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
                {t('enterprise.egress.form.enabledHint')}
              </label>
            </PixelField>
          )}
          {formError && <ErrorBanner message={formError} className="mb-0" />}
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!deleteId}
        title={t('enterprise.egress.confirm.deleteTitle')}
        message={t('enterprise.egress.confirm.deleteMessage', {
          name: gateways.find((g) => g.id === deleteId)?.gateway_name ?? '',
        })}
        variant="danger"
        confirmLabel={t('enterprise.action.delete')}
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        onCancel={() => {
          setDeleteId(null);
          setDeleteError(null);
        }}
      />
      {deleteError && <ErrorBanner message={deleteError} className="mt-4" />}

      <StepUpDialog
        open={showStepUp}
        onSuccess={handleStepUpSuccess}
        onCancel={handleStepUpCancel}
      />
    </div>
  );
}
