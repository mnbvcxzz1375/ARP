import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import EmptyState from '../EmptyState';
import { setLocale, DEFAULT_LOCALE } from '../../i18n/core';

/**
 * The story scenes consume the real sibling deliverables: the StationMaster
 * sprite (components/pixel/StationMaster) and the PIX_LINK_PRIMARY link
 * class constant (features/connections/pixel-ui). Only the preferences hook
 * is mocked (the sprite reads the stored reduced-motion preference through
 * react-query; the scenes render it as a static `pose="idle"` sprite, so no
 * timers and no query client are involved).
 */
vi.mock('../../hooks/usePreferences', () => ({
  usePreferences: () => ({ data: { reducedMotion: null } }),
}));

function renderWithRouter(ui: JSX.Element) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

const AGENTS_ACTION = { to: '/docs/quickstart', label: 'Read the quickstart' };

describe('EmptyState', () => {
  afterEach(() => {
    setLocale(DEFAULT_LOCALE);
  });

  describe('default scene (backwards compatible)', () => {
    it('renders the Inbox panel with the message prop', () => {
      render(<EmptyState message="Nothing here" />);
      expect(screen.getByText('Nothing here')).toBeInTheDocument();
      // Inbox icon stays decorative.
      expect(document.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
    });

    it('renders no action link and no scene art without the new props', () => {
      render(<EmptyState message="Nothing here" />);
      expect(screen.queryByRole('link')).toBeNull();
      expect(screen.queryByRole('img')).toBeNull();
    });

    it('keeps the legacy markup shape: single muted paragraph, p-12 panel', () => {
      const { container } = render(<EmptyState message="Nothing here" />);
      const panel = container.firstElementChild as HTMLElement;
      expect(panel.className).toContain('bg-pixel-surface');
      expect(panel.className).toContain('p-12');
      // No scanline texture on the default scene.
      expect(panel.className).not.toContain('repeating-linear-gradient');
      expect(panel.querySelectorAll('p')).toHaveLength(1);
    });
  });

  describe('agents scene', () => {
    it('renders the story copy from the agents namespace', () => {
      renderWithRouter(<EmptyState scene="agents" action={AGENTS_ACTION} />);
      expect(screen.getByText('No agent on duty yet')).toBeInTheDocument();
      expect(
        screen.getByText('Connect your first agent and the station opens.'),
      ).toBeInTheDocument();
    });

    it('renders the action as a primary link to the quickstart, not a button', () => {
      renderWithRouter(<EmptyState scene="agents" action={AGENTS_ACTION} />);
      const link = screen.getByRole('link', { name: 'Read the quickstart' });
      expect(link).toHaveAttribute('href', '/docs/quickstart');
      // PIX_LINK_PRIMARY contract: 44px touch target, accent solid block,
      // hard dark border, and the 2px press feedback (no a > button nesting;
      // the affordance is an <a> itself).
      expect(link.className).toContain('min-h-[44px]');
      expect(link.className).toContain('bg-pixel-accent');
      expect(link.className).toContain('active:translate-y-[2px]');
      expect(link.tagName).toBe('A');
      expect(link.querySelector('button')).toBeNull();
    });

    it('renders no link when no action is provided', () => {
      renderWithRouter(<EmptyState scene="agents" />);
      expect(screen.queryByRole('link')).toBeNull();
    });

    it('gives the scene art an accessible name and consumes StationMaster idle', () => {
      renderWithRouter(<EmptyState scene="agents" action={AGENTS_ACTION} />);
      const svg = screen.getByRole('img', { name: 'No agent on duty yet' });
      // React renders the attribute kebab-cased in the DOM.
      expect(svg.getAttribute('shape-rendering')).toBe('crispEdges');
      // The real mascot sprite renders beside the scene as a static 64px
      // read-only consumption (role=img + i18n label, never aria-hidden).
      const mascot = screen.getByRole('img', { name: 'Station Master' });
      expect(mascot.getAttribute('width')).toBe('64');
      expect(mascot.getAttribute('height')).toBe('64');
      // pose="idle" is static: no waving class, no timers attached.
      expect(mascot.className).not.toContain('is-waving');
    });

    it('uses only theme-following pixel palette variables in the scene art', () => {
      renderWithRouter(<EmptyState scene="agents" action={AGENTS_ACTION} />);
      const svg = screen.getByRole('img', { name: 'No agent on duty yet' });
      const styles = [...svg.querySelectorAll('rect')].map((r) => r.getAttribute('style') ?? '');
      // Every shape is painted from a theme-following --pixel-* token; no
      // hardcoded hex ever lands on a dark panel (the dark-theme contrast
      // ratios in the design spec assume exactly this).
      for (const s of styles) {
        expect(s).toMatch(/var\(--pixel-(fg|bg|muted|line)\)/);
        expect(s).not.toMatch(/#[0-9a-fA-F]{3,6}/);
        expect(s).not.toMatch(/rgb\(/);
      }
    });
  });

  describe('tasks scene', () => {
    it('renders the story copy from the tasks namespace', () => {
      renderWithRouter(<EmptyState scene="tasks" action={AGENTS_ACTION} />);
      expect(screen.getByText('The conveyor is quiet')).toBeInTheDocument();
      expect(
        screen.getByText('Send the first task and the first parcel rolls out.'),
      ).toBeInTheDocument();
    });

    it('renders the quickstart action link', () => {
      renderWithRouter(<EmptyState scene="tasks" action={AGENTS_ACTION} />);
      expect(screen.getByRole('link', { name: 'Read the quickstart' })).toHaveAttribute(
        'href',
        '/docs/quickstart',
      );
    });

    it('labels the conveyor scene and keeps the mascot beside it', () => {
      renderWithRouter(<EmptyState scene="tasks" />);
      expect(screen.getByRole('img', { name: 'The conveyor is quiet' })).toBeInTheDocument();
      expect(screen.getByRole('img', { name: 'Station Master' })).toBeInTheDocument();
    });
  });

  describe('zh locale', () => {
    it('renders the Chinese story copy for both scenes', () => {
      setLocale('zh');
      renderWithRouter(<EmptyState scene="agents" action={AGENTS_ACTION} />);
      expect(screen.getByText('第一个伙伴还没上岗')).toBeInTheDocument();
      expect(screen.getByText('接入第一个智能体，中继站就开始营业了')).toBeInTheDocument();
      // The mascot label follows the shell namespace into Chinese too.
      expect(screen.getByRole('img', { name: '小站长' })).toBeInTheDocument();

      renderWithRouter(<EmptyState scene="tasks" />);
      expect(screen.getByText('传送带还安静')).toBeInTheDocument();
      expect(screen.getByText('发出第一个任务，包裹就会从这里出发')).toBeInTheDocument();
    });
  });
});
