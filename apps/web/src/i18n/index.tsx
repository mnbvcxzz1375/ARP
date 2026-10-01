/**
 * React layer of the self-hosted AgentNet i18n core.
 *
 * Exports:
 * - I18nProvider: wraps the app; resolves the locale from the signed-in
 *   user's backend preference (useAuth /me `locale` field), localStorage,
 *   navigator.language, and finally 'en'. Must live inside
 *   QueryClientProvider because it reads the auth query.
 * - useT() / useI18n(): translate + switch locale.
 * - useFormat(): locale-aware date/number formatting for pages replacing
 *   scattered toLocaleString calls.
 *
 * Components rendered without a provider still work: they bind to the
 * module-level store (see core.ts) so existing tests that render layouts
 * standalone keep asserting English.
 */

import { createContext, useContext, useEffect, useMemo, useSyncExternalStore } from 'react';
import { useAuth } from '../hooks/useAuth';
import {
  DEFAULT_LOCALE,
  getLocale,
  resolveBaseLocale,
  setLocale,
  subscribe,
  syncLocale,
  translate,
} from './core';
import type { Locale, TFunction, TranslateParams } from './types';

// Route-level lazy loaders (App.tsx) import the loading helpers from
// './i18n/core' directly: this file is a React module and re-exporting
// plain functions here trips react-refresh's only-export-components rule.

export interface I18nContextValue {
  /** Active locale. */
  locale: Locale;
  /** Translate: `t('nav.item.agents', { count: 3 })`. */
  t: TFunction;
  /** Switch locale (persists to localStorage, sets <html lang>). */
  setLocale: (locale: Locale) => void;
  /** Locale-aware formatters (see useFormat). */
  format: ReturnType<typeof buildFormat>;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function buildT(locale: Locale): TFunction {
  return (key: string, params?: TranslateParams) => translate(locale, key, params);
}

/** Locale-aware formatting helpers bound to one locale. */
export function buildFormat(locale: Locale) {
  return {
    /** e.g. '2024/3/1' (zh) / '3/1/2024' (en). */
    formatDate(date: Date | string | number, options?: Intl.DateTimeFormatOptions): string {
      const value = date instanceof Date ? date : new Date(date);
      return value.toLocaleDateString(locale, options);
    },
    /** Replacement for bare `toLocaleString()` calls. */
    formatDateTime(date: Date | string | number, options?: Intl.DateTimeFormatOptions): string {
      const value = date instanceof Date ? date : new Date(date);
      return value.toLocaleString(locale, options);
    },
    /** e.g. '1,234'. */
    formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
      return value.toLocaleString(locale, options);
    },
  };
}

function useStoreLocale(): Locale {
  return useSyncExternalStore(subscribe, getLocale, () => DEFAULT_LOCALE);
}

/** Context-less fallback: binds straight to the module store. */
function useFallbackI18n(): I18nContextValue {
  const locale = useStoreLocale();
  return useMemo(
    () => ({ locale, t: buildT(locale), setLocale, format: buildFormat(locale) }),
    [locale],
  );
}

/**
 * Locale resolution, in priority order:
 *   1. signed-in user's backend preference (GET /me `locale`, 'en'|'zh'|null)
 *   2. localStorage 'agentnet-locale'
 *   3. navigator.language
 *   4. 'en'
 *
 * The backend preference is only honored while it does not contradict a
 * manual pick made this session (core.syncLocale tracks that flag); a
 * manual switch still persists to localStorage and wins until reload.
 */
export function I18nProvider({ children }: { children: React.ReactNode }) {
  const storeLocale = useStoreLocale();
  const { data } = useAuth();

  const preferred = data?.locale ?? null;
  const target = preferred ?? resolveBaseLocale();

  useEffect(() => {
    syncLocale(target);
  }, [target]);

  const value = useMemo<I18nContextValue>(
    () => ({ locale: storeLocale, t: buildT(storeLocale), setLocale, format: buildFormat(storeLocale) }),
    [storeLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const fallback = useFallbackI18n();
  const context = useContext(I18nContext);
  return context ?? fallback;
}

export function useT(): TFunction {
  return useI18n().t;
}

export function useFormat() {
  return useI18n().format;
}
