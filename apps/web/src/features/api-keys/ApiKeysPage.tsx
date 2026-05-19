import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import SecretMaskedText from '../../components/SecretMaskedText';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function ApiKeysPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['api-keys'],
    queryFn: () => api.get('/v1/dashboard/api-keys').then((r) => r.data),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load API keys" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">API Keys</h2>
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'name', label: 'Name' },
            { key: 'key_prefix', label: 'Key Prefix', render: (r: any) => <SecretMaskedText text={r.key_prefix ?? ''} /> },
            { key: 'created_at', label: 'Created' },
            { key: 'expires_at', label: 'Expires' },
            { key: 'revoked_at', label: 'Revoked' },
          ]}
          data={data?.api_keys ?? []}
        />
      </div>
    </div>
  );
}
