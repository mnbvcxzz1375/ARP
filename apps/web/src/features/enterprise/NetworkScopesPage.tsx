import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import FormDialog from '../../components/FormDialog';
import ConfirmDialog from '../../components/ConfirmDialog';
import StatusBadge from '../../components/StatusBadge';

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

function extractDomainError(err: any): string {
  const data = err?.response?.data;
  if (data?.error?.message) return data.error.message;
  if (data?.error?.detail) return data.error.detail;
  if (data?.detail) return data.detail;
  if (data?.message) return data.message;
  return err?.message || 'Operation failed';
}

export default function NetworkScopesPage() {
  const qc = useQueryClient();
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
      setFormError(extractDomainError(err));
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
      setFormError(extractDomainError(err));
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
      setDeleteError(extractDomainError(err));
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
      setFormError('Scope name is required');
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
        setFormError('User ID is required');
        return;
      }
      body.user_id = form.user_id.trim();
      body.scope_type = form.scope_type;
      createMutation.mutate(body);
    }
  }

  const scopes: ScopeRow[] = data?.scopes ?? [];
  const total: number = data?.total ?? 0;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold">Network Scopes</h2>
        <button
          onClick={handleOpenCreate}
          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Add Scope
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        <button
          onClick={() => { setScopeTypeFilter(''); setOffset(0); }}
          className={`px-3 py-1 text-sm rounded ${!scopeTypeFilter ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
        >
          All
        </button>
        {VALID_SCOPE_TYPES.map((t) => (
          <button
            key={t}
            onClick={() => { setScopeTypeFilter(t); setOffset(0); }}
            className={`px-3 py-1 text-sm rounded capitalize ${scopeTypeFilter === t ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
          >
            {t}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-gray-500">Loading...</p>}
      {isError && <p className="text-red-600">Failed to load scopes</p>}

      {!isLoading && !isError && (
        <DataTable
          columns={[
            { key: 'scope_id', label: 'ID', render: (r: ScopeRow) => r.scope_id.slice(0, 8) },
            { key: 'scope_name', label: 'Name' },
            { key: 'scope_type', label: 'Type', render: (r: ScopeRow) => <StatusBadge status={r.scope_type} /> },
            { key: 'username', label: 'Owner' },
            { key: 'network_cidr', label: 'CIDR' },
            { key: 'agent_count', label: 'Agents' },
            { key: 'zone_count', label: 'Zones' },
            {
              key: 'actions', label: '', render: (r: ScopeRow) => (
                <div className="flex gap-2">
                  <button onClick={() => handleOpenEdit(r)} className="text-xs text-blue-600 hover:underline">Edit</button>
                  <button onClick={() => { setDeleteId(r.scope_id); setDeleteError(null); }} className="text-xs text-red-600 hover:underline">Delete</button>
                </div>
              ),
            },
          ]}
          data={scopes}
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
        title={editingId ? 'Edit Scope' : 'Create Scope'}
        onClose={() => { setFormOpen(false); setEditingId(null); }}
        onSubmit={handleSubmit}
        loading={createMutation.isPending || updateMutation.isPending}
      >
        <div className="space-y-3">
          {!editingId && (
            <>
              <div>
                <label htmlFor="scope-user-id" className="block text-sm font-medium text-gray-700 mb-1">User ID</label>
                <input
                  id="scope-user-id"
                  className="w-full border rounded px-3 py-1.5 text-sm"
                  value={form.user_id}
                  onChange={(e) => setForm({ ...form, user_id: e.target.value })}
                  placeholder="UUID of owner"
                />
              </div>
              <div>
                <label htmlFor="scope-type" className="block text-sm font-medium text-gray-700 mb-1">Scope Type</label>
                <select
                  id="scope-type"
                  className="w-full border rounded px-3 py-1.5 text-sm"
                  value={form.scope_type}
                  onChange={(e) => setForm({ ...form, scope_type: e.target.value })}
                >
                  {VALID_SCOPE_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </>
          )}
          <div>
            <label htmlFor="scope-name" className="block text-sm font-medium text-gray-700 mb-1">Scope Name</label>
            <input
              id="scope-name"
              className="w-full border rounded px-3 py-1.5 text-sm"
              value={form.scope_name}
              onChange={(e) => setForm({ ...form, scope_name: e.target.value })}
            />
          </div>
          <div>
            <label htmlFor="scope-cidr" className="block text-sm font-medium text-gray-700 mb-1">Network CIDR</label>
            <input
              id="scope-cidr"
              className="w-full border rounded px-3 py-1.5 text-sm"
              value={form.network_cidr}
              onChange={(e) => setForm({ ...form, network_cidr: e.target.value })}
              placeholder="e.g. 10.0.0.0/8"
            />
          </div>
          {formError && <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{formError}</div>}
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!deleteId}
        title="Delete Scope"
        message="This will delete the scope and its child zones. This action cannot be undone."
        variant="danger"
        confirmLabel="Delete"
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        onCancel={() => { setDeleteId(null); setDeleteError(null); }}
      />
      {deleteError && <div className="mt-2 text-sm text-red-600 bg-red-50 p-2 rounded">{deleteError}</div>}
    </div>
  );
}