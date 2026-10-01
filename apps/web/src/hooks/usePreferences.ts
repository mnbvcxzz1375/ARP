import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/client';
import type { PixelTheme } from './useTheme';

/**
 * User preferences (settings center).
 *
 * Contract (apps/api/app/routers/dashboard_auth.py, covered by
 * apps/api/tests/test_user_preferences.py):
 * - GET  /v1/dashboard/auth/me/preferences -> { locale: 'en'|'zh'|null, preferences: {...} }
 * - PATCH /v1/dashboard/auth/me/preferences <- { locale?, preferences? }; absent fields
 *   keep their stored value, `locale: null` clears it. The server only accepts
 *   the appearance keys theme / fontScale / reducedMotion (400 otherwise).
 *
 * NOTE: the task brief stated '/v1/dashboard/me/preferences', but the
 * backend registers the router under the '/v1/dashboard/auth' prefix
 * (router = APIRouter(prefix='/v1/dashboard/auth')), same prefix as the
 * /me endpoint useAuth calls. The hook follows the backend contract.
 *
 * The hook exposes normalized data plus an optimistic `patchPreferences`
 * mutation: the cache is updated immediately so the UI reflects the change
 * before the round-trip, and rolled back on error. The auth query cache
 * (`['auth/me']`, read by I18nProvider for the backend locale preference)
 * is refreshed on success so the resolved locale stays consistent.
 */

export type PreferenceLocale = 'en' | 'zh';

export interface UserPreferences {
  /** Backend locale preference; null = no preference (fall back to local). */
  locale: PreferenceLocale | null;
  /** Backend theme preference; null = no preference (fall back to local). */
  theme: PixelTheme | null;
  /** Document zoom factor; null = no preference (defaults to 1). */
  fontScale: number | null;
  /** Reduced-motion preference; null = no preference (follow the OS hint). */
  reducedMotion: boolean | null;
}

interface RawPreferencesResponse {
  locale: string | null;
  preferences: Record<string, unknown> | null;
}

export interface UpdatePreferencesPayload {
  locale?: PreferenceLocale | null;
  preferences?: {
    theme?: PixelTheme;
    fontScale?: number;
    reducedMotion?: boolean;
  };
}

export const PREFERENCES_QUERY_KEY = ['me/preferences'] as const;

const AUTH_QUERY_KEY = ['auth/me'] as const;

function normalizeTheme(value: unknown): PixelTheme | null {
  return value === 'light' || value === 'dark' ? value : null;
}

function normalize(data: RawPreferencesResponse): UserPreferences {
  const prefs = data.preferences ?? {};
  const fontScale = prefs.fontScale;
  return {
    locale: data.locale === 'en' || data.locale === 'zh' ? data.locale : null,
    theme: normalizeTheme(prefs.theme),
    fontScale: typeof fontScale === 'number' && !Number.isNaN(fontScale) ? fontScale : null,
    reducedMotion: typeof prefs.reducedMotion === 'boolean' ? prefs.reducedMotion : null,
  };
}

/** Merge one patch into a snapshot (absent fields untouched), null-safe. */
function applyPatch(previous: UserPreferences, payload: UpdatePreferencesPayload): UserPreferences {
  const prefs = payload.preferences ?? {};
  return {
    locale: payload.locale !== undefined ? payload.locale : previous.locale,
    theme: prefs.theme !== undefined ? prefs.theme : previous.theme,
    fontScale: prefs.fontScale !== undefined ? prefs.fontScale : previous.fontScale,
    reducedMotion:
      prefs.reducedMotion !== undefined ? prefs.reducedMotion : previous.reducedMotion,
  };
}

export interface UsePreferencesResult {
  data?: UserPreferences;
  isLoading: boolean;
  isError: boolean;
  /** True while a PATCH round-trip is in flight (optimistic update already applied). */
  isSaving: boolean;
  /** Last PATCH error; null while clean / after a successful retry. */
  saveError: unknown;
  /** Fire-and-forget PATCH with an optimistic cache update + error rollback. */
  patchPreferences: (payload: UpdatePreferencesPayload) => void;
}

export function usePreferences(): UsePreferencesResult {
  const queryClient = useQueryClient();
  const [saveError, setSaveError] = useState<unknown>(null);

  const query = useQuery<UserPreferences, Error>({
    queryKey: PREFERENCES_QUERY_KEY,
    queryFn: () =>
      api
        .get<RawPreferencesResponse>('/v1/dashboard/auth/me/preferences')
        .then((r) => normalize(r.data)),
    retry: false,
  });

  const patchMutation = useMutation({
    mutationFn: (payload: UpdatePreferencesPayload) =>
      api
        .patch<RawPreferencesResponse>('/v1/dashboard/auth/me/preferences', payload)
        .then((r) => r.data),
    onMutate: async (payload) => {
      setSaveError(null);
      await queryClient.cancelQueries({ queryKey: PREFERENCES_QUERY_KEY });
      const previous = queryClient.getQueryData<UserPreferences>(PREFERENCES_QUERY_KEY);
      if (previous) {
        queryClient.setQueryData<UserPreferences>(
          PREFERENCES_QUERY_KEY,
          applyPatch(previous, payload),
        );
      }
      return { previous };
    },
    onError: (error, _payload, context) => {
      setSaveError(error);
      // Undo the optimistic update so the UI never shows an unsaved value.
      if (context?.previous) {
        queryClient.setQueryData(PREFERENCES_QUERY_KEY, context.previous);
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData<UserPreferences>(PREFERENCES_QUERY_KEY, normalize(data));
      // Keep the auth query's backend locale in sync: it drives the
      // I18nProvider resolution (server preference > localStorage > browser).
      queryClient.setQueryData(AUTH_QUERY_KEY, (old: unknown) => {
        if (!old || typeof old !== 'object') return old;
        return { ...(old as Record<string, unknown>), locale: data.locale };
      });
    },
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    isSaving: patchMutation.isPending,
    saveError,
    patchPreferences: patchMutation.mutate,
  };
}
