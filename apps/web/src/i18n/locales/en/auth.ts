/**
 * Sign-in page (namespace `auth`) - English source locale.
 *
 * Covers src/features/auth/LoginPage.tsx. The page's label/error/submit
 * copy already lives in the `common` namespace (it is public-shell
 * surface rendered before any feature namespace, see
 * locales/en/common.ts) and is reused as-is; this namespace holds only
 * the remaining page-specific strings (input placeholders).
 *
 * Parallel translation shards: extend this file for auth-page strings -
 * do not create a second registration file (locales are auto-gathered
 * by import.meta.glob in ../core.ts). Translation rules live in
 * src/i18n/glossary.md.
 */
const auth = {
  // LoginPage inputs
  'login.usernamePlaceholder': 'your-username',
  // Format example: the literal 'ak_' prefix of a real API key.
  'login.apiKeyPlaceholder': 'ak_...',
};

export default auth;
