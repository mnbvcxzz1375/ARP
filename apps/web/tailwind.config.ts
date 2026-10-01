import type { Config } from 'tailwindcss';

/**
 * AgentNet pixel design system (Tailwind 3 extension).
 *
 * Single source of truth for color values is src/index.css (:root CSS
 * variables). This config only maps those variables into utility names so
 * the dark/light variants resolve at runtime without rebuilding CSS.
 *
 * Design language: ModRetro Chromatic / GBC hardware inspired pixel UI.
 * - All corners are hard edges (border-radius 0 across the whole scale).
 * - Box shadows are hard pixel steps (no blur), NES.css style.
 * - Fonts are self-hosted via @fontsource (see src/main.tsx).
 */

const cjkFallback = [
  'Microsoft YaHei',
  'Noto Sans CJK SC',
  'PingFang SC',
  'sans-serif',
];

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Pixel design tokens. Values live in src/index.css so the
        // prefers-color-scheme / .theme-light variants can swap them.
        // NOTE: the legacy border/background/foreground HSL mappings were
        // removed; grep found no bg-background/text-foreground/border-border
        // usage in src/, so pixel.* is the only palette.
        pixel: {
          bg: 'var(--pixel-bg)',
          surface: 'var(--pixel-surface)',
          raised: 'var(--pixel-raised)',
          fg: 'var(--pixel-fg)',
          muted: 'var(--pixel-muted)',
          accent: 'var(--pixel-accent)',
          'accent-2': 'var(--pixel-accent-2)',
          line: 'var(--pixel-line)',
          led: {
            green: '#99e550',
            amber: '#fbf236',
            red: '#ac3232',
          },
        },
      },
      fontFamily: {
        // CJK fallback: Press Start 2P / VT323 / Pixelify Sans ship only
        // latin, latin-ext, cyrillic and greek subsets. Chinese text has no
        // pixel glyphs in these fonts and falls back to the system CJK stack
        // (marked as fallback, not pixel fonts).
        display: ['"Press Start 2P"', ...cjkFallback],
        body: ['VT323', ...cjkFallback],
        mono: ['VT323', ...cjkFallback],
        pixel: ['"Pixelify Sans"', ...cjkFallback],
      },
      // Shape consistency: hard edges everywhere. Any rounded-* utility
      // resolves to 0 radius so legacy class names never reintroduce curves.
      borderRadius: {
        none: '0px',
        DEFAULT: '0px',
        sm: '0px',
        md: '0px',
        lg: '0px',
        xl: '0px',
        '2xl': '0px',
        '3xl': '0px',
        full: '0px',
      },
      // Pixel step shadows: hard offsets, zero blur.
      boxShadow: {
        pixel: '6px 6px 0 0 var(--pixel-line)',
        'pixel-sm': '4px 4px 0 0 var(--pixel-line)',
        'pixel-raised': '4px 4px 0 0 rgba(0, 0, 0, 0.45)',
        'pixel-inset': 'inset 3px 3px 0 0 rgba(0, 0, 0, 0.4), inset -3px -3px 0 0 rgba(255, 255, 255, 0.07)',
        'pixel-accent': '4px 4px 0 0 var(--pixel-accent)',
      },
      letterSpacing: {
        pixel: '0.1em',
      },
      transitionDuration: {
        'pixel-off': '0ms',
      },
      // Type scale anchored on 16px / 4px grid for the display font.
      fontSize: {
        'pixel-sm': ['10px', { lineHeight: '1.6', letterSpacing: '0.08em' }],
        'pixel-base': ['12px', { lineHeight: '1.6', letterSpacing: '0.06em' }],
        'pixel-lg': ['16px', { lineHeight: '1.5', letterSpacing: '0.04em' }],
        'pixel-xl': ['20px', { lineHeight: '1.4', letterSpacing: '0.03em' }],
        'pixel-2xl': ['24px', { lineHeight: '1.3', letterSpacing: '0.02em' }],
      },
    },
  },
  plugins: [],
} satisfies Config;
