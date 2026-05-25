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

interface ChannelForm {
  name: string;
  target_agent_id: string;
  channel_type: string;
  config: string;
}

const emptyForm: ChannelForm = {
  name: '',
  target_agent_id: '',
  channel_type: 'kafka',
  config: '{}',
};

export default function DedicatedChannelsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const limit = 20;

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ChannelForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['dedicated-channels', page, limit],
    queryFn: () =>
      api
        .get('/v1/egress/dedicated-channels', {
          params: { offset: (page - 1) * limit, limit },
        })
        .then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: object) => api.post('/v1/egress/dedicated-channels', body),
    onSuccess: () => {
      setFormOpen(false);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setFormError(detail || (err as any)?.message || 'Failed to create dedicated channel');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: object }) =>
      api.put(`/v1/egress/dedicated-channels/${id}`, body),
    onSuccess: () => {
      setFormOpen(false);
      setEditingId(null);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setFormError(detail || (err as any)?.message || 'Failed to update dedicated channel');
    },
  });

  const healthCheckMutation = useMutation({
    mutationFn: (id: string) =>
      api.post(`/v1/egress/dedicated-channels/${id}/health-check`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/egress/dedicated-channels/${id}`),
    onSuccess: () => {
      setDeleteId(null);
      queryClient.invalidateQueries({ queryKey: ['dedicated-channels'] });
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
    setEditingId(row.channel_id);
    setForm({
      name: row.name || '',
      target_agent_id: row.target_agent_id || '',
      channel_type: row.channel_type || 'kafka',
      config: row.config ? JSON.stringify(row.config, null, 2) : '{}',
    });
    setFormError(null);
    setFormOpen(true);
  };

  const handleSubmit = () => {
    let parsedConfig: object;
    try {
      parsedConfig = JSON.parse(form.config);
    } catch {
      setFormError('Config must be valid JSON');
      return;
    }
    const body = {
      name: form.name,
      target_agent_id: form.target_agent_id,
      channel_type: form.channel_type,
      config: parsedConfig,
    };
    if (editingId) {
      updateMutation.mutate({ id: editingId, body });
    } else {
      createMutation.mutate(body);
    }
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load dedicated channels" />;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Dedicated Channels</h2>
        <button
          onClick={handleOpenCreate}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          Add Channel
        </button>
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'name', label: 'Name', render: (r: any) => r.name || '-' },
            {
              key: 'channel_type',
              label: 'Type',
              render: (r: any) => (
                <span className="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                  {r.channel_type || '-'}
                </span>
              ),
            },
            {
              key: 'status',
              label: 'Status',
              render: (r: any) => <StatusBadge status={r.status} />,
            },
            {
              key: 'target_agent_id',
              label: 'Target Agent',
              render: (r: any) => r.target_agent_id ? r.target_agent_id.slice(0, 8) + '...' : '-',
            },
            {
              key: 'last_health_check',
              label: 'Last Health Check',
              render: (r: any) =>
                r.last_health_check ? new Date(r.last_health_check).toLocaleString() : '-',
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
                    onClick={() => healthCheckMutation.mutate(r.channel_id)}
                    disabled={healthCheckMutation.isPending}
                    className="px-3 py-1 text-xs font-medium text-green-700 bg-green-50 rounded hover:bg-green-100 disabled:opacity-50"
                  >
                    Health Check
                  </button>
                  <button
                    onClick={() => setDeleteId(r.channel_id)}
                    className="px-3 py-1 text-xs font-medium text-red-700 bg-red-50 rounded hover:bg-red-100"
                  >
                    Delete
                  </button>
                </div>
              ),
            },
          ]}
          data={data?.channels ?? []}
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
        title={editingId ? 'Edit Dedicated Channel' : 'Add Dedicated Channel'}
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
          <label htmlFor="dc-name" className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            id="dc-name"
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="dc-target-agent" className="block text-sm font-medium text-gray-700 mb-1">Target Agent ID</label>
          <input
            id="dc-target-agent"
            type="text"
            value={form.target_agent_id}
            onChange={(e) => setForm({ ...form, target_agent_id: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="dc-channel-type" className="block text-sm font-medium text-gray-700 mb-1">Channel Type</label>
          <select
            id="dc-channel-type"
            value={form.channel_type}
            onChange={(e) => setForm({ ...form, channel_type: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm bg-white"
          >
            <option value="kafka">Kafka</option>
            <option value="rabbitmq">RabbitMQ</option>
            <option value="grpc">gRPC</option>
          </select>
        </div>
        <div>
          <label htmlFor="dc-config" className="block text-sm font-medium text-gray-700 mb-1">Config (JSON)</label>
          <textarea
            id="dc-config"
            value={form.config}
            onChange={(e) => setForm({ ...form, config: e.target.value })}
            rows={4}
            className="w-full px-3 py-2 border rounded text-sm font-mono"
          />
        </div>
      </FormDialog>

      <ConfirmDialog
        open={deleteId !== null}
        title="Delete Dedicated Channel"
        message="Are you sure you want to delete this dedicated channel? This action cannot be undone."
        variant="danger"
        confirmLabel="Delete"
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
}
