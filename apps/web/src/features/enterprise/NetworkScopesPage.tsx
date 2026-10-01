import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { useT } from '../../i18n';
import DataTable from '../../components/DataTable';
import FormDialog from '../../components/FormDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import Pagination from '../../components/Pagination';
import {
  ErrorBanner,
  FilterPill,
  NeutralChip,
  PageTitleRow,
  PixelField,
  PixButton,
  PIXEL_INPUT,
} from '../connections/pixel-ui';

const VALID_SCOPE_TYPES = ['personal', 'enterprise'];
const PAGE_SIZE = 50;

interface ScopeRow {
  scope_id: string;
  scope_name: string;
  scope_type: string;
  user_id: string;
  username: string | null;
  network_cidr: string | null;
  agent_count: number;
  zone_count: number;
  created_at: string;
  updated_at: string;
}

interface ScopeForm {
  user_id: string;
  scope_name: string;
  scope_type: string;
  network_cidr: string;
}

const emptyForm: ScopeForm = {
  user_id: '',
  scope_name: '',
  scope_type: 'personal',
  network_cidr: '',
};

/**
 * Server error detail extractor: returns backend messages verbatim (they are
 * dynamic data, never translated) and falls back to the caller-supplied
 * translated message when nothing usable is present.
 */
function extractDomainError(err: any, fallback: string): string {
  const data = err?.response?.data;
  if (data?.error?.message) return data.error.message;
  if (data?.error?.detail) return data.error.detail;
  if (data?.detail) return data.detail;
  if (data?.message) return data.message;
  return err?.message || fallback;
}

export default function NetworkScopesPage() {
  const qc = useQueryClient();
  const t = useT();
  const [offset, setOffset] = useState(0);
  const [scopeTypeFilter, setScopeTypeFilter] = useState<string>('');
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ScopeForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/network/scopes', offset, scopeTypeFilter],
    queryFn: () =>
      api
        .get('/v1/dashboard/admin/network/scopes', {
          params: { offset, limit: PAGE_SIZE, scope_type: scopeTypeFilter || undefined },
        })
        .then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: Partial<ScopeForm>) =>
      api.post('/v1/dashboard/admin/network/scopes', body),
    onSuccess: () => {
      setFormOpen(false);
      setFormError(null);
      qc.invalidateQueries({ queryKey: ['admin/network/scopes'] });
    },
    onError: (err: any) => {
      setFormError(extractDomainError(err, t('enterprise.error.operationFailed')));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<ScopeForm> }) =>
      api.put(`/v1/dashboard/admin/network/scopes/${id}`, body),
    onSuccess: () => {
      setFormOpen(false);
      setEditingId(null);
      setFormError(null);
      qc.invalidateQueries({ queryKey: ['admin/network/scopes'] });
    },
    onError: (err: any) => {
      setFormError(extractDomainError(err, t('enterprise.error.operationFailed')));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      api.delete(`/v1/dashboard/admin/network/scopes/${id}`),
    onSuccess: () => {
      setDeleteId(null);
      setDeleteError(null);
      qc.invalidateQueries({ queryKey: ['admin/network/scopes'] });
    },
    onError: (err: any) => {
      setDeleteError(extractDomainError(err, t('enterprise.error.operationFailed')));
    },
  });

  function handleOpenCreate() {
    setEditingId(null);
    setForm(emptyForm);
    setFormError(null);
    setFormOpen(true);
  }

  function handleOpenEdit(row: ScopeRow) {
    setEditingId(row.scope_id);
    setForm({
      user_id: row.user_id,
      scope_name: row.scope_name,
      scope_type: row.scope_type,
      network_cidr: row.network_cidr || '',
    });
    setFormError(null);
    setFormOpen(true);
  }

  function handleSubmit() {
    if (!form.scope_name.trim()) {
      setFormError(t('enterprise.scopes.error.nameRequired'));
      return;
    }
    const body: Record<string, any> = {
      scope_name: form.scope_name.trim(),
      network_cidr: form.network_cidr.trim() || null,
    };
    if (editingId) {
      updateMutation.mutate({ id: editingId, body });
    } else {
      if (!form.user_id.trim()) {
        setFormError(t('enterprise.scopes.error.userIdRequired'));
        return;
      }
      body.user_id = form.user_id.trim();
      body.scope_type = form.scope_type;
      createMutation.mutate(body);
    }
  }

  const scopes: ScopeRow[] = data?.scopes ?? [];
  const total: number = data?.total ?? 0;

  return (
    <div>
      <PageTitleRow
        title={t('enterprise.scopes.title')}
        actions={
          <PixButton onClick={handleOpenCreate}>{t('enterprise.scopes.action.add')}</PixButton>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <FilterPill
          active={!scopeTypeFilter}
          onClick={() => {
            setScopeTypeFilter('');
            setOffset(0);
          }}
        >
          {t('enterprise.filter.all')}
        </FilterPill>
        {VALID_SCOPE_TYPES.map((scopeType) => (
          <FilterPill
            key={scopeType}
            active={scopeTypeFilter === scopeType}
            onClick={() => {
              setScopeTypeFilter(scopeType);
              setOffset(0);
            }}
            className="capitalize"
          >
            {t(`enterprise.scopes.scopeType.${scopeType}`)}
          </FilterPill>
        ))}
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message={t('enterprise.scopes.error.load')} />}

      {!isLoading && !isError && (
        <DataTable
          columns={[
            { key: 'scope_id', label: t('enterprise.table.id'), render: (r: ScopeRow) => r.scope_id.slice(0, 8) },
            { key: 'scope_name', label: t('enterprise.table.name') },
            {
              key: 'scope_type',
              label: t('enterprise.table.type'),
              render: (r: ScopeRow) => (
                <NeutralChip>
                  {VALID_SCOPE_TYPES.includes(r.scope_type)
                    ? t(`enterprise.scopes.scopeType.${r.scope_type}`)
                    : r.scope_type}
                </NeutralChip>
              ),
            },
            { key: 'username', label: t('enterprise.scopes.table.owner') },
            { key: 'network_cidr', label: t('enterprise.scopes.table.cidr') },
            { key: 'agent_count', label: t('enterprise.scopes.table.agents') },
            { key: 'zone_count', label: t('enterprise.scopes.table.zones') },
            {
              key: 'actions',
              label: '',
              render: (r: ScopeRow) => (
                <div className="flex gap-2">
                  <PixButton variant="ghost" compact onClick={() => handleOpenEdit(r)}>
                    {t('enterprise.action.edit')}
                  </PixButton>
                  <PixButton
                    variant="danger"
                    compact
                    onClick={() => {
                      setDeleteId(r.scope_id);
                      setDeleteError(null);
                    }}
                  >
                    {t('enterprise.action.delete')}
                  </PixButton>
                </div>
              ),
            },
          ]}
          data={scopes}
        />
      )}

      {total > PAGE_SIZE && (
        <Pagination offset={offset} limit={PAGE_SIZE} total={total} onPageChange={setOffset} />
      )}

      <FormDialog
        open={formOpen}
        title={editingId ? t('enterprise.scopes.form.editTitle') : t('enterprise.scopes.form.createTitle')}
        onClose={() => {
          setFormOpen(false);
          setEditingId(null);
        }}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      >
        <div className="space-y-4">
          {!editingId && (
            <>
              <PixelField label={t('enterprise.scopes.form.userId')} htmlFor="scope-user-id">
                <input
                  id="scope-user-id"
                  className={PIXEL_INPUT}
                  value={form.user_id}
                  onChange={(e) => setForm({ ...form, user_id: e.target.value })}
                  placeholder={t('enterprise.scopes.form.userIdPlaceholder')}
                />
              </PixelField>
              <PixelField label={t('enterprise.scopes.form.scopeType')} htmlFor="scope-type">
                <select
                  id="scope-type"
                  className={PIXEL_INPUT}
                  value={form.scope_type}
                  onChange={(e) => setForm({ ...form, scope_type: e.target.value })}
                >
                  {VALID_SCOPE_TYPES.map((scopeType) => (
                    <option key={scopeType} value={scopeType}>
                      {t(`enterprise.scopes.scopeType.${scopeType}`)}
                    </option>
                  ))}
                </select>
              </PixelField>
            </>
          )}
          <PixelField label={t('enterprise.scopes.form.scopeName')} htmlFor="scope-name">
            <input
              id="scope-name"
              className={PIXEL_INPUT}
              value={form.scope_name}
              onChange={(e) => setForm({ ...form, scope_name: e.target.value })}
            />
          </PixelField>
          <PixelField label={t('enterprise.scopes.form.networkCidr')} htmlFor="scope-cidr">
            <input
              id="scope-cidr"
              className={PIXEL_INPUT}
              value={form.network_cidr}
              onChange={(e) => setForm({ ...form, network_cidr: e.target.value })}
              placeholder={t('enterprise.scopes.form.cidrPlaceholder')}
            />
          </PixelField>
          {formError && <ErrorBanner message={formError} className="mb-0" />}
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!deleteId}
        title={t('enterprise.scopes.confirm.deleteTitle')}
        message={t('enterprise.scopes.confirm.deleteMessage', {
          name: scopes.find((s) => s.scope_id === deleteId)?.scope_name ?? '',
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
    </div>
  );
}
