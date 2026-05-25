import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import ConfirmDialog from '../../components/ConfirmDialog';
import FormDialog from '../../components/FormDialog';

interface GatewayForm {
  name: string;
  endpoint: string;
  protocol: string;
  enabled: boolean;
  allowed_domains: string;
}

const emptyForm: GatewayForm = {
  name: '',
  endpoint: '',
  protocol: 'https',
  enabled: true,
  allowed_domains: '',
};

export default function EgressGatewaysPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [domainFilter, setDomainFilter] = useState('');
  const [appliedDomain, setAppliedDomain] = useState<string | undefined>(undefined);
  const limit = 20;

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<GatewayForm>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['egress-gateways', page, limit, appliedDomain],
    queryFn: () =>
      api
        .get('/v1/egress/gateways', {
          params: {
            offset: (page - 1) * limit,
            limit,
            target_domain: appliedDomain || undefined,
          },
        })
        .then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: object) => api.post('/v1/egress/gateways', body),
    onSuccess: () => {
      setFormOpen(false);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['egress-gateways'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setFormError(detail || (err as any)?.message || 'Failed to create egress gateway');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: object }) =>
      api.put(`/v1/egress/gateways/${id}`, body),
    onSuccess: () => {
      setFormOpen(false);
      setEditingId(null);
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ['egress-gateways'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setFormError(detail || (err as any)?.message || 'Failed to update egress gateway');
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.patch(`/v1/egress/gateways/${id}`, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['egress-gateways'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/v1/egress/gateways/${id}`),
    onSuccess: () => {
      setDeleteId(null);
      queryClient.invalidateQueries({ queryKey: ['egress-gateways'] });
    },
  });

  const isMutating = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  const handleSearch = () => {
    setAppliedDomain(domainFilter || undefined);
    setPage(1);
  };

  const handleOpenCreate = () => {
    setEditingId(null);
    setForm(emptyForm);
    setFormError(null);
    setFormOpen(true);
  };

  const handleOpenEdit = (row: any) => {
    setEditingId(row.gateway_id);
    setForm({
      name: row.name || '',
      endpoint: row.endpoint || '',
      protocol: row.protocol || 'https',
      enabled: row.enabled ?? true,
      allowed_domains: Array.isArray(row.allowed_domains) ? row.allowed_domains.join(', ') : '',
    });
    setFormError(null);
    setFormOpen(true);
  };

  const handleSubmit = () => {
    const domains = form.allowed_domains
      .split(',')
      .map((d) => d.trim())
      .filter(Boolean);
    const body = {
      name: form.name,
      endpoint: form.endpoint,
      protocol: form.protocol,
      enabled: form.enabled,
      allowed_domains: domains,
    };
    if (editingId) {
      updateMutation.mutate({ id: editingId, body });
    } else {
      createMutation.mutate(body);
    }
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load egress gateways" />;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Egress Gateways</h2>
        <button
          onClick={handleOpenCreate}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          Add Gateway
        </button>
      </div>

      <div className="mb-4 flex gap-2">
        <input
          type="text"
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Filter by domain"
          className="px-3 py-1.5 text-sm border rounded bg-white"
        />
        <button
          onClick={handleSearch}
          className="px-3 py-1.5 text-sm font-medium text-white bg-gray-900 rounded hover:bg-gray-800"
        >
          Search
        </button>
        {appliedDomain && (
          <button
            onClick={() => {
              setDomainFilter('');
              setAppliedDomain(undefined);
              setPage(1);
            }}
            className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50"
          >
            Clear
          </button>
        )}
      </div>

      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'name', label: 'Name', render: (r: any) => r.name || '-' },
            { key: 'endpoint', label: 'Endpoint', render: (r: any) => r.endpoint || '-' },
            {
              key: 'protocol',
              label: 'Protocol',
              render: (r: any) => (
                <span className="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                  {r.protocol || '-'}
                </span>
              ),
            },
            {
              key: 'enabled',
              label: 'Enabled',
              render: (r: any) => (
                <button
                  onClick={() => toggleMutation.mutate({ id: r.gateway_id, enabled: !r.enabled })}
                  className={`px-2 py-0.5 rounded text-xs font-medium cursor-pointer ${
                    r.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {r.enabled ? 'Yes' : 'No'}
                </button>
              ),
            },
            {
              key: 'allowed_domains',
              label: 'Allowed Domains',
              render: (r: any) =>
                Array.isArray(r.allowed_domains) && r.allowed_domains.length > 0
                  ? r.allowed_domains.join(', ')
                  : '-',
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
                    onClick={() => setDeleteId(r.gateway_id)}
                    className="px-3 py-1 text-xs font-medium text-red-700 bg-red-50 rounded hover:bg-red-100"
                  >
                    Delete
                  </button>
                </div>
              ),
            },
          ]}
          data={data?.gateways ?? []}
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
        title={editingId ? 'Edit Egress Gateway' : 'Add Egress Gateway'}
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
          <label htmlFor="eg-name" className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            id="eg-name"
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="eg-endpoint" className="block text-sm font-medium text-gray-700 mb-1">Endpoint</label>
          <input
            id="eg-endpoint"
            type="url"
            value={form.endpoint}
            onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
        <div>
          <label htmlFor="eg-protocol" className="block text-sm font-medium text-gray-700 mb-1">Protocol</label>
          <select
            id="eg-protocol"
            value={form.protocol}
            onChange={(e) => setForm({ ...form, protocol: e.target.value })}
            className="w-full px-3 py-2 border rounded text-sm bg-white"
          >
            <option value="http">HTTP</option>
            <option value="https">HTTPS</option>
            <option value="socks5">SOCKS5</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="eg-enabled"
            checked={form.enabled}
            onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            className="h-4 w-4 rounded border-gray-300"
          />
          <label htmlFor="eg-enabled" className="text-sm font-medium text-gray-700">Enabled</label>
        </div>
        <div>
          <label htmlFor="eg-domains" className="block text-sm font-medium text-gray-700 mb-1">Allowed Domains (comma-separated)</label>
          <input
            id="eg-domains"
            type="text"
            value={form.allowed_domains}
            onChange={(e) => setForm({ ...form, allowed_domains: e.target.value })}
            placeholder="example.com, api.example.org"
            className="w-full px-3 py-2 border rounded text-sm"
          />
        </div>
      </FormDialog>

      <ConfirmDialog
        open={deleteId !== null}
        title="Delete Egress Gateway"
        message="Are you sure you want to delete this egress gateway? This action cannot be undone."
        variant="danger"
        confirmLabel="Delete"
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
}
