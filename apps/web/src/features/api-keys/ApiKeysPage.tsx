import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import SecretMaskedText from '../../components/SecretMaskedText';
import ConfirmDialog from '../../components/ConfirmDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

interface RawKeyInfo {
  apiKey: string;
  name: string;
}

interface RevokeDialog {
  apiKeyId: string;
  keyName: string;
}

export default function ApiKeysPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [rawKey, setRawKey] = useState<RawKeyInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revokeDialog, setRevokeDialog] = useState<RevokeDialog | null>(null);

  const { data, isLoading, isError: isQueryError } = useQuery({
    queryKey: ['api-keys'],
    queryFn: () => api.get('/v1/dashboard/api-keys').then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (body: { name: string; expires_at: string | null }) =>
      api.post('/v1/dashboard/api-keys', body).then((r) => r.data),
    onSuccess: (result) => {
      setRawKey({ apiKey: result.api_key, name: result.name });
      setName('');
      setExpiresAt('');
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || 'Failed to create API key');
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (apiKeyId: string) =>
      api.post(`/v1/dashboard/api-keys/${apiKeyId}/revoke`, { allow_last_key: false }),
    onSuccess: () => {
      setRevokeDialog(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['api-keys'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard/overview'] });
    },
    onError: (err: unknown) => {
      setRevokeDialog(null);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || 'Failed to revoke API key');
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setRawKey(null);
    setError(null);
    const expiresAtIso = expiresAt ? new Date(expiresAt + 'T00:00:00').toISOString() : null;
    createMutation.mutate({ name: name.trim(), expires_at: expiresAtIso });
  };

  const handleCloseRawKey = () => setRawKey(null);

  const handleRevokeClick = (apiKeyId: string, keyName: string) => {
    setError(null);
    setRevokeDialog({ apiKeyId, keyName });
  };

  const handleRevokeCancel = () => {
    setRevokeDialog(null);
    setError(null);
  };

  const handleRevokeConfirm = () => {
    if (!revokeDialog || revokeMutation.isPending) return;
    revokeMutation.mutate(revokeDialog.apiKeyId);
  };

  if (isLoading) return <LoadingState />;
  if (isQueryError) return <ErrorState message="Failed to load API keys" />;

  const apiKeys = data?.api_keys ?? [];

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">API Keys</h2>

      {error && (
        <div className="mb-4 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded">
          {error}
        </div>
      )}

      {/* Create API Key Form */}
      <form onSubmit={handleCreate} className="mb-6 p-4 bg-white rounded-lg border">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Create API Key</h3>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="key-name" className="block text-xs font-medium text-gray-600 mb-1">
              Name
            </label>
            <input
              id="key-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="My API Key"
              className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="key-expires" className="block text-xs font-medium text-gray-600 mb-1">
              Expires At (optional)
            </label>
            <input
              id="key-expires"
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={createMutation.isPending || !name.trim()}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Key'}
          </button>
        </div>
      </form>

      {/* Raw Key Panel */}
      {rawKey && (
        <div className="mb-6 p-4 bg-white rounded-lg border-2 border-green-500">
          <div className="flex items-start justify-between mb-2">
            <h3 className="text-sm font-semibold text-green-800">API Key Created: {rawKey.name}</h3>
            <button
              onClick={handleCloseRawKey}
              className="text-sm text-gray-500 hover:text-gray-700 underline"
            >
              Close
            </button>
          </div>
          <SecretMaskedText text={rawKey.apiKey} />
          <p className="mt-2 text-sm text-red-600 font-medium">
            Copy this key now. You will not be able to see it again.
          </p>
        </div>
      )}

      {/* API Keys Table */}
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'name', label: 'Name' },
            { key: 'key_prefix', label: 'Key Prefix', render: (r: any) => <SecretMaskedText text={r.key_prefix ?? ''} /> },
            { key: 'created_at', label: 'Created' },
            { key: 'expires_at', label: 'Expires' },
            { key: 'revoked_at', label: 'Revoked' },
            {
              key: 'actions',
              label: 'Actions',
              render: (r: any) => {
                if (r.revoked_at) return null;
                return (
                  <button
                    onClick={() => handleRevokeClick(r.api_key_id, r.name)}
                    disabled={revokeMutation.isPending}
                    className="px-3 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Revoke
                  </button>
                );
              },
            },
          ]}
          data={apiKeys}
        />
      </div>

      <ConfirmDialog
        open={revokeDialog !== null}
        title="Revoke API Key"
        message={`Are you sure you want to revoke "${revokeDialog?.keyName}"? This action cannot be undone.`}
        variant="danger"
        confirmLabel="Revoke"
        onConfirm={handleRevokeConfirm}
        onCancel={handleRevokeCancel}
      />
    </div>
  );
}
