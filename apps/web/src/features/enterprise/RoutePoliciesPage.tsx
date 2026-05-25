import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import ConfirmDialog from '../../components/ConfirmDialog';
import FormDialog from '../../components/FormDialog';

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
      setFormError(detail || (err as any)?.message || 'Failed to create route policy');
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
      setFormError(detail || (err as any)?.message || 'Failed to update route policy');
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
      return <ErrorState message="Access denied" />;
    }
    return <ErrorState message="Failed to load route policies" />;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Route Policies</h2>
        <button
          onClick={handleOpenCreate}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          Add Policy
        </button>
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'name', label: 'Name' },
            { key: 'source_zone', label: 'Source Zone', render: (r: any) => r.source_zone || '-' },
            { key: 'dest_zone', label: 'Dest Zone', render: (r: any) => r.dest_zone || '-' },
            { key: 'priority', label: 'Priority', render: (r: any) => r.priority ?? '-' },
            {
              key: 'relay_type_preference',
              label: 'Relay Type',
              render: (r: any) => (
                <span className="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                  {r.relay_type_preference || '-'}
                </span>
              ),
            },
            {
              key: 'enabled',
              label: 'Enabled',
              render: (r: any) => (
                <button
                  onClick={() => toggleMutation.mutate({ id: r.policy_id, enabled: !r.enabled })}
                  className={`px-2 py-0.5 rounded text-xs font-medium cursor-pointer ${
                    r.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {r.enabled ? 'Yes' : 'No'}
                </button>
              ),
            },
            {
              key: 'created_at',
              label: 'Created',
              render: (r: any) => r.created_at ? new Date(r.created_at).toLocaleString() : '-',
            },
            {
              key: 'actions',
              label: '',
              render: (r: any) => (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleOpenEdit(r)}
                    className="px-3 py-1 text-xs font-medium text-blue-700 bg-blue-50 rounded hover:bg-blue-100"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => setDeleteId(r.policy_id)}
                    className="px-3 py-1 text-xs font-medium text-red-700 bg-red-50 rounded hover:bg-red-100"
                  >
                    Delete
                  </button>
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
      </div>

      <FormDialog
        open={formOpen}
        title={editingId ? 'Edit Route Policy' : 'Add Route Policy'}
        onClose={() => { setFormOpen(false); setEditingId(null); setFormError(null); }}
        onSubmit={handleSubmit}
        loading={isMutating}
      >
        {formError && (
          <div className="p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded">
            {formError}
          </div>
        )}
        <div>
          <label htmlFor="rp-name" className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            id="rp-name"
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="rp-source-zone" className="block text-sm font-medium text-gray-700 mb-1">Source Zone</label>
          <input
            id="rp-source-zone"
            type="text"
            value={form.source_zone}
            onChange={(e) => setForm({ ...form, source_zone: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="rp-dest-zone" className="block text-sm font-medium text-gray-700 mb-1">Dest Zone</label>
          <input
            id="rp-dest-zone"
            type="text"
            value={form.dest_zone}
            onChange={(e) => setForm({ ...form, dest_zone: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="rp-priority" className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
          <input
            id="rp-priority"
            type="number"
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: e.target.value === '' ? '' : Number(e.target.value) })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="rp-relay-type" className="block text-sm font-medium text-gray-700 mb-1">Relay Type Preference</label>
          <select
            id="rp-relay-type"
            value={form.relay_type_preference}
            onChange={(e) => setForm({ ...form, relay_type_preference: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm bg-white"
          >
            <option value="central_relay">Central Relay</option>
            <option value="edge">Edge</option>
            <option value="dedicated">Dedicated</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="rp-enabled"
            checked={form.enabled}
            onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            className="h-4 w-4 rounded border-gray-300"
          />
          <label htmlFor="rp-enabled" className="text-sm font-medium text-gray-700">Enabled</label>
        </div>
      </FormDialog>

      <ConfirmDialog
        open={deleteId !== null}
        title="Delete Route Policy"
        message="Are you sure you want to delete this route policy? This action cannot be undone."
        variant="danger"
        confirmLabel="Delete"
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
}
