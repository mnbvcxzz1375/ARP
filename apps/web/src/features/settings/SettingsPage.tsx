import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { KeyRound, LogOut } from 'lucide-react';
import { useAuth, useLogout } from '../../hooks/useAuth';
import { usePreferences } from '../../hooks/usePreferences';
import { useTheme, type PixelTheme } from '../../hooks/useTheme';
import { useFormat, useI18n, useT } from '../../i18n';
import type { Locale } from '../../i18n/types';
import LoadingState from '../../components/LoadingState';
import { ErrorBanner, PageTitle, PixelPanel, PixButton } from '../connections/pixel-ui';
import UsernameRow from './UsernameRow';

/**
 * Settings center (pixel design system).
 *
 * Two pixel panels:
 * - Appearance: theme (dark/light segmented control), language (EN/中文
 *   segmented control, same native labels as the shell LanguageSwitcher),
 *   font size scale, reduced-motion switch.
 * - Account: username / role / user_id from `useAuth`, session expiry and
 *   step-up window, an entry to /app/api-keys and the sign-out action.
 *
 * Persistence: logged-in changes are PATCHed to
 * /v1/dashboard/auth/me/preferences via `usePreferences` (optimistic, so the
 * change is visible immediately) and also applied locally, matching the
 * resolution priority server > local used by useTheme / useI18n.
 *
 * Note on the reduced-motion switch: index.css only honors the
 * `prefers-reduced-motion` media query, which a manual toggle cannot flip.
 * This shard may not edit the shared stylesheet, so the toggle mirrors the
 * media-query block with a managed <style> element instead.
 *
 * The pixel font sizes are px-based (tailwind.config.ts type scale), so a
 * root font-size change would leave the labels untouched; font scaling is
 * therefore applied as a document zoom, the only effective lever here.
 */

const FONT_SCALES = [0.8, 0.9, 1, 1.1, 1.25, 1.5] as const;
const THEME_OPTIONS: PixelTheme[] = ['dark', 'light'];
const LANGUAGE_OPTIONS: Locale[] = ['en', 'zh'];

const REDUCED_MOTION_STYLE_ID = 'agentnet-reduced-motion';
const REDUCED_MOTION_STYLE = `
.pixel-scanlines, .pixel-rgb-stripes { display: none !important; }
.chromatic { text-shadow: none !important; }
*, *::before, *::after {
  animation-duration: 0ms !important;
  animation-iteration-count: 1 !important;
  transition-duration: 0ms !important;
}
`;

/** Role enum -> translation key; unknown roles fall back to the raw value. */
const ROLE_LABEL_KEYS: Record<string, string> = {
  user: 'settings.account.role.user',
  admin: 'settings.account.role.admin',
  super_admin: 'settings.account.role.superAdmin',
};

function systemPrefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function AccountRow({
  label,
  value,
  mono,
  testId,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
  testId?: string;
}) {
  return (
    <div
      data-testid={testId}
      className="flex flex-col gap-1 border-b-2 border-pixel-line px-4 py-3 last:border-b-0 sm:flex-row sm:items-start sm:gap-4"
    >
      <dt className="min-w-[7.5rem] flex-none font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">
        {label}
      </dt>
      <dd className={`min-w-0 break-all text-pixel-fg ${mono ? 'font-mono text-base' : 'text-lg'}`}>
        {value}
      </dd>
    </div>
  );
}

interface OptionRowProps<T> {
  groupLabel: string;
  testIdPrefix: string;
  options: readonly T[];
  selected: T;
  optionLabel: (option: T) => string;
  onSelect: (option: T) => void;
}

/**
 * Pixel segmented control row: 2px hard borders, accent solid block marks
 * the active segment (#191a26 text = 5.36:1 in both themes), 44px targets,
 * wraps instead of overflowing at 375px.
 */
function OptionRow<T extends string | number>({
  groupLabel,
  testIdPrefix,
  options,
  selected,
  optionLabel,
  onSelect,
}: OptionRowProps<T>) {
  return (
    <div
      role="group"
      aria-label={groupLabel}
      className="flex flex-wrap w-fit max-w-full border-2 border-pixel-line"
    >
      {options.map((option) => {
        const active = option === selected;
        return (
          <button
            key={String(option)}
            type="button"
            aria-pressed={active}
            data-testid={`${testIdPrefix}-${option}`}
            onClick={() => onSelect(option)}
            className={`flex items-center justify-center min-h-[44px] min-w-[44px] px-3 font-pixel text-pixel-sm border-r-2 border-pixel-line last:border-r-0 ${
              active
                ? 'bg-pixel-accent text-[#191a26]'
                : 'text-pixel-muted hover:bg-pixel-raised hover:text-pixel-fg'
            }`}
          >
            {optionLabel(option)}
          </button>
        );
      })}
    </div>
  );
}

export default function SettingsPage() {
  const t = useT();
  const { formatDateTime } = useFormat();
  const { locale, setLocale } = useI18n();
  const { data: user } = useAuth();
  const {
    data: prefs,
    isLoading,
    isError,
    isSaving,
    saveError,
    patchPreferences,
  } = usePreferences();
  const { theme: localTheme, setTheme } = useTheme();
  const logoutMutation = useLogout();
  const navigate = useNavigate();

  // Resolution priority: server preference > local.
  const effectiveTheme: PixelTheme = prefs?.theme ?? localTheme;
  // The chip reflects the locale the UI actually renders in: the i18n
  // store already resolved server preference > localStorage > browser
  // (I18nProvider syncs it from the auth query).
  const effectiveLocale: Locale = locale;
  const fontScale = prefs?.fontScale ?? 1;
  const reducedMotion = prefs?.reducedMotion ?? systemPrefersReducedMotion();
  const role = user?.role ?? '';
  const roleLabel = ROLE_LABEL_KEYS[role] ? t(ROLE_LABEL_KEYS[role]) : role;

  // Server theme preference wins: sync <html> class + localStorage when the
  // two disagree (write-local on switch, per the settings contract).
  useEffect(() => {
    if (effectiveTheme !== localTheme) {
      setTheme(effectiveTheme);
    }
  }, [effectiveTheme, localTheme, setTheme]);

  // Font size scale: document zoom (pixel type scale is px-based).
  // CSS zoom does NOT rescale viewport units, so a 100dvh-tall layout
  // renders 10% taller than the window at 110% zoom and clips anything
  // pinned to the bottom (the console sidebar footer). Expose a
  // zoom-adjusted height for viewport-filling containers.
  useEffect(() => {
    const root = document.documentElement;
    root.style.zoom = fontScale === 1 ? '' : String(fontScale);
    root.style.setProperty(
      '--app-vh',
      fontScale === 1 ? '' : `${100 / fontScale}dvh`,
    );
  }, [fontScale]);

  // Reduced motion: managed <style> mirrors the index.css media-query block.
  useEffect(() => {
    if (!reducedMotion) {
      document.getElementById(REDUCED_MOTION_STYLE_ID)?.remove();
      return;
    }
    if (!document.getElementById(REDUCED_MOTION_STYLE_ID)) {
      const style = document.createElement('style');
      style.id = REDUCED_MOTION_STYLE_ID;
      style.textContent = REDUCED_MOTION_STYLE;
      document.head.appendChild(style);
    }
  }, [reducedMotion]);

  if (isLoading) return <LoadingState />;

  const handleTheme = (next: PixelTheme) => {
    setTheme(next); // optimistic local apply
    patchPreferences({ preferences: { theme: next } });
  };

  const handleLocale = (next: Locale) => {
    setLocale(next); // optimistic local apply (session manual override)
    patchPreferences({ locale: next });
  };

  const handleFontScale = (next: number) => {
    patchPreferences({ preferences: { fontScale: next } });
  };

  const handleReducedMotion = () => {
    patchPreferences({ preferences: { reducedMotion: !reducedMotion } });
  };

  const handleLogout = () => {
    logoutMutation.mutate(undefined, {
      onSuccess: () => navigate('/login'),
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <PageTitle>{t('settings.title')}</PageTitle>
      <p className="-mt-2 text-lg text-pixel-muted">{t('settings.description')}</p>

      {/* ================================================================ */}
      {/* Appearance */}
      {/* ================================================================ */}
      {/* PixelPanel does not forward arbitrary props (no data-testid), so the
          testid rides on a wrapper div. */}
      <div data-testid="settings-appearance-panel">
        <PixelPanel title={t('settings.appearance.title')} bodyClassName="p-4">
          <div className="flex flex-col gap-6">
          {isError && <ErrorBanner message={t('settings.error.load')} />}
          {saveError != null && <ErrorBanner message={t('settings.error.save')} />}

          {/* Theme: dark/light segmented control. */}
          <div className="flex flex-col gap-2">
            <span className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">
              {t('settings.appearance.theme.label')}
            </span>
            <OptionRow<PixelTheme>
              groupLabel={t('settings.appearance.theme.aria')}
              testIdPrefix="settings-theme"
              options={THEME_OPTIONS}
              selected={effectiveTheme}
              optionLabel={(option) =>
                option === 'dark'
                  ? t('settings.appearance.theme.dark')
                  : t('settings.appearance.theme.light')
              }
              onSelect={handleTheme}
            />
          </div>

          {/* Language: EN / 中文 (native labels, as in the shell switcher). */}
          <div className="flex flex-col gap-2">
            <span className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">
              {t('settings.appearance.language.label')}
            </span>
            <OptionRow<Locale>
              groupLabel={t('settings.appearance.language.label')}
              testIdPrefix="settings-language"
              options={LANGUAGE_OPTIONS}
              selected={effectiveLocale}
              optionLabel={(option) => (option === 'zh' ? '中文' : 'EN')}
              onSelect={handleLocale}
            />
            <p className="text-base text-pixel-muted">
              {t('settings.appearance.language.description')}
            </p>
          </div>

          {/* Font size scale. */}
          <div className="flex flex-col gap-2">
            <span className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">
              {t('settings.appearance.fontScale.label')}
            </span>
            <OptionRow<number>
              groupLabel={t('settings.appearance.fontScale.aria')}
              testIdPrefix="settings-font-scale"
              options={FONT_SCALES}
              selected={fontScale}
              optionLabel={(option) =>
                t('settings.appearance.fontScale.percent', {
                  value: Math.round(option * 100),
                })
              }
              onSelect={handleFontScale}
            />
          </div>

          {/* Reduced motion switch. */}
          <div className="flex flex-col gap-2">
            <span className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">
              {t('settings.appearance.reducedMotion.label')}
            </span>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
              <button
                type="button"
                role="switch"
                aria-checked={reducedMotion}
                data-testid="settings-reduced-motion"
                onClick={handleReducedMotion}
                disabled={isSaving}
                className={`flex min-h-[44px] min-w-[88px] items-center justify-center border-2 border-pixel-line px-4 font-pixel text-pixel-sm ${
                  reducedMotion
                    ? 'bg-pixel-accent text-[#191a26] border-[#191a26]'
                    : 'text-pixel-muted hover:bg-pixel-raised hover:text-pixel-fg'
                }`}
              >
                {reducedMotion
                  ? t('settings.appearance.reducedMotion.on')
                  : t('settings.appearance.reducedMotion.off')}
              </button>
              <p className="min-w-0 flex-1 text-base text-pixel-muted">
                {t('settings.appearance.reducedMotion.description')}
              </p>
            </div>
          </div>
        </div>
        </PixelPanel>
      </div>

      {/* ================================================================ */}
      {/* Account */}
      {/* ================================================================ */}
      <div data-testid="settings-account-panel">
        <PixelPanel title={t('settings.account.title')} bodyClassName="p-0">
          <dl className="flex flex-col">
          <UsernameRow />
          <AccountRow
            testId="settings-role"
            label={t('settings.account.role.label')}
            value={roleLabel || role}
          />
          <AccountRow
            testId="settings-user-id"
            label={t('settings.account.userId.label')}
            value={user?.user_id ?? ''}
            mono
          />
          <AccountRow
            testId="settings-session-expires"
            label={t('settings.account.sessionExpires.label')}
            value={
              user?.session_expires_at
                ? formatDateTime(user.session_expires_at)
                : t('settings.account.stepUpUntil.none')
            }
          />
          <AccountRow
            testId="settings-step-up-until"
            label={t('settings.account.stepUpUntil.label')}
            value={
              user?.step_up_until
                ? formatDateTime(user.step_up_until)
                : t('settings.account.stepUpUntil.none')
            }
          />
        </dl>

        <div className="flex flex-col gap-3 border-t-2 border-pixel-line p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="min-w-0 text-base text-pixel-muted">
            {t('settings.account.apiKeys.description')}
          </p>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/app/api-keys"
              data-testid="settings-api-keys-link"
              className="inline-flex items-center justify-center min-h-[44px] px-4 py-2 font-pixel text-pixel-base bg-pixel-surface text-pixel-fg border-2 border-pixel-line hover:bg-pixel-raised"
            >
              <KeyRound size={16} strokeWidth={2} className="mr-2 flex-none" />
              {t('settings.account.apiKeys.link')}
            </Link>
            <PixButton
              variant="danger"
              onClick={handleLogout}
              data-testid="settings-logout"
              disabled={logoutMutation.isPending}
            >
              <LogOut size={16} strokeWidth={2} className="mr-2 flex-none" />
              {t('settings.account.logout')}
            </PixButton>
          </div>
        </div>
        </PixelPanel>
      </div>
    </div>
  );
}
