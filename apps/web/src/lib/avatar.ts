/** Stable seed normalization and selection of the shared pixel robot art.
 * The original geometry helper remains available for existing consumers;
 * visible AgentAvatar and StationMaster render the artwork selected below.
 */

/** Antenna geometry on top of the head. */
export type AntennaVariant = 'straight' | 'tiltedLeft' | 'tiltedRight' | 'none';
/** Eye style drawn inside the head. */
export type EyeVariant = 'square' | 'dot' | 'visor' | 'closedHappy';
/** Shell fill, theme-following (light = --pixel-fg, muted = --pixel-muted). */
export type ShellVariant = 'light' | 'muted';
/** Chest panel detail (badge adds the decorative --pixel-accent rect). */
export type ChestVariant = 'plain' | 'badge';

export interface AvatarParts {
  antenna: AntennaVariant;
  eyes: EyeVariant;
  shell: ShellVariant;
  chest: ChestVariant;
}

/** Seed used when the input carries no usable identity. */
export const FALLBACK_SEED = 'unknown-agent';

/**
 * Guard against pathological inputs (a 1MB agent_number string would hash
 * forever for no benefit): longer seeds collapse to the fallback.
 */
const MAX_SEED_LENGTH = 1024;

/**
 * A string made only of pictographs (emoji), variation selectors, ZWJ and
 * whitespace carries no readable identity, so it falls back too. \p{...}
 * unicode property escapes need the `u` flag (ES2018+, tsconfig ES2020).
 */
const PICTOGRAPHIC_ONLY_RE = /^[\p{Extended_Pictographic}\s\uFE0F\u200D]*$/u;

const ANTENNA_VARIANTS: readonly AntennaVariant[] = [
  'straight',
  'tiltedLeft',
  'tiltedRight',
  'none',
];
const EYE_VARIANTS: readonly EyeVariant[] = ['square', 'dot', 'visor', 'closedHappy'];
const SHELL_VARIANTS: readonly ShellVariant[] = ['light', 'muted'];
const CHEST_VARIANTS: readonly ChestVariant[] = ['plain', 'badge'];

/**
 * Collapse any input to a hashable seed. Non-strings, empty/whitespace-only
 * strings, pure-emoji strings and oversized strings all resolve to the
 * shared fallback identity instead of throwing.
 */
export function normalizeSeed(seed: unknown): string {
  if (typeof seed !== 'string') return FALLBACK_SEED;
  const trimmed = seed.trim();
  if (trimmed.length === 0 || trimmed.length > MAX_SEED_LENGTH) return FALLBACK_SEED;
  if (PICTOGRAPHIC_ONLY_RE.test(trimmed)) return FALLBACK_SEED;
  return trimmed;
}

/**
 * FNV-1a 32-bit (offset basis 0x811c9dc5, prime 0x01000193).
 * `Math.imul` keeps the multiply inside 32 bits (no 53-bit float drift) and
 * `>>> 0` returns the unsigned magnitude, so the hash is stable across
 * engines for the same input.
 */
export function hashSeed(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

/**
 * Derive the four sprite dimensions from a seed. Bit layout (spec):
 * antenna h % 4, eyes (h >>> 2) % 4, chest (h >>> 6) % 2; the shell slot
 * takes the free bit between them, (h >>> 4) % 2, so all 64 combinations
 * stay reachable.
 */
export function generateAvatarParts(seed: string | null | undefined): AvatarParts {
  const h = hashSeed(normalizeSeed(seed));
  return {
    antenna: ANTENNA_VARIANTS[h % ANTENNA_VARIANTS.length],
    eyes: EYE_VARIANTS[(h >>> 2) % EYE_VARIANTS.length],
    shell: SHELL_VARIANTS[(h >>> 4) % SHELL_VARIANTS.length],
    chest: CHEST_VARIANTS[(h >>> 6) % CHEST_VARIANTS.length],
  };
}

/** Bounds trim transparent export padding without altering the original artwork. */
const AVATAR_SPRITES = [
  { src: '/art/archipelago/robot-courier.png', width: 1145, height: 1374, viewBox: '228 115 720 1172', portraitViewBox: '228 115 720 900' },
  { src: '/art/archipelago/robot-operator.png', width: 1122, height: 1402, viewBox: '142 31 861 1339', portraitViewBox: '142 31 861 1020' },
  { src: '/art/archipelago/robot-scout.png', width: 1049, height: 1499, viewBox: '54 16 954 1443', portraitViewBox: '54 16 954 1100' },
] as const;

export function getAvatarSprite(seed: string | null | undefined) {
  return AVATAR_SPRITES[hashSeed(normalizeSeed(seed)) % AVATAR_SPRITES.length];
}
