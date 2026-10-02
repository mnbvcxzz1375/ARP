import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import IslandNode, {
  ISLAND_SPRITE_WIDTH,
  ISLAND_SPRITE_HEIGHT,
  ISLAND_NODE_CENTER_OFFSET,
} from '../IslandNode';
import { CATALOG, registerMessages, setLocale } from '../../../i18n/core';

/**
 * Unit-level checks for the archipelago island node. What jsdom can verify:
 * - the button role, 44px touch target and the composed accessible name,
 * - selection semantics (aria-pressed + aria-current=step, stepped ring),
 * - anchor geometry (bottom-center slot anchor) and exported metrics,
 * - presence: LED-green/line dot + the EXISTING common.statusLabel words,
 *   in en and zh (never color alone),
 * - deterministic avatar derivation (agent_number ?? agent_id),
 * - theme-token-only fills (no hardcoded colors).
 *
 * What is NOT covered here (documented gaps):
 * - the composed label relies on 'overview.island.label', a key owned by
 *   the overview i18n item (locales/{en,zh}/overview.ts). Until it lands,
 *   translate() returns the key itself; these tests therefore REGISTER
 *   the contract copy at runtime (core.registerMessages, an API export)
 *   instead of editing the locale shard, and assert the composition.
 * - visual pixel-art precision (sighted review), stage scaling,
 *   arrow-key roving tabindex (the stage owns it; the button exposes the
 *   native Enter/Space activation and a tabIndex pass-through).
 */

/** The exact contract copy IslandNode consumes (see its docblock). */
const ISLAND_COPY_EN = {
  'island.label': 'Island {{index}} of {{total}} · {{name}} ({{number}}) · {{status}}',
};
const ISLAND_COPY_ZH = {
  'island.label': '第 {{index}} 座岛，共 {{total}} 座 · {{name}}（{{number}}）· {{status}}',
};

/** Merge the label key into the existing overview namespace (no shard edit). */
function installIslandLabelKey(): void {
  registerMessages('en', 'overview', { ...(CATALOG['en']?.['overview'] ?? {}), ...ISLAND_COPY_EN });
  registerMessages('zh', 'overview', { ...(CATALOG['zh']?.['overview'] ?? {}), ...ISLAND_COPY_ZH });
}

const AGENT = {
  id: 'a1000001-0000-4000-8000-000000000001',
  number: 'AN-01AA-BB01-01',
  name: 'Atlas Worker',
  status: 'online' as const,
};

const SLOT = { x: 240, y: 144 };

function avatarSprite(): Element {
  const svg = document.querySelector('.agent-avatar');
  if (!svg) throw new Error('AgentAvatar sprite missing');
  return svg;
}

beforeEach(() => {
  installIslandLabelKey();
  setLocale('en');
});

afterEach(() => {
  setLocale('en');
  cleanup();
});

describe('IslandNode', () => {
  it('renders a 44px-touch-target button with the composed accessible name', () => {
    render(<IslandNode agent={AGENT} slot={SLOT} index={1} total={6} />);
    const button = screen.getByRole('button');
    // Touch target (TOUCH_TARGET, tokens.ts:66) on the button itself.
    expect(button.className).toContain('min-h-[44px]');
    expect(button.className).toContain('min-w-[44px]');
    expect(button).toHaveAttribute(
      'aria-label',
      'Island 1 of 6 · Atlas Worker (AN-01AA-BB01-01) · Online',
    );
    // The node composes the name/number/presence/ordinal itself.
    expect(screen.getByText('Atlas Worker')).toBeInTheDocument();
    expect(screen.getByText('AN-01AA-BB01-01')).toBeInTheDocument();
  });

  it('anchors the sprite bottom-center at the slot and exports the metrics ConnectionLayer needs', () => {
    render(<IslandNode agent={AGENT} slot={SLOT} index={1} total={6} />);
    const button = screen.getByRole('button');
    expect(button.style.left).toBe('240px');
    expect(button.style.top).toBe('144px');
    // Bottom-center anchor: sprite grows upward from the slot, label above.
    expect(button.style.transform).toBe('translate(-50%, -100%)');
    // Exported geometry (stage px, figure box + center offset).
    expect(ISLAND_SPRITE_WIDTH).toBe(232);
    expect(ISLAND_SPRITE_HEIGHT).toBe(176);
    expect(ISLAND_NODE_CENTER_OFFSET).toBe(88);
  });

  it('marks selection with aria-pressed and aria-current=step only when selected', () => {
    const { rerender } = render(
      <IslandNode agent={AGENT} slot={SLOT} index={3} total={6} />,
    );
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-pressed', 'false');
    expect(button).not.toHaveAttribute('aria-current');

    rerender(<IslandNode agent={AGENT} slot={SLOT} index={3} total={6} selected />);
    expect(button).toHaveAttribute('aria-pressed', 'true');
    // aria-current=step is the SELECTED NODE semantics (JourneyMap.tsx:283),
    // never to be used on connections.
    expect(button).toHaveAttribute('aria-current', 'step');
  });


  it('reports presence as a semantic dot plus the shared en/zh status words', () => {
    const { rerender } = render(<IslandNode agent={AGENT} slot={SLOT} index={1} total={6} />);
    // Online: LED-green dot + the EXISTING common.statusLabel.online word.
    expect(screen.getByText('Online')).toBeInTheDocument();
    const onlineDot = screen.getByText('Online').previousElementSibling!;
    expect(onlineDot.className).toContain('bg-pixel-led-green');
    expect(onlineDot.className).toContain('border-pixel-bg');

    // Offline: line-colored dot + the offline word (never color alone).
    rerender(
      <IslandNode
        agent={{ ...AGENT, status: 'offline' }}
        slot={SLOT}
        index={1}
        total={6}
      />,
    );
    // Offline: line-colored dot + the offline word (never color alone).
    expect(screen.getByText('Offline')).toBeInTheDocument();
    const offlineDot = screen.getByText('Offline').previousElementSibling!;
    expect(offlineDot.className).toContain('bg-pixel-line');

    // Unknown/absent status also reads offline instead of implying presence.
    rerender(
      <IslandNode agent={{ ...AGENT, status: null }} slot={SLOT} index={1} total={6} />,
    );
    expect(screen.getByText('Offline')).toBeInTheDocument();
  });

  it('renders the zh status word under the zh locale (CJK falls back honestly)', () => {
    setLocale('zh');
    render(<IslandNode agent={AGENT} slot={SLOT} index={2} total={6} />);
    // common.statusLabel.online exists in zh ('在线') - reused, not new copy.
    expect(screen.getByText('在线')).toBeInTheDocument();
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute(
      'aria-label',
      '第 2 座岛，共 6 座 · Atlas Worker（AN-01AA-BB01-01）· 在线',
    );
  });

  it('derives the avatar deterministically from agent_number, falling back to agent_id', () => {
    const { unmount } = render(<IslandNode agent={AGENT} slot={SLOT} index={1} total={6} />);
    const first = avatarSprite().outerHTML;
    unmount();

    render(<IslandNode agent={AGENT} slot={SLOT} index={1} total={6} />);
    expect(avatarSprite().outerHTML).toBe(first);
    cleanup();

    // A different number hashes a different face (FNV-1a, 64 faces).
    render(
      <IslandNode
        agent={{ ...AGENT, number: 'AN-02AA-BB02-02', name: 'Beacon Relay Bot' }}
        slot={SLOT}
        index={2}
        total={6}
      />,
    );
    expect(avatarSprite().outerHTML).not.toBe(first);
    cleanup();

    // No number -> the agent id seeds the face.
    render(<IslandNode agent={{ ...AGENT, number: null }} slot={SLOT} index={1} total={6} />);
    const byId = avatarSprite().outerHTML;
    expect(avatarSprite()).toHaveAttribute('data-agent-seed', AGENT.id);
    cleanup();

    render(<IslandNode agent={{ ...AGENT, number: null }} slot={SLOT} index={1} total={6} />);
    expect(avatarSprite().outerHTML).toBe(byId);
  });

  it('selects on click with the agent id and passes tabIndex through (roving tabindex)', () => {
    const onSelect = vi.fn();
    render(
      <IslandNode agent={AGENT} slot={SLOT} index={1} total={6} onSelect={onSelect} tabIndex={-1} />,
    );
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('tabindex', '-1');
    fireEvent.click(button);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(AGENT.id);
  });


  it('falls back to the raw key (visible in dev) while overview.island.label is absent', () => {
    // Restore the pristine overview shard: the label key is owned by the
    // i18n item, so its absence must surface, not silently render empty.
    const pristineEn = { ...CATALOG['en']?.['overview'] };
    delete (pristineEn as Record<string, string>)['island.label'];
    registerMessages('en', 'overview', pristineEn);
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      render(<IslandNode agent={AGENT} slot={SLOT} index={1} total={6} />);
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'overview.island.label');
      const warned = warn.mock.calls.some((call) =>
        String(call[0]).includes('overview.island.label'),
      );
      expect(warned).toBe(true);
    } finally {
      warn.mockRestore();
      installIslandLabelKey();
    }
  });
});
