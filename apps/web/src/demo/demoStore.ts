/**
 * Mutable store backing the demo adapter.
 *
 * The store is a deep copy of the fixture world per session: mutations from
 * the console (create gateway, approve request, toggle channel...) land in
 * the store and the next GET re-reads it — exactly the request/query
 * invalidation cycle pages already perform after mutations.
 *
 * Session persistence: the real app's session lives in HTTP cookies and
 * survives `window.location.href` (useLogin/redirectToConsole do FULL page
 * loads, not client-side navigation). The demo has no cookie, so the
 * session (persona id + loggedIn flag + locale) is mirrored to
 * localStorage; the fixture WORLD stays in memory only — a reload restores
 * a pristine demo dataset, which is the intended demo behavior.
 */
import { createDemoWorld, type DemoWorld } from './fixtures';
import type { PersonaId } from './personas';

/** Server-side appearance preferences (settings page PATCH target). Mirrors
 * UpdateUserPreferencesRequest: theme / fontScale / reducedMotion. */
export interface DemoPreferences {
  theme?: 'dark' | 'light';
  fontScale?: number;
  reducedMotion?: boolean;
}

export interface DemoStore {
  world: DemoWorld;
  /** Persona currently logged in ('personal' is the default demo login). */
  personaId: PersonaId;
  /** Whether the demo session is logged in at all. */
  loggedIn: boolean;
  /** Server-side locale preference mirror (settings page PATCH target). */
  locale: 'en' | 'zh' | null;
  /** Server-side appearance preferences (settings page PATCH target). */
  preferences: DemoPreferences;
}

const STORAGE_KEY = 'agentnet-demo-session';

interface PersistedSession {
  personaId: PersonaId;
  loggedIn: boolean;
  locale: 'en' | 'zh' | null;
  preferences?: DemoPreferences;
}

function loadSession(): PersistedSession {
  const fallback: PersistedSession = {
    personaId: 'personal',
    loggedIn: false,
    locale: null,
    preferences: {},
  };
  if (typeof window === 'undefined' || !window.localStorage) return fallback;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Partial<PersistedSession>;
    const prefs = parsed.preferences ?? {};
    return {
      personaId: parsed.personaId === 'super_admin' || parsed.personaId === 'org_manager' || parsed.personaId === 'personal'
        ? parsed.personaId
        : 'personal',
      loggedIn: !!parsed.loggedIn,
      locale: parsed.locale === 'en' || parsed.locale === 'zh' ? parsed.locale : null,
      preferences: {
        theme: prefs.theme === 'dark' || prefs.theme === 'light' ? prefs.theme : undefined,
        fontScale: typeof prefs.fontScale === 'number' ? prefs.fontScale : undefined,
        reducedMotion: typeof prefs.reducedMotion === 'boolean' ? prefs.reducedMotion : undefined,
      },
    };
  } catch {
    return fallback;
  }
}

function persistSession(s: PersistedSession): void {
  if (typeof window === 'undefined' || !window.localStorage) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    // Storage unavailable (private mode): the session lives in memory only,
    // and a full page reload signs the demo visitor back out.
  }
}

const initial = loadSession();

const store: DemoStore = {
  world: createDemoWorld(),
  personaId: initial.personaId,
  loggedIn: initial.loggedIn,
  locale: initial.locale,
  preferences: initial.preferences ?? {},
};

function sync(): void {
  persistSession({
    personaId: store.personaId,
    loggedIn: store.loggedIn,
    locale: store.locale,
    preferences: store.preferences,
  });
}

export function getDemoStore(): DemoStore {
  return store;
}

/** Mutations go through this to keep the persisted session in sync. */
export function setDemoSession(patch: Partial<PersistedSession>): void {
  if (patch.personaId !== undefined) store.personaId = patch.personaId;
  if (patch.loggedIn !== undefined) store.loggedIn = patch.loggedIn;
  if (patch.locale !== undefined) store.locale = patch.locale;
  sync();
}

export function resetDemoStore(): void {
  store.world = createDemoWorld();
}

/** Clear the demo session (identity + locale + preferences) without
 * touching the world. Used between tests; the banner's reset control
 * keeps the session. */
export function resetDemoSession(): void {
  store.preferences = {};
  setDemoSession({ personaId: 'personal', loggedIn: false, locale: null });
}
