/**
 * No-access feedback page (namespace `noAccess`) - English source locale.
 *
 * Shown when an authenticated session lacks the permissions a guarded route
 * requires (fail-closed guard outcome). Public route, no sign-in needed.
 */
const noAccess = {
  title: 'No Access',
  description:
    'Your account does not have the permissions required for this page. Sign in with a different account, or go back to the console overview.',
  back: 'Back to Overview',
  logout: 'Sign Out',
};

export default noAccess;
