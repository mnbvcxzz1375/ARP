import { describe, it, expect } from 'vitest';
// Pure-function enumeration tests: generateAvatarParts is the only entry
// point under test (spec). No DOM, no rendering, no timers.
import { generateAvatarParts } from '../../../lib/avatar';

const FALLBACK = 'unknown-agent';

const ANTENNA = ['straight', 'tiltedLeft', 'tiltedRight', 'none'] as const;
const EYES = ['square', 'dot', 'visor', 'closedHappy'] as const;
const SHELL = ['light', 'muted'] as const;
const CHEST = ['plain', 'badge'] as const;

/** 5000 seeds shaped like real agent numbers / names / ids. */
const SEEDS: string[] = [
  ...Array.from({ length: 2000 }, (_, i) => `AGT-${String(i + 1).padStart(4, '0')}`),
  ...Array.from({ length: 1500 }, (_, i) => `agent-${i}@example.com`),
  ...Array.from({ length: 1000 }, (_, i) => String(i)),
  ...Array.from({ length: 500 }, (_, i) => `推理引擎-${i}`),
];

describe('generateAvatarParts (pure functions)', () => {
  it('renders the identical parts for the same seed 1000 times', () => {
    const first = generateAvatarParts('AGT-0001');
    for (let i = 0; i < 1000; i++) {
      expect(generateAvatarParts('AGT-0001')).toEqual(first);
    }
  });

  it('keeps every dimension inside its domain across 5000 seeds', () => {
    for (const seed of SEEDS) {
      const parts = generateAvatarParts(seed);
      expect(ANTENNA).toContain(parts.antenna);
      expect(EYES).toContain(parts.eyes);
      expect(SHELL).toContain(parts.shell);
      expect(CHEST).toContain(parts.chest);
    }
  });

  it('reaches every variant value at least once across the enumeration', () => {
    const seen = { antenna: new Set<string>(), eyes: new Set<string>(), shell: new Set<string>(), chest: new Set<string>() };
    for (const seed of SEEDS) {
      const parts = generateAvatarParts(seed);
      seen.antenna.add(parts.antenna);
      seen.eyes.add(parts.eyes);
      seen.shell.add(parts.shell);
      seen.chest.add(parts.chest);
    }
    expect(seen.antenna).toEqual(new Set(ANTENNA));
    expect(seen.eyes).toEqual(new Set(EYES));
    expect(seen.shell).toEqual(new Set(SHELL));
    expect(seen.chest).toEqual(new Set(CHEST));
  });

  it('covers all 64 combinations across the enumeration (bits stay free)', () => {
    const combos = new Set<string>();
    for (const seed of SEEDS) {
      const p = generateAvatarParts(seed);
      combos.add(`${p.antenna}|${p.eyes}|${p.shell}|${p.chest}`);
    }
    expect(combos.size).toBe(64);
  });

  it('falls back to the shared identity for empty / null / undefined seeds', () => {
    const fallback = generateAvatarParts(FALLBACK);
    expect(generateAvatarParts('')).toEqual(fallback);
    expect(generateAvatarParts('   ')).toEqual(fallback);
    expect(generateAvatarParts(null)).toEqual(fallback);
    expect(generateAvatarParts(undefined)).toEqual(fallback);
  });

  it('falls back for pure-emoji and oversized seeds without throwing', () => {
    const fallback = generateAvatarParts(FALLBACK);
    expect(generateAvatarParts('🤖🛰️')).toEqual(fallback);
    expect(generateAvatarParts('🤖 🧠')).toEqual(fallback);
    // Ultra-long input collapses to the fallback instead of hashing forever.
    expect(generateAvatarParts('a'.repeat(100_000))).toEqual(fallback);
  });

  it('keeps mixed-content seeds with emoji (not pure emoji)', () => {
    // A readable identity next to an emoji still identifies the agent.
    const parts = generateAvatarParts('AGT-0001 🤖');
    expect(ANTENNA).toContain(parts.antenna);
    expect(generateAvatarParts('AGT-0001 🤖')).toEqual(parts);
  });

  it('distinguishes different business identifiers', () => {
    // Verified against the deterministic hash: two different agent numbers
    // resolve to different faces (collisions are acceptable at scale, but
    // adjacent numbers must not systematically collide).
    expect(generateAvatarParts('AGT-0001')).not.toEqual(generateAvatarParts('AGT-0002'));
  });

  it('never throws on hostile inputs', () => {
    // Control characters are not pure pictographs, so they hash normally;
    // the contract is only "no exception, parts stay in the domain".
    expect(() => generateAvatarParts('\u0000\u0001')).not.toThrow();
    const parts = generateAvatarParts('\u0000\u0001');
    expect(ANTENNA).toContain(parts.antenna);
    expect(EYES).toContain(parts.eyes);
  });
});
