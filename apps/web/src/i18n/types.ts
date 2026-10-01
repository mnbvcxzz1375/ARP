/**
 * Type contracts for the self-hosted AgentNet i18n core.
 *
 * No runtime i18n library is used (zero new dependencies). Everything in
 * this file is structural so the locale set can grow (ja etc.) by adding
 * the locale code to `Locale` and dropping a `locales/<code>/` directory
 * next to the existing ones - the glob in core.ts picks it up
 * automatically. No hand-maintained registration table exists on purpose:
 * parallel translators must never edit a shared registry file.
 */

/**
 * Supported UI locales. The development/source locale is `en` - it is the
 * fallback for every missing key and the default before resolution.
 */
export type Locale = 'en' | 'zh';

/**
 * Shape every locale module under `locales/<locale>/<namespace>.ts` must
 * export as default: a flat map of message keys to message strings.
 *
 * Keys may contain dots ('item.overview'); the first segment of a
 * translation key is the namespace (the file name), the rest is the
 * message key inside it. Example: key 'nav.item.agents' lives in
 * `locales/en/nav.ts` under 'item.agents'.
 *
 * Values are plain strings - pluralization/count handling is intentionally
 * out of scope for this console.
 */
export type Messages = Record<string, string>;

/**
 * A whole locale: namespace (file name) -> messages.
 */
export type LocaleCatalog = Record<string, Messages>;

/**
 * The full catalog: locale code -> LocaleCatalog. Populated by the
 * import.meta.glob in core.ts.
 */
export type Catalog = Record<Locale, LocaleCatalog>;

/**
 * Interpolation parameters. `{{paramName}}` inside a message string is
 * replaced by `params.paramName`.
 */
export type TranslateParams = Record<string, string | number>;

/**
 * The translate function returned by useT().
 *
 * - Interpolates `{{param}}` placeholders.
 * - Falls back to the English message when the key is missing in the
 *   active locale.
 * - Returns the key itself and console.warns when the key is missing from
 *   every locale, so missing keys surface during development instead of
 *   rendering as blank space.
 */
export type TFunction = (key: string, params?: TranslateParams) => string;
