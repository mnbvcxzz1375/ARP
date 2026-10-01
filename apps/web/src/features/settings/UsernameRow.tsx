import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import { useT } from '../../i18n';
import { PixButton } from '../connections/pixel-ui';
import { PIXEL_INPUT } from '../connections/pixel-ui';
import { cn } from '../../lib/utils';

/**
 * Editable username row for the settings account panel.
 *
 * The username is a NON-unique display label (backend migration 0030):
 * renaming never collides with another user, and the account itself is
 * identified by the user_id shown below this row. Saving PATCHes
 * /v1/dashboard/auth/me/profile (CSRF header is attached by the shared
 * axios client) and invalidates the auth query so the shell sidebar
 * picks up the new name.
 */
export default function UsernameRow() {
  const t = useT();
  const { data } = useAuth();
  const queryClient = useQueryClient();
  const current = data?.username ?? '';
  const [value, setValue] = useState(current);

  // Re-sync the local input when the server value changes (e.g. after
  // another session renamed the account).
  useEffect(() => {
    setValue(current);
  }, [current]);

  const mutation = useMutation({
    mutationFn: (username: string) =>
      api
        .patch('/v1/dashboard/auth/me/profile', { username })
        .then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth/me'] });
    },
  });

  const trimmed = value.trim();
  const dirty = trimmed !== current && trimmed.length > 0;
  const errorMsg = mutation.error
    ? t('settings.account.username.error')
    : null;

  return (
    <div
      data-testid="settings-username"
      className="flex flex-col gap-2 border-b-2 border-pixel-line px-4 py-3 last:border-b-0 sm:flex-row sm:items-start sm:gap-4"
    >
      <dt className="min-w-[7.5rem] flex-none font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">
        {t('settings.account.username.label')}
      </dt>
      <dd className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            maxLength={128}
            aria-label={t('settings.account.username.label')}
            placeholder={t('settings.account.username.placeholder')}
            className={cn(PIXEL_INPUT, 'w-full sm:w-56')}
          />
          <PixButton
            onClick={() => mutation.mutate(trimmed)}
            disabled={!dirty || mutation.isPending}
          >
            {mutation.isPending
              ? t('settings.account.username.saving')
              : t('settings.account.username.save')}
          </PixButton>
        </div>
        {mutation.isSuccess && !dirty && (
          <p className="text-base text-pixel-accent-2" data-testid="settings-username-saved">
            {t('settings.account.username.saved')}
          </p>
        )}
        {errorMsg && (
          <p
            className="font-pixel text-pixel-sm text-pixel-led-red"
            data-testid="settings-username-error"
          >
            {errorMsg}
          </p>
        )}
        <p className="text-base text-pixel-muted">
          {t('settings.account.username.hint')}
        </p>
      </dd>
    </div>
  );
}
