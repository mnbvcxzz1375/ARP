import { Languages } from 'lucide-react';
import { useI18n, useT } from '../i18n';
import type { Locale } from '../i18n/types';

/**
 * Segmented language chip (pixel design system): EN | 中文.
 *
 * - font-pixel (Pixelify Sans), 2px hard pixel border.
 * - The only accent color (#df7126 / bg-pixel-accent) highlights the
 *   active segment, with #191a26 text (5.34:1 in both themes, AA).
 * - Each segment is a 44px minimum touch target.
 * - Mounted in the DashboardShell footer and the PublicLayout footer.
 *
 * The collapsed sidebar is only 4rem wide - the EN | 中文 chip (min
 * 88px + borders) overflows and gets clipped by the aside's
 * overflow-hidden there. The `compact` variant renders a single 44px
 * button with a globe icon that toggles to the other locale instead.
 *
 * Locale labels are intentionally native names ('EN' / '中文') in both
 * locales - a user must be able to recognize their own language.
 */
const OPTIONS: { value: Locale; key: string }[] = [
  { value: 'en', key: 'shell.language.en' },
  { value: 'zh', key: 'shell.language.zh' },
];

export default function LanguageSwitcher({
  className = '',
  compact = false,
}: {
  className?: string;
  compact?: boolean;
}) {
  const { locale, setLocale } = useI18n();
  const t = useT();

  if (compact) {
    const other = OPTIONS.find((o) => o.value !== locale) ?? OPTIONS[0];
    return (
      <button
        type="button"
        onClick={() => setLocale(other.value)}
        aria-label={t('shell.language.aria')}
        title={t('shell.language.toggle')}
        data-testid="language-switcher-compact"
        className={`flex items-center justify-center min-h-[44px] min-w-[44px] border-2 border-pixel-line text-pixel-muted hover:bg-pixel-raised hover:text-pixel-fg ${className}`}
      >
        <Languages size={18} strokeWidth={2} aria-hidden="true" />
      </button>
    );
  }

  return (
    <div
      role="group"
      aria-label={t('shell.language.aria')}
      className={`flex border-2 border-pixel-line ${className}`}
      data-testid="language-switcher"
    >
      {OPTIONS.map((option) => {
        const active = locale === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => setLocale(option.value)}
            aria-pressed={active}
            data-testid={`language-option-${option.value}`}
            className={`flex items-center justify-center min-h-[44px] min-w-[44px] px-2 font-pixel text-pixel-sm border-r-2 border-pixel-line last:border-r-0 ${
              active
                ? 'bg-pixel-accent text-[#191a26]'
                : 'text-pixel-muted hover:bg-pixel-raised hover:text-pixel-fg'
            }`}
          >
            {t(option.key)}
          </button>
        );
      })}
    </div>
  );
}
