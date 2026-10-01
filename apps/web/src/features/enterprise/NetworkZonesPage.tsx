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
  NeutralChip,
  PageTitleRow,
  PixelField,
  PixButton,
  PIXEL_INPUT,
} from '../connections/pixel-ui';
import { cn } from '../../lib/utils';

const VALID_ZONE_TYPES = ['regional', 'edge', 'restricted'];
const VALID_SECURITY_LEVELS = ['standard', 'high', 'critical'];
const PAGE_SIZE = 50;

interface ZoneRow {
  zone_id: string;
  scope_id: string;
  zone_name: string;
  zone_type: string;
  region: string | null;
  security_level: string | null;
  network_cidr: string | null;
  agent_count: number;
  created_at: string;
  updated_at: string;
}

interface ZoneForm {
  scope_id: string;
  zone_name: string;
  zone_type: string;
  region: string;
  security_level: string;
  network_cidr: string;
}

const emptyForm: ZoneForm = {
  scope_id: '',
  zone_name: '',
  zone_type: 'regional',
  region: '',
  security_level: 'standard',
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

export default function NetworkZonesPage() {
  const qc = useQueryClient();
  const t = useT();
  const [offset, setOffset] = useState(0);
  const [scopeIdFilter, setScopeIdFilter] = useState<string>('');
  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ZoneForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/network/zones', offset, scopeIdFilter],
    queryFn: () =>
      api
        .get('/v1/dashboard/admin/network/zones', {
          params: { offset, limit: PAGE_SIZE, scope_id: scopeIdFilter || undefined },
        })
        .then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: Partial<ZoneForm>) =>
      api.post('/v1/dashboard/admin/network/zones', body),
    onSuccess: () => {
      setFormOpen(false);
      setFormError(null);
      qc.invalidateQueries({ queryKey: ['admin/network/zones'] });
    },
    onError: (err: any) => {
      setFormError(extractDomainError(err, t('enterprise.error.operationFailed')));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<ZoneForm> }) =>
      api.put(`/v1/dashboard/admin/network/zones/${id}`, body),
    onSuccess: () => {
      setFormOpen(false);
      setEditingId(null);
      setFormError(null);
      qc.invalidateQueries({ queryKey: ['admin/network/zones'] });
    },
    onError: (err: any) => {
      setFormError(extractDomainError(err, t('enterprise.error.operationFailed')));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      api.delete(`/v1/dashboard/admin/network/zones/${id}`),
    onSuccess: () => {
      setDeleteId(null);
      setDeleteError(null);
      qc.invalidateQueries({ queryKey: ['admin/network/zones'] });
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

  function handleOpenEdit(row: ZoneRow) {
    setEditingId(row.zone_id);
    setForm({
      scope_id: row.scope_id,
      zone_name: row.zone_name,
      zone_type: row.zone_type,
      region: row.region || '',
      security_level: row.security_level || 'standard',
      network_cidr: row.network_cidr || '',
    });
    setFormError(null);
    setFormOpen(true);
  }

  function handleSubmit() {
    if (!form.zone_name.trim()) {
      setFormError(t('enterprise.zones.error.nameRequired'));
      return;
    }
    const body: Record<string, any> = {
      zone_name: form.zone_name.trim(),
      region: form.region.trim() || null,
      security_level: form.security_level,
      network_cidr: form.network_cidr.trim() || null,
    };
    if (editingId) {
      updateMutation.mutate({ id: editingId, body });
    } else {
      if (!form.scope_id.trim()) {
        setFormError(t('enterprise.zones.error.scopeIdRequired'));
        return;
      }
      body.scope_id = form.scope_id.trim();
      body.zone_type = form.zone_type;
      createMutation.mutate(body);
    }
  }

  const zones: ZoneRow[] = data?.zones ?? [];
  const total: number = data?.total ?? 0;

  return (
    <div>
      <PageTitleRow
        title={t('enterprise.zones.title')}
        actions={
          <PixButton onClick={handleOpenCreate}>{t('enterprise.zones.action.add')}</PixButton>
        }
      />

      <div className="mb-4">
        <input
          className={cn(PIXEL_INPUT, 'sm:w-72')}
          placeholder={t('enterprise.zones.filter.scopePlaceholder')}
          value={scopeIdFilter}
          onChange={(e) => {
            setScopeIdFilter(e.target.value);
            setOffset(0);
          }}
        />
      </div>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message={t('enterprise.zones.error.load')} />}

      {!isLoading && !isError && (
        <DataTable
          columns={[
            { key: 'zone_id', label: t('enterprise.table.id'), render: (r: ZoneRow) => r.zone_id.slice(0, 8) },
            { key: 'zone_name', label: t('enterprise.table.name') },
            {
              key: 'zone_type',
              label: t('enterprise.table.type'),
              render: (r: ZoneRow) => (
                <NeutralChip>
                  {VALID_ZONE_TYPES.includes(r.zone_type)
                    ? t(`enterprise.zones.zoneType.${r.zone_type}`)
                    : r.zone_type}
                </NeutralChip>
              ),
            },
            { key: 'scope_id', label: t('enterprise.zones.table.scope'), render: (r: ZoneRow) => r.scope_id.slice(0, 8) },
            { key: 'region', label: t('enterprise.zones.table.region') },
            {
              key: 'security_level',
              label: t('enterprise.zones.table.security'),
              render: (r: ZoneRow) =>
                r.security_level && VALID_SECURITY_LEVELS.includes(r.security_level)
                  ? t(`enterprise.zones.security.${r.security_level}`)
                  : r.security_level ?? '',
            },
            { key: 'agent_count', label: t('enterprise.zones.table.agents') },
            {
              key: 'actions',
              label: '',
              render: (r: ZoneRow) => (
                <div className="flex gap-2">
                  <PixButton variant="ghost" compact onClick={() => handleOpenEdit(r)}>
                    {t('enterprise.action.edit')}
                  </PixButton>
                  <PixButton
                    variant="danger"
                    compact
                    onClick={() => {
                      setDeleteId(r.zone_id);
                      setDeleteError(null);
                    }}
                  >
                    {t('enterprise.action.delete')}
                  </PixButton>
                </div>
              ),
            },
          ]}
          data={zones}
        />
      )}

      {total > PAGE_SIZE && (
        <Pagination offset={offset} limit={PAGE_SIZE} total={total} onPageChange={setOffset} />
      )}

      <FormDialog
        open={formOpen}
        title={editingId ? t('enterprise.zones.form.editTitle') : t('enterprise.zones.form.createTitle')}
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
              <PixelField label={t('enterprise.zones.form.scopeId')} htmlFor="zone-scope-id">
                <input
                  id="zone-scope-id"
                  className={PIXEL_INPUT}
                  value={form.scope_id}
                  onChange={(e) => setForm({ ...form, scope_id: e.target.value })}
                  placeholder={t('enterprise.zones.form.scopeIdPlaceholder')}
                />
              </PixelField>
              <PixelField label={t('enterprise.zones.form.zoneType')} htmlFor="zone-type">
                <select
                  id="zone-type"
                  className={PIXEL_INPUT}
                  value={form.zone_type}
                  onChange={(e) => setForm({ ...form, zone_type: e.target.value })}
                >
                  {VALID_ZONE_TYPES.map((zoneType) => (
                    <option key={zoneType} value={zoneType}>
                      {t(`enterprise.zones.zoneType.${zoneType}`)}
                    </option>
                  ))}
                </select>
              </PixelField>
            </>
          )}
          <PixelField label={t('enterprise.zones.form.zoneName')} htmlFor="zone-name">
            <input
              id="zone-name"
              className={PIXEL_INPUT}
              value={form.zone_name}
              onChange={(e) => setForm({ ...form, zone_name: e.target.value })}
            />
          </PixelField>
          <PixelField label={t('enterprise.zones.form.region')} htmlFor="zone-region">
            <input
              id="zone-region"
              className={PIXEL_INPUT}
              value={form.region}
              onChange={(e) => setForm({ ...form, region: e.target.value })}
              placeholder={t('enterprise.zones.form.regionPlaceholder')}
            />
          </PixelField>
          <PixelField label={t('enterprise.zones.form.securityLevel')} htmlFor="zone-security">
            <select
              id="zone-security"
              className={PIXEL_INPUT}
              value={form.security_level}
              onChange={(e) => setForm({ ...form, security_level: e.target.value })}
            >
              {VALID_SECURITY_LEVELS.map((level) => (
                <option key={level} value={level}>
                  {t(`enterprise.zones.security.${level}`)}
                </option>
              ))}
            </select>
          </PixelField>
          <PixelField label={t('enterprise.zones.form.networkCidr')} htmlFor="zone-cidr">
            <input
              id="zone-cidr"
              className={PIXEL_INPUT}
              value={form.network_cidr}
              onChange={(e) => setForm({ ...form, network_cidr: e.target.value })}
              placeholder={t('enterprise.zones.form.cidrPlaceholder')}
            />
          </PixelField>
          {formError && <ErrorBanner message={formError} className="mb-0" />}
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!deleteId}
        title={t('enterprise.zones.confirm.deleteTitle')}
        message={t('enterprise.zones.confirm.deleteMessage', {
          name: zones.find((z) => z.zone_id === deleteId)?.zone_name ?? '',
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
