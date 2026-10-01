import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/client';
import { useT } from '../i18n';

interface StepUpDialogProps {
  open: boolean;
  onSuccess: () => void;
  onCancel: () => void;
}

export default function StepUpDialog({ open, onSuccess, onCancel }: StepUpDialogProps) {
  const [apiKey, setApiKey] = useState('');
  const queryClient = useQueryClient();
  const t = useT();

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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#191a26]/70"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-md p-6 mx-4 bg-pixel-surface border-2 border-pixel-fg shadow-pixel">
        <h3 className="font-display text-pixel-lg text-pixel-fg">{t('common.stepUp.title')}</h3>
        <p className="mt-3 text-lg text-pixel-muted">{t('common.stepUp.description')}</p>
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={t('common.stepUp.placeholder')}
            autoComplete="off"
            data-testid="step-up-input"
            className="mt-4 w-full px-3 py-2 text-lg font-mono text-pixel-fg placeholder:text-pixel-muted bg-pixel-bg border-2 border-pixel-line focus:border-pixel-accent-2"
          />
          {stepUpMutation.isError && (
            // Solid LED-red chip: #ac3232 text on bg-pixel-surface was only
            // ~2.46:1 (AA fail). Chip measures ~6.1:1 in both themes.
            <p
              className="mt-2 inline-block px-2 py-1 text-sm font-pixel bg-pixel-led-red text-[#f4f4fa]"
              data-testid="step-up-error"
            >
              {(stepUpMutation.error as any)?.response?.data?.detail || t('common.stepUp.error')}
            </p>
          )}
          <div className="flex justify-end gap-3 mt-6">
            <button
              type="button"
              onClick={handleCancel}
              disabled={stepUpMutation.isPending}
              className="min-h-[44px] px-4 py-2 font-pixel text-pixel-base border-2 border-pixel-line text-pixel-fg hover:bg-pixel-raised disabled:opacity-50"
            >
              {t('common.action.cancel')}
            </button>
            <button
              type="submit"
              disabled={!apiKey.trim() || stepUpMutation.isPending}
              className="min-h-[44px] px-4 py-2 font-pixel text-pixel-base border-2 border-[#191a26] bg-pixel-accent text-[#191a26] disabled:opacity-50"
            >
              {stepUpMutation.isPending ? t('common.stepUp.verifying') : t('common.stepUp.verify')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
