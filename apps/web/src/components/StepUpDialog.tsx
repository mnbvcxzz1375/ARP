import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/client';

interface StepUpDialogProps {
  open: boolean;
  onSuccess: () => void;
  onCancel: () => void;
}

export default function StepUpDialog({ open, onSuccess, onCancel }: StepUpDialogProps) {
  const [apiKey, setApiKey] = useState('');
  const queryClient = useQueryClient();

  const stepUpMutation = useMutation({
    mutationFn: (key: string) => api.post('/v1/dashboard/auth/step-up', { api_key: key }),
    onSuccess: () => {
      setApiKey('');
      queryClient.invalidateQueries({ queryKey: ['auth/me'] });
      onSuccess();
    },
    onError: () => {
      setApiKey('');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    stepUpMutation.mutate(apiKey);
  };

  const handleCancel = () => {
    setApiKey('');
    stepUpMutation.reset();
    onCancel();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 className="text-lg font-semibold text-gray-900">Step-Up Verification</h3>
        <p className="mt-2 text-sm text-gray-600">
          This action requires additional verification. Enter your API key to proceed.
        </p>
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Enter your API key"
            autoComplete="off"
            data-testid="step-up-input"
            className="mt-4 w-full px-3 py-2 border rounded text-sm"
          />
          {stepUpMutation.isError && (
            <p className="mt-2 text-sm text-red-600" data-testid="step-up-error">
              {(stepUpMutation.error as any)?.response?.data?.detail || 'Step-up verification failed'}
            </p>
          )}
          <div className="mt-6 flex justify-end gap-3">
            <button
              type="button"
              onClick={handleCancel}
              disabled={stepUpMutation.isPending}
              className="px-4 py-2 text-sm font-medium border rounded hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!apiKey.trim() || stepUpMutation.isPending}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {stepUpMutation.isPending ? 'Verifying...' : 'Verify'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
