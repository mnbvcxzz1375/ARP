import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import RelayScene from '../RelayScene';
import { setLocale } from '../../../i18n/core';

/**
 * Unit-level checks for the overview hero scene. The spec's full
 * acceptance set (375px overflow, emulated prefers-reduced-motion without
 * parcel displacement, live theme contrast sampling) is playwright-based
 * and not runnable here; these tests cover what jsdom can verify:
 * - the three summary branches with {{count}} interpolation,
 * - the scene geometry and the read-only consumer sprites,
 * - theme-token-only classes (no hardcoded colors on the new art),
 * - the `is-live` pass-through the host toggles on a data change.
 */

// The embedded StationMaster reads the stored backend preference
// (usePreferences.ts:38); mocking the hook keeps these tests network-free
// (same pattern as StationMaster.test.tsx).
vi.mock('../../../hooks/usePreferences', () => ({
  usePreferences: () => ({ data: { reducedMotion: null } }),
}));

beforeEach(() => {
  setLocale('en');
});

afterEach(() => {
  setLocale('en');
  cleanup();
});

describe('RelayScene', () => {
  it('renders the nominal summary with the online count', () => {
    render(<RelayScene onlineAgents={3} failedTasks={0} />);
    expect(screen.getByText('Station nominal · 3 agents online')).toBeInTheDocument();
  });

  it('renders the idle summary when no agent is online', () => {
    render(<RelayScene onlineAgents={0} failedTasks={0} />);
    expect(screen.getByText('Station idling, no agent on duty')).toBeInTheDocument();
  });

  it('renders the failed branch as an LED chip plus copy (failed wins over idle)', () => {
    render(<RelayScene onlineAgents={0} failedTasks={2} />);
    // Inline count chip on the existing PIXEL_CHIP.bad palette (tokens.ts:25).
    const chip = screen.getByText('2');
    expect(chip.className).toContain('bg-pixel-led-red');
    expect(chip.className).toContain('border-[#191a26]');
    expect(screen.getByText('2 parcels stuck, need attention')).toBeInTheDocument();
  });

  it('renders the zh nominal copy under the zh locale', () => {
    setLocale('zh');
    render(<RelayScene onlineAgents={5} failedTasks={0} />);
    // zh copy falls back through the CJK stack; assert the count interpolation.
    expect(screen.getByText(/5/)).toBeInTheDocument();
    expect(screen.getByText(/伙伴在线/)).toBeInTheDocument();
  });

  it('embeds the StationMaster sprite (read-only consumption) and two agent avatars', () => {
    render(<RelayScene onlineAgents={1} failedTasks={0} />);
    const sprites = document.querySelectorAll('.station-master');
    expect(sprites).toHaveLength(1);
    expect(sprites[0]).toHaveAttribute('aria-label', 'Station Master');
    // Both agent avatars render; the right one is hidden below sm.
    const avatars = document.querySelectorAll('.agent-avatar');
    expect(avatars).toHaveLength(2);
    expect(avatars[0].closest('div')!.className).not.toContain('hidden');
    expect(avatars[1].closest('div')!.className).toContain('hidden');
    expect(avatars[1].closest('div')!.className).toContain('sm:flex');
  });

  it('draws the scene art from theme tokens (parcel, tower, track, pedestal)', () => {
    render(<RelayScene onlineAgents={1} failedTasks={0} />);
    const parcel = document.querySelector('.relay-scene__package')!;
    // Parcel: fg fill + 2px bg edge + resting on the line track.
    expect(parcel.className).toContain('bg-pixel-fg');
    expect(parcel.className).toContain('border-pixel-bg');
    // The parcel rests beside the tower (natural slot), not mid-route.
    expect(parcel.className).toContain('left-[140px]');
    // Pedestals carry the muted fill + bg edge (AA in both themes).
    const pedestals = document.querySelectorAll('.bg-pixel-muted.border-pixel-bg');
    expect(pedestals.length).toBeGreaterThanOrEqual(2);
    // No inline style leaks hardcoded colors into the new scene art.
    expect(document.querySelector('.relay-scene__package')!.getAttribute('style')).toBeNull();
  });

  it('passes the host className through (is-live toggle surface)', () => {
    render(<RelayScene onlineAgents={1} failedTasks={0} className="is-live" />);
    expect(document.querySelector('.relay-scene')!.className).toContain('is-live');
    // The animation target exists and is scoped by that exact class pair.
    expect(document.querySelector('.relay-scene.is-live .relay-scene__package')).not.toBeNull();
  });
});
