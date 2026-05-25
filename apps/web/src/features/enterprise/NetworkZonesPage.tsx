import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import FormDialog from '../../components/FormDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import StatusBadge from '../../components/StatusBadge';

const VALID_ZONE_TYPES = ['regional', 'edge', 'restricted'];
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

function extractDomainError(err: any): string {
  const data = err?.response?.data;
  if (data?.error?.message) return data.error.message;
  if (data?.error?.detail) return data.error.detail;
  if (data?.detail) return data.detail;
  if (data?.message) return data.message;
  return err?.message || 'Operation failed';
}

export default function NetworkZonesPage() {
  const qc = useQueryClient();
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
      setFormError(extractDomainError(err));
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
      setFormError(extractDomainError(err));
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
      setDeleteError(extractDomainError(err));
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
      setFormError('Zone name is required');
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
        setFormError('Scope ID is required');
        return;
      }
      body.scope_id = form.scope_id.trim();
      body.zone_type = form.zone_type;
      createMutation.mutate(body);
    }
  }

  const zones: ZoneRow[] = data?.zones ?? [];
  const total: number = data?.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Network Zones</h2>
        <button
          onClick={handleOpenCreate}
          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Add Zone
        </button>
      </div>

      <div className="mb-4">
        <input
          className="border rounded px-3 py-1.5 text-sm w-72"
          placeholder="Filter by Scope ID"
          value={scopeIdFilter}
          onChange={(e) => { setScopeIdFilter(e.target.value); setOffset(0); }}
        />
      </div>

      {isLoading && <p className="text-gray-500">Loading...</p>}
      {isError && <p className="text-red-600">Failed to load zones</p>}

      {!isLoading && !isError && (
        <DataTable
          columns={[
            { key: 'zone_id', label: 'ID', render: (r: ZoneRow) => r.zone_id.slice(0, 8) },
            { key: 'zone_name', label: 'Name' },
            { key: 'zone_type', label: 'Type', render: (r: ZoneRow) => <StatusBadge status={r.zone_type} /> },
            { key: 'scope_id', label: 'Scope', render: (r: ZoneRow) => r.scope_id.slice(0, 8) },
            { key: 'region', label: 'Region' },
            { key: 'security_level', label: 'Security' },
            { key: 'agent_count', label: 'Agents' },
            {
              key: 'actions', label: '', render: (r: ZoneRow) => (
                <div className="flex gap-2">
                  <button onClick={() => handleOpenEdit(r)} className="text-xs text-blue-600 hover:underline">Edit</button>
                  <button onClick={() => { setDeleteId(r.zone_id); setDeleteError(null); }} className="text-xs text-red-600 hover:underline">Delete</button>
                </div>
              ),
            },
          ]}
          data={zones}
        />
      )}

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm text-gray-600">
            Showing {offset + 1}-{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={!canPrev}
              className="px-3 py-1.5 text-sm rounded bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={!canNext}
              className="px-3 py-1.5 text-sm rounded bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}

      <FormDialog
        open={formOpen}
        title={editingId ? 'Edit Zone' : 'Create Zone'}
        onClose={() => { setFormOpen(false); setEditingId(null); }}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      >
        <div className="space-y-3">
          {!editingId && (
            <>
              <div>
                <label htmlFor="zone-scope-id" className="block text-sm font-medium text-gray-700 mb-1">Scope ID</label>
                <input
                  id="zone-scope-id"
                  className="w-full border rounded px-3 py-1.5 text-sm"
                  value={form.scope_id}
                  onChange={(e) => setForm({ ...form, scope_id: e.target.value })}
                  placeholder="UUID of parent scope"
                />
              </div>
              <div>
                <label htmlFor="zone-type" className="block text-sm font-medium text-gray-700 mb-1">Zone Type</label>
                <select
                  id="zone-type"
                  className="w-full border rounded px-3 py-1.5 text-sm"
                  value={form.zone_type}
                  onChange={(e) => setForm({ ...form, zone_type: e.target.value })}
                >
                  {VALID_ZONE_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </>
          )}
          <div>
            <label htmlFor="zone-name" className="block text-sm font-medium text-gray-700 mb-1">Zone Name</label>
            <input
              id="zone-name"
              className="w-full border rounded px-3 py-1.5 text-sm"
              value={form.zone_name}
              onChange={(e) => setForm({ ...form, zone_name: e.target.value })}
            />
          </div>
          <div>
            <label htmlFor="zone-region" className="block text-sm font-medium text-gray-700 mb-1">Region</label>
            <input
              id="zone-region"
              className="w-full border rounded px-3 py-1.5 text-sm"
              value={form.region}
              onChange={(e) => setForm({ ...form, region: e.target.value })}
              placeholder="e.g. us-east-1"
            />
          </div>
          <div>
            <label htmlFor="zone-security" className="block text-sm font-medium text-gray-700 mb-1">Security Level</label>
            <select
              id="zone-security"
              className="w-full border rounded px-3 py-1.5 text-sm"
              value={form.security_level}
              onChange={(e) => setForm({ ...form, security_level: e.target.value })}
            >
              <option value="standard">Standard</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>
          <div>
            <label htmlFor="zone-cidr" className="block text-sm font-medium text-gray-700 mb-1">Network CIDR</label>
            <input
              id="zone-cidr"
              className="w-full border rounded px-3 py-1.5 text-sm"
              value={form.network_cidr}
              onChange={(e) => setForm({ ...form, network_cidr: e.target.value })}
              placeholder="e.g. 10.1.0.0/16"
            />
          </div>
          {formError && <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{formError}</div>}
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!deleteId}
        title="Delete Zone"
        message="This will delete the zone. This action cannot be undone."
        variant="danger"
        confirmLabel="Delete"
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        onCancel={() => { setDeleteId(null); setDeleteError(null); }}
      />
      {deleteError && <div className="mt-2 text-sm text-red-600 bg-red-50 p-2 rounded">{deleteError}</div>}
    </div>
  );
}