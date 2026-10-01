import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../test-utils';

// Mocked auth: the provider reads the backend locale preference from it.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
  useLogout: vi.fn(() => ({ mutate: vi.fn() })),
}));

import { useAuth } from '../../hooks/useAuth';
import { I18nProvider, useI18n, useFormat } from '../index';
import {
  CATALOG,
  DEFAULT_LOCALE,
  LOCALE_STORAGE_KEY,
  __resetI18n,
  getLocale,
  hasNamespace,
  interpolate,
  loadNamespace,
  localeFromBrowserTag,
  missingNamespacesFor,
  registerMessages,
  resolveBaseLocale,
  resolveLocale,
  setLocale,
  subscribe,
  translate,
} from '../core';

/** Renders inside I18nProvider exactly like main.tsx does. */
function renderWithProvider(ui: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting>
        <I18nProvider>{ui}</I18nProvider>
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

/** Component that exposes the i18n state + a manual switch button. */
function Probe() {
  const { locale, t, setLocale } = useI18n();
  return (
    <div>
      <span data-testid="probe-locale">{locale}</span>
      <span data-testid="probe-submit">{t('common.login.submit')}</span>
      <span data-testid="probe-interpolated">{t('common.pagination.page', { current: 2, total: 5 })}</span>
      <button type="button" onClick={() => setLocale('zh')} data-testid="switch-to-zh">
        zh
      </button>
    </div>
  );
}

function FormatProbe() {
  const { formatDate, formatNumber } = useFormat();
  return (
    <div>
      <span data-testid="probe-date">{formatDate(new Date('2024-03-01T12:00:00Z'))}</span>
      <span data-testid="probe-number">{formatNumber(1234567)}</span>
    </div>
  );
}

const ANON_AUTH = { data: undefined, isLoading: false, isError: true, error: null };

describe('i18n core', () => {
  beforeEach(() => {
    localStorage.clear();
    __resetI18n();
    vi.mocked(useAuth).mockReturnValue(ANON_AUTH as any);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('catalog auto-gathering', () => {
    it('gathers every en/zh namespace file via import.meta.glob', () => {
      // Namespaces are added per feature shard (public/auth/overview/...); the
      // core contract is that the infra namespaces are always present and the
      // two locales expose the same namespace set.
      const enNamespaces = Object.keys(CATALOG.en).sort();
      const zhNamespaces = Object.keys(CATALOG.zh).sort();
      for (const ns of ['common', 'nav', 'shell']) {
        expect(enNamespaces, `en catalog must include the '${ns}' namespace`).toContain(ns);
        expect(zhNamespaces, `zh catalog must include the '${ns}' namespace`).toContain(ns);
      }
      expect(zhNamespaces).toEqual(enNamespaces);
    });

    it('every zh key has an en counterpart (no half-translated namespaces)', () => {
      for (const [namespace, messages] of Object.entries(CATALOG.zh)) {
        for (const key of Object.keys(messages)) {
          expect(CATALOG.en[namespace]?.[key], `zh key ${namespace}.${key} missing in en`).toBeDefined();
        }
      }
    });
  });

  describe('interpolation', () => {
    it('replaces {{param}} placeholders', () => {
      expect(interpolate('Page {{current}} of {{total}}', { current: 2, total: 5 })).toBe('Page 2 of 5');
    });

    it('translates with params via t()', () => {
      expect(translate(DEFAULT_LOCALE, 'common.pagination.page', { current: 2, total: 5 })).toBe(
        'Page 2 of 5',
      );
    });

    it('leaves unknown placeholders untouched', () => {
      expect(interpolate('Page {{current}}', {})).toBe('Page {{current}}');
    });
  });

  describe('fallback behavior', () => {
    it('falls back to English when the key is missing in the active locale', () => {
      const zhCommon = CATALOG.zh.common;
      const saved = zhCommon['login.submit'];
      delete zhCommon['login.submit'];
      try {
        expect(translate('zh', 'common.login.submit')).toBe('Sign In');
      } finally {
        zhCommon['login.submit'] = saved;
      }
    });

    it('returns the key and warns when the key is missing from every locale', () => {
      const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
      expect(translate('zh', 'common.login.doesNotExist')).toBe('common.login.doesNotExist');
      expect(warn).toHaveBeenCalledWith(expect.stringContaining('common.login.doesNotExist'));
    });

    it('warns on keys without a namespace segment', () => {
      const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
      expect(translate('en', 'nope')).toBe('nope');
      expect(warn).toHaveBeenCalled();
    });
  });

  describe('locale resolution', () => {
    it('priority: backend preference > localStorage > navigator.language > en', () => {
      expect(resolveLocale('zh', 'en', 'en')).toBe('zh');
      expect(resolveLocale(null, 'zh', 'en')).toBe('zh');
      expect(resolveLocale(null, null, 'zh')).toBe('zh');
      expect(resolveLocale(null, null, 'en')).toBe('en');
    });

    it('ignores invalid values in any slot', () => {
      expect(resolveLocale('fr' as any, 'de' as any, 'en')).toBe('en');
    });

    it('maps browser tags to supported locales', () => {
      expect(localeFromBrowserTag('zh-CN')).toBe('zh');
      expect(localeFromBrowserTag('zh-TW')).toBe('zh');
      expect(localeFromBrowserTag('en-US')).toBe('en');
      expect(localeFromBrowserTag('fr-FR')).toBe('en');
      expect(localeFromBrowserTag(undefined)).toBe('en');
    });

    it('resolveBaseLocale reads localStorage over navigator.language', () => {
      localStorage.setItem(LOCALE_STORAGE_KEY, 'zh');
      expect(resolveBaseLocale()).toBe('zh');
    });

    it('defaults to en with no stored preference and an English browser', () => {
      expect(resolveBaseLocale()).toBe('en');
    });

    it('falls back to navigator.language when nothing is stored', () => {
      Object.defineProperty(window, 'navigator', { value: { language: 'zh-CN' }, configurable: true });
      try {
        expect(resolveBaseLocale()).toBe('zh');
      } finally {
        Object.defineProperty(window, 'navigator', { value: { language: 'en-US' }, configurable: true });
      }
    });
  });

  describe('I18nProvider', () => {
    it('defaults to en and translates', () => {
      renderWithProvider(<Probe />);
      expect(screen.getByTestId('probe-locale')).toHaveTextContent('en');
      expect(screen.getByTestId('probe-submit')).toHaveTextContent('Sign In');
    });

    it('switching locale re-renders, persists to localStorage and sets <html lang>', async () => {
      const user = userEvent.setup();
      renderWithProvider(<Probe />);
      await user.click(screen.getByTestId('switch-to-zh'));
      expect(screen.getByTestId('probe-locale')).toHaveTextContent('zh');
      expect(screen.getByTestId('probe-submit')).toHaveTextContent('登录');
      expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('zh');
      expect(document.documentElement.lang).toBe('zh');
    });

    it('honor the backend preference (auth /me.locale) over localStorage', () => {
      localStorage.setItem(LOCALE_STORAGE_KEY, 'en');
      vi.mocked(useAuth).mockReturnValue({
        data: { user_id: 'u1', username: 'alice', role: 'user', locale: 'zh' },
        isLoading: false,
        isError: false,
        error: null,
      } as any);
      renderWithProvider(<Probe />);
      expect(screen.getByTestId('probe-locale')).toHaveTextContent('zh');
      expect(screen.getByTestId('probe-submit')).toHaveTextContent('登录');
    });

    it('falls back through localStorage when the backend preference is null', () => {
      localStorage.setItem(LOCALE_STORAGE_KEY, 'zh');
      vi.mocked(useAuth).mockReturnValue({
        data: { user_id: 'u1', username: 'alice', role: 'user', locale: null },
        isLoading: false,
        isError: false,
        error: null,
      } as any);
      renderWithProvider(<Probe />);
      expect(screen.getByTestId('probe-locale')).toHaveTextContent('zh');
    });

    it('respects a manual switch made this session over the backend preference', async () => {
      vi.mocked(useAuth).mockReturnValue({
        data: { user_id: 'u1', username: 'alice', role: 'user', locale: 'zh' },
        isLoading: false,
        isError: false,
        error: null,
      } as any);
      renderWithProvider(<Probe />);
      expect(screen.getByTestId('probe-locale')).toHaveTextContent('zh');
      // Manual override back to en (localStorage now says en, backend says zh).
      act(() => {
        setLocale('en');
      });
      expect(screen.getByTestId('probe-locale')).toHaveTextContent('en');
      expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('en');
    });

    it('useFormat follows the active locale', async () => {
      const user = userEvent.setup();
      renderWithProvider(
        <>
          <Probe />
          <FormatProbe />
        </>,
      );
      // en: month/day/year. Timezone-invariant shape assertions.
      expect(screen.getByTestId('probe-date').textContent).toMatch(/^\d+\/\d+\/2024$/);
      await user.click(screen.getByTestId('switch-to-zh'));
      // zh: year/month/day.
      expect(screen.getByTestId('probe-date').textContent).toMatch(/^2024\/\d+\/\d+$/);
      expect(screen.getByTestId('probe-number')).toHaveTextContent('1,234,567');
    });
  });

  describe('provider-less usage', () => {
    it('useI18n works without a provider (existing standalone tests rely on en)', () => {
      render(<Probe />);
      expect(screen.getByTestId('probe-locale')).toHaveTextContent('en');
      expect(screen.getByTestId('probe-submit')).toHaveTextContent('Sign In');
    });
  });

  describe('lazy namespace loading', () => {
    it('keeps the infra namespaces eager in every environment', () => {
      for (const ns of ['common', 'nav', 'shell']) {
        expect(hasNamespace('en', ns), `en must eagerly load ${ns}`).toBe(true);
        expect(hasNamespace('zh', ns), `zh must eagerly load ${ns}`).toBe(true);
      }
    });

    it('loadNamespace resolves without side effects when the namespace is present', async () => {
      await expect(loadNamespace('en', 'common')).resolves.toBeUndefined();
      await expect(loadNamespace('zh', 'common')).resolves.toBeUndefined();
    });

    it('registerMessages merges a namespace, notifies subscribers and keeps the en fallback', () => {
      const warns = vi.spyOn(console, 'warn').mockImplementation(() => {});
      let notifications = 0;
      const unsubscribe = subscribe(() => {
        notifications += 1;
      });
      try {
        const saved = CATALOG.zh.featuretest;
        delete CATALOG.zh.featuretest;
        registerMessages('zh', 'featuretest', { title: '测试标题' });
        expect(hasNamespace('zh', 'featuretest')).toBe(true);
        expect(translate('zh', 'featuretest.title')).toBe('测试标题');
        expect(notifications).toBeGreaterThan(0);
        // English never had the namespace: the key falls through with a warn.
        expect(translate('en', 'featuretest.title')).toBe('featuretest.title');
        if (saved === undefined) delete CATALOG.zh.featuretest;
        else CATALOG.zh.featuretest = saved;
      } finally {
        unsubscribe();
        warns.mockRestore();
      }
    });

    it('missingNamespacesFor reports namespaces loaded for another locale but absent in the target', () => {
      const saved = CATALOG.zh.agents;
      delete CATALOG.zh.agents;
      try {
        expect(missingNamespacesFor('zh')).toContain('agents');
        expect(missingNamespacesFor('en')).toEqual([]);
      } finally {
        CATALOG.zh.agents = saved;
      }
    });

    it('setLocale applies synchronously when no namespace is missing', () => {
      act(() => setLocale('zh'));
      expect(getLocale()).toBe('zh');
      act(() => setLocale('en'));
      expect(getLocale()).toBe('en');
    });

    it('setLocale keeps the old locale until the missing namespace load lands', async () => {
      const saved = CATALOG.zh.agents;
      delete CATALOG.zh.agents;
      const warns = vi.spyOn(console, 'warn').mockImplementation(() => {});
      try {
        act(() => setLocale('zh'));
        // The switch is deferred while the on-demand load is in flight, so
        // nothing renders a raw key in the meantime.
        await act(async () => {
          await waitFor(() => expect(getLocale()).toBe('zh'));
        });
        expect(getLocale()).toBe('zh');
      } finally {
        CATALOG.zh.agents = saved;
        warns.mockRestore();
        act(() => setLocale('en'));
      }
    });
  });
});
