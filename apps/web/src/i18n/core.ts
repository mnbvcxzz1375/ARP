/**
 * Framework-agnostic i18n core: catalog loading, interpolation, locale
 * resolution and a tiny external store the React layer subscribes to.
 *
 * Loading is split in two tiers:
 *
 * - Infra namespaces (`common`, `nav`, `shell`) are gathered eagerly. They
 *   render the app chrome (layouts, sidebars, generic buttons) and must be
 *   available before the first route chunk lands, so `t()` stays
 *   synchronous for them.
 *
 * - Feature namespaces (agents, tasks, enterprise, docs, ...) are gathered
 *   lazily and loaded together with the page chunk that uses them, so the
 *   initial bundle no longer ships the whole catalog (zh included).
 *   `loadNamespace()` registers them at runtime; `setLocale()`/`syncLocale()`
 *   load the namespaces already in use for the target locale before the
 *   switch applies, so a locale switch never renders a missing key.
 *
 * Both tiers stay auto-gathered: adding a namespace file (or a whole new
 * locale directory) takes effect without touching any registration table.
 * This is deliberate: 33 pages are translated in parallel and a
 * hand-written registry would be a merge-conflict magnet.
 *
 * In the vitest environment every namespace stays eager: unit tests render
 * pages directly (there is no route-level lazy boundary in them) and assert
 * translated strings synchronously.
 */

import type { Catalog, Locale, LocaleCatalog, Messages, TranslateParams } from './types';

export const LOCALE_STORAGE_KEY = 'agentnet-locale';

/** Locales the UI actually ships. Order matters: first = development source. */
export const SUPPORTED_LOCALES: readonly Locale[] = ['en', 'zh'];

/** Development source locale and the default before any resolution. */
export const DEFAULT_LOCALE: Locale = 'en';

type LocaleModule = { default: Messages };
type LocaleImporter = () => Promise<LocaleModule>;

/** Namespaces rendered by the app shell before any route resolves. */
export const EAGER_NAMESPACES = ['common', 'nav', 'shell'] as const;

/** Cache key for one namespace of one locale (`'en:agents'`). */
function nsKey(locale: Locale, namespace: string): string {
  return `${locale}:${namespace}`;
}

const LOCALE_PATH_RE = /\/locales\/([a-zA-Z-]+)\/([a-zA-Z0-9-]+)\.ts$/;

/**
 * Auto-gathered infra catalogs. Keys look like './locales/en/nav.ts'; the
 * path segments carry the locale code and the namespace (file name).
 */
const infraModules = import.meta.glob('./locales/*/{common,nav,shell}.ts', {
  eager: true,
}) as Record<string, LocaleModule>;

/**
 * Every namespace (infra included) as an on-demand import. In vitest the
 * glob is eager so unit tests keep their synchronous translations; in the
 * browser the values are dynamic imports resolved by `loadNamespace()`.
 */
const featureModules = import.meta.env.TEST
  ? (import.meta.glob('./locales/*/*.ts', { eager: true }) as Record<string, LocaleModule>)
  : (import.meta.glob('./locales/*/*.ts') as Record<string, LocaleImporter>);

/**
 * On-demand importers keyed by `'<locale>:<namespace>'`. The keys come from
 * the static glob output, so no user/locale string is ever built into a
 * module path at runtime.
 */
const featureImporters = new Map<string, LocaleImporter>();
if (!import.meta.env.TEST) {
  for (const [modulePath, importer] of Object.entries(featureModules)) {
    const match = LOCALE_PATH_RE.test(modulePath) ? modulePath.match(LOCALE_PATH_RE) : null;
    if (!match) {
      console.warn(`[i18n] unexpected locale module path, skipped: ${modulePath}`);
      continue;
    }
    const [, localeCode, namespace] = match;
    if (!isSupportedLocale(localeCode)) {
      console.warn(`[i18n] unsupported locale in path, skipped: ${modulePath}`);
      continue;
    }
    featureImporters.set(nsKey(localeCode, namespace), importer as LocaleImporter);
  }
}

/** Parse locale + namespace out of a glob key like './locales/en/nav.ts'. */
function parseLocalePath(path: string): [Locale, string] | null {
  const match = path.match(LOCALE_PATH_RE);
  if (!match) return null;
  const [, localeCode, namespace] = match;
  if (!isSupportedLocale(localeCode)) return null;
  return [localeCode, namespace];
}

function buildCatalog(): Catalog {
  const catalog: Partial<Catalog> = {};
  registerEagerModules(catalog, infraModules);
  if (import.meta.env.TEST) {
    registerEagerModules(catalog, featureModules as Record<string, LocaleModule>);
  }
  for (const locale of SUPPORTED_LOCALES) {
    if (!catalog[locale]) catalog[locale] = {};
  }
  return catalog as Catalog;
}

function registerEagerModules(
  catalog: Partial<Catalog>,
  modules: Record<string, LocaleModule>,
): void {
  for (const [path, mod] of Object.entries(modules)) {
    const parsed = parseLocalePath(path);
    if (!parsed) {
      console.warn(`[i18n] unexpected or unsupported locale module path, skipped: ${path}`);
      continue;
    }
    const [localeCode, namespace] = parsed;
    const messages = mod?.default;
    if (!messages || typeof messages !== 'object') {
      console.warn(`[i18n] locale module has no default message map: ${path}`);
      continue;
    }
    const localeCatalog: LocaleCatalog = (catalog[localeCode] ??= {});
    localeCatalog[namespace] = messages;
  }
}

export const CATALOG: Catalog = buildCatalog();

// ---------------------------------------------------------------------------
// Lazy namespace loading
// ---------------------------------------------------------------------------

const inFlightLoads = new Map<string, Promise<void>>();

/** True when the namespace is already registered for this locale. */
export function hasNamespace(locale: Locale, namespace: string): boolean {
  return CATALOG[locale]?.[namespace] !== undefined;
}

/** Merge a loaded namespace into the catalog and notify subscribers. */
export function registerMessages(locale: Locale, namespace: string, messages: Messages): void {
  const localeCatalog: LocaleCatalog = (CATALOG[locale] ??= {});
  if (localeCatalog[namespace] === messages) return;
  localeCatalog[namespace] = messages;
  notify();
}

/**
 * Load one feature namespace for one locale on demand. Idempotent and
 * de-duplicated: concurrent callers share the same in-flight promise.
 * A failed load warns and leaves the namespace absent, so `translate()`
 * still falls back to English (or the key) instead of throwing.
 */
export function loadNamespace(locale: Locale, namespace: string): Promise<void> {
  const cacheKey = nsKey(locale, namespace);
  if (hasNamespace(locale, namespace)) return Promise.resolve();
  const existing = inFlightLoads.get(cacheKey);
  if (existing) return existing;

  const importer = featureImporters.get(cacheKey);
  if (!importer) {
    console.warn(`[i18n] no locale module for namespace: ${cacheKey}`);
    return Promise.resolve();
  }

  const load: Promise<void> = importer().then(
    (mod) => {
      const messages = mod?.default;
      if (!messages || typeof messages !== 'object') {
        console.warn(`[i18n] locale module has no default message map: ${cacheKey}`);
        return;
      }
      registerMessages(locale, namespace, messages);
    },
    (error: unknown) => {
      // Keep the UI running on the English fallback; the switcher retries
      // on the next locale change because the cache entry is dropped below.
      console.warn(`[i18n] failed to load namespace: ${cacheKey}`, error);
    },
  );
  inFlightLoads.set(cacheKey, load);
  // A failed load must stay retryable, so it is not cached as in-flight.
  void load.then(undefined, () => inFlightLoads.delete(cacheKey));
  return load;
}

/** Load several namespaces for one locale in parallel. */
export function loadNamespaces(locale: Locale, namespaces: readonly string[]): Promise<void> {
  return Promise.all(namespaces.map((ns) => loadNamespace(locale, ns))).then(() => undefined);
}

/**
 * Namespaces still missing for `locale` but already loaded for another
 * locale - i.e. exactly the feature namespaces currently in use. Loading
 * these before a locale switch keeps `t()` synchronous without missing keys.
 */
export function missingNamespacesFor(locale: Locale): string[] {
  const inUse = new Set<string>();
  for (const other of SUPPORTED_LOCALES) {
    if (other === locale) continue;
    for (const namespace of Object.keys(CATALOG[other] ?? {})) inUse.add(namespace);
  }
  return [...inUse].filter((namespace) => !hasNamespace(locale, namespace));
}

export function isSupportedLocale(value: unknown): value is Locale {
  return (
    typeof value === 'string' &&
    (SUPPORTED_LOCALES as readonly string[]).includes(value)
  );
}

const INTERPOLATE_RE = /\{\{\s*(\w+)\s*\}\}/g;

/** Replace `{{param}}` placeholders with concrete values. */
export function interpolate(message: string, params?: TranslateParams): string {
  if (!params) return message;
  return message.replace(INTERPOLATE_RE, (match, name: string) => {
    const value = params[name];
    return value === undefined || value === null ? match : String(value);
  });
}

/** Look up a dotted key ('nav.item.overview') inside one locale. */
export function lookup(locale: Locale, key: string): string | undefined {
  const sep = key.indexOf('.');
  if (sep === -1) return undefined;
  const namespace = key.slice(0, sep);
  const messageKey = key.slice(sep + 1);
  return CATALOG[locale]?.[namespace]?.[messageKey];
}

/**
 * Translate with English fallback. Missing everywhere -> return the key
 * and warn, so a typo'd key is visible in dev instead of rendering empty.
 */
export function translate(locale: Locale, key: string, params?: TranslateParams): string {
  const message = lookup(locale, key) ?? lookup(DEFAULT_LOCALE, key);
  if (message === undefined) {
    console.warn(`[i18n] missing translation key: "${key}" (locale ${locale})`);
    return key;
  }
  return interpolate(message, params);
}

/**
 * Map an arbitrary browser language tag to a supported locale.
 * 'zh-*' -> 'zh', everything else -> 'en'.
 */
export function localeFromBrowserTag(tag: string | undefined): Locale {
  if (!tag) return DEFAULT_LOCALE;
  const code = tag.trim().toLowerCase().split('-')[0];
  return code === 'zh' ? 'zh' : DEFAULT_LOCALE;
}

function readStoredLocale(): Locale | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    return isSupportedLocale(stored) ? stored : null;
  } catch {
    return null; // localStorage unavailable (private mode etc.)
  }
}

export function getBrowserLocale(): Locale {
  if (typeof navigator === 'undefined') return DEFAULT_LOCALE;
  return localeFromBrowserTag(navigator.language);
}

/**
 * Pure resolution used both directly and by the provider. Priority:
 * backend preference (logged-in user) > localStorage > navigator.language
 * > 'en'. Returns the *effective* locale for a candidate stack.
 */
export function resolveLocale(
  preferred: Locale | null | undefined,
  stored: Locale | null,
  browser: Locale,
): Locale {
  if (isSupportedLocale(preferred)) return preferred;
  if (isSupportedLocale(stored)) return stored;
  return browser;
}

/**
 * Resolve without a backend preference (public surface / pre-auth).
 */
export function resolveBaseLocale(): Locale {
  return resolveLocale(null, readStoredLocale(), getBrowserLocale());
}

// ---------------------------------------------------------------------------
// External store - the React layer subscribes via useSyncExternalStore so
// `useI18n()` also works for components rendered without an I18nProvider
// (existing unit tests render layouts standalone; they assert English).
// ---------------------------------------------------------------------------

let currentLocale: Locale = resolveBaseLocale();
/** Set once the user manually picked a locale this session; a manual pick
 *  wins over the backend preference until the page is reloaded. */
let manualOverride = false;
const listeners = new Set<() => void>();

export function getLocale(): Locale {
  return currentLocale;
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function notify() {
  for (const listener of listeners) listener();
}

function applyLocale(locale: Locale) {
  currentLocale = locale;
  if (typeof document !== 'undefined') {
    document.documentElement.lang = locale;
  }
  notify();
}

/**
 * Apply `locale` once every namespace currently in use has been loaded for
 * it: when all namespaces are already present (always true for the infra
 * tier) the switch is synchronous; otherwise the UI keeps rendering the old
 * locale for the short on-demand load window instead of flashing untranslated
 * keys or English fallbacks.
 */
function applyLocaleWithNamespaces(locale: Locale): void | Promise<void> {
  const missing = missingNamespacesFor(locale);
  if (missing.length === 0) {
    applyLocale(locale);
    return;
  }
  return loadNamespaces(locale, missing).then(() => applyLocale(locale));
}

/**
 * Switch locale as a user action: persists to localStorage and sets
 * `<html lang>`. Marks a session manual override so the provider's
 * backend-preference sync does not immediately revert it (resolution
 * priority still applies on the next full page load).
 */
export function setLocale(locale: Locale): void {
  if (!isSupportedLocale(locale)) return;
  manualOverride = true;
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // Ignore write failures - the in-memory locale still applies.
  }
  void applyLocaleWithNamespaces(locale);
}

/**
 * Provider-driven sync (backend preference). Never persists and never
 * overrides an explicit user pick from this session.
 */
export function syncLocale(locale: Locale): void {
  if (!isSupportedLocale(locale)) return;
  if (manualOverride || locale === currentLocale) return;
  void applyLocaleWithNamespaces(locale);
}

/** Test helper: reset store + DOM side effects between cases. */
export function __resetI18n(): void {
  manualOverride = false;
  applyLocale(resolveBaseLocale());
}

// Reflect the resolved locale on <html lang> as early as possible.
if (typeof document !== 'undefined') {
  document.documentElement.lang = currentLocale;
}
