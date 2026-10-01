import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import SecretMaskedText from '../../components/SecretMaskedText';
import ConfirmDialog from '../../components/ConfirmDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { ErrorBanner, PageTitle, PixelField, PixelPanel, PixButton, PIXEL_INPUT } from '../connections/pixel-ui';
import { useT } from '../../i18n';

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
  const t = useT();
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
      setError(detail || (err as any)?.message || t('apiKeys.error.create'));
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
      setError(detail || (err as any)?.message || t('apiKeys.error.revoke'));
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
  if (isQueryError) return <ErrorState message={t('apiKeys.error.load')} />;

  const apiKeys = data?.api_keys ?? [];

  return (
    <div>
      <PageTitle>{t('apiKeys.title')}</PageTitle>

      {error && <ErrorBanner message={error} />}

      {/* Create API Key Form */}
      <PixelPanel title={t('apiKeys.create.title')} className="mb-6" bodyClassName="p-4">
        <form onSubmit={handleCreate} className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div className="flex-1 min-w-0">
            <PixelField label={t('apiKeys.create.field.name')} htmlFor="key-name">
              <input
                id="key-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder={t('apiKeys.create.field.namePlaceholder')}
                className={PIXEL_INPUT}
              />
            </PixelField>
          </div>
          <div className="flex-1 min-w-0">
            <PixelField label={t('apiKeys.create.field.expires')} htmlFor="key-expires">
              <input
                id="key-expires"
                type="date"
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                className={PIXEL_INPUT}
              />
            </PixelField>
          </div>
          <PixButton
            type="submit"
            disabled={createMutation.isPending || !name.trim()}
          >
            {createMutation.isPending
              ? t('apiKeys.create.action.creating')
              : t('apiKeys.create.action.submit')}
          </PixButton>
        </form>
      </PixelPanel>

      {/* Raw Key Panel: success state = solid LED green chip (11.24:1 both themes). */}
      {rawKey && (
        <div className="mb-6 border-2 border-[#191a26] bg-pixel-led-green p-4">
          <div className="mb-2 flex items-start justify-between gap-4">
            <h3 className="font-pixel text-pixel-sm uppercase tracking-pixel text-[#191a26]">
              {t('apiKeys.created.title', { name: rawKey.name })}
            </h3>
            <button
              onClick={handleCloseRawKey}
              className="border-2 border-[#191a26] bg-pixel-led-green px-3 py-1 font-pixel text-pixel-sm text-[#191a26] hover:bg-[#191a26] hover:text-pixel-led-green"
            >
              {t('common.action.close')}
            </button>
          </div>
          <SecretMaskedText text={rawKey.apiKey} />
          <p className="mt-2 font-pixel text-pixel-sm text-[#191a26]">
            {t('apiKeys.created.note')}
          </p>
        </div>
      )}

      {/* API Keys Table */}
      <DataTable
        columns={[
          { key: 'name', label: t('apiKeys.table.name') },
          { key: 'key_prefix', label: t('apiKeys.table.keyPrefix'), render: (r: any) => <SecretMaskedText text={r.key_prefix ?? ''} /> },
          { key: 'created_at', label: t('apiKeys.table.created') },
          { key: 'expires_at', label: t('apiKeys.table.expires') },
          { key: 'revoked_at', label: t('apiKeys.table.revoked') },
          {
            key: 'actions',
            label: t('apiKeys.table.actions'),
            render: (r: any) => {
              if (r.revoked_at) return null;
              return (
                <PixButton
                  variant="danger"
                  compact
                  onClick={() => handleRevokeClick(r.api_key_id, r.name)}
                  disabled={revokeMutation.isPending}
                >
                  {t('apiKeys.action.revoke')}
                </PixButton>
              );
            },
          },
        ]}
        data={apiKeys}
      />


      <ConfirmDialog
        open={revokeDialog !== null}
        title={t('apiKeys.confirm.revokeTitle')}
        message={
          revokeDialog
            ? t('apiKeys.confirm.revokeMessage', { name: revokeDialog.keyName })
            : ''
        }
        variant="danger"
        confirmLabel={t('apiKeys.action.revoke')}
        cancelLabel={t('common.action.cancel')}
        onConfirm={handleRevokeConfirm}
        onCancel={handleRevokeCancel}
      />
    </div>
  );
}
