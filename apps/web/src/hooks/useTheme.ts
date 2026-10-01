import { useCallback, useEffect, useState } from 'react';

/**
 * Theme controller for the pixel design system.
 *
 * Dark is the default (Chromatic-inspired console). The light variant is
 * respected automatically through `prefers-color-scheme: light`, and the
 * user can override it manually; the choice is persisted in localStorage
 * and applied as a `theme-light` / `theme-dark` class on <html>.
 *
 * Theme is locked once per page (document root). Sections never invert
 * locally - see the design system doc.
 */

export type PixelTheme = 'dark' | 'light';

const STORAGE_KEY = 'agentnet-theme';

function resolveInitialTheme(): PixelTheme {
  if (typeof window === 'undefined') return 'dark';
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    // localStorage unavailable (private mode etc.): fall through to media.
  }
  if (window.matchMedia?.('(prefers-color-scheme: light)').matches) {
    return 'light';
  }
  return 'dark';
}

export function useTheme() {
  const [theme, setTheme] = useState<PixelTheme>(resolveInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('theme-light', 'theme-dark');
    root.classList.add(theme === 'light' ? 'theme-light' : 'theme-dark');
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Ignore write failures - auto detection still applies on next load.
    }
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'));
  }, []);

  return { theme, toggleTheme, setTheme };
}
