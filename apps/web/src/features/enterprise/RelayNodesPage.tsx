import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import ConfirmDialog from '../../components/ConfirmDialog';
import FormDialog from '../../components/FormDialog';

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

export default function RelayNodesPage() {
  const queryClient = useQueryClient();
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
      setFormError(detail || (err as any)?.message || 'Failed to create relay node');
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
      setFormError(detail || (err as any)?.message || 'Failed to update relay node');
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

  if (isLoading) return <LoadingState />;
  if (isError) {
    const statusCode = (error as any)?.response?.status;
    if (statusCode === 403) {
      return <ErrorState message="Access denied" />;
    }
    return <ErrorState message="Failed to load relay nodes" />;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Relay Nodes</h2>
        <button
          onClick={handleOpenCreate}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          Add Relay Node
        </button>
      </div>

      <div className="mb-4 flex gap-3">
        <select
          value={nodeType ?? ''}
          onChange={(e) => {
            setNodeType(e.target.value || undefined);
            setPage(1);
          }}
          className="px-3 py-1.5 text-sm border rounded bg-white"
        >
          <option value="">All Types</option>
          <option value="relay">Relay</option>
          <option value="edge">Edge</option>
          <option value="personal_edge">Personal Edge</option>
        </select>
        <select
          value={status ?? ''}
          onChange={(e) => {
            setStatus(e.target.value || undefined);
            setPage(1);
          }}
          className="px-3 py-1.5 text-sm border rounded bg-white"
        >
          <option value="">All Statuses</option>
          <option value="healthy">Healthy</option>
          <option value="degraded">Degraded</option>
          <option value="down">Down</option>
        </select>
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'node_name', label: 'Name' },
            { key: 'node_type', label: 'Type' },
            { key: 'status', label: 'Status', render: (r: any) => <StatusBadge status={r.status} /> },
            {
              key: 'current_load',
              label: 'Load',
              render: (r: any) => r.current_load != null ? `${r.current_load}%` : '-',
            },
            { key: 'queue_depth', label: 'Queue' },
            {
              key: 'avg_latency_ms',
              label: 'Latency (ms)',
              render: (r: any) => r.avg_latency_ms != null ? `${r.avg_latency_ms}` : '-',
            },
            {
              key: 'success_rate',
              label: 'Success Rate',
              render: (r: any) => r.success_rate != null ? `${r.success_rate}%` : '-',
            },
            { key: 'region', label: 'Region', render: (r: any) => r.region || '-' },
            { key: 'zone', label: 'Zone', render: (r: any) => r.zone || '-' },
            {
              key: 'enabled',
              label: 'Enabled',
              render: (r: any) => (
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                  r.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                }`}>
                  {r.enabled ? 'Yes' : 'No'}
                </span>
              ),
            },
            {
              key: 'last_heartbeat_at',
              label: 'Last Heartbeat',
              render: (r: any) => r.last_heartbeat_at ? new Date(r.last_heartbeat_at).toLocaleString() : '-',
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
                    onClick={() => setDeleteId(r.node_id)}
                    className="px-3 py-1 text-xs font-medium text-red-700 bg-red-50 rounded hover:bg-red-100"
                  >
                    Delete
                  </button>
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
      </div>

      <FormDialog
        open={formOpen}
        title={editingId ? 'Edit Relay Node' : 'Add Relay Node'}
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
          <label htmlFor="rn-name" className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            id="rn-name"
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="rn-endpoint" className="block text-sm font-medium text-gray-700 mb-1">Endpoint</label>
          <input
            id="rn-endpoint"
            type="url"
            value={form.endpoint}
            onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="rn-zone" className="block text-sm font-medium text-gray-700 mb-1">Zone</label>
          <input
            id="rn-zone"
            type="text"
            value={form.zone}
            onChange={(e) => setForm({ ...form, zone: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="rn-relay-type" className="block text-sm font-medium text-gray-700 mb-1">Relay Type</label>
          <select
            id="rn-relay-type"
            value={form.relay_type}
            onChange={(e) => setForm({ ...form, relay_type: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm bg-white"
          >
            <option value="central_relay">Central Relay</option>
            <option value="edge">Edge</option>
          </select>
        </div>
        <div>
          <label htmlFor="rn-capacity" className="block text-sm font-medium text-gray-700 mb-1">Capacity</label>
          <input
            id="rn-capacity"
            type="number"
            value={form.capacity}
            onChange={(e) => setForm({ ...form, capacity: e.target.value === '' ? '' : Number(e.target.value) })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
      </FormDialog>

      <ConfirmDialog
        open={deleteId !== null}
        title="Delete Relay Node"
        message="Are you sure you want to delete this relay node? This action cannot be undone."
        variant="danger"
        confirmLabel="Delete"
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
}
