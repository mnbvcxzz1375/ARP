/**
 * Settings center labels (namespace `settings`) - English source locale.
 *
 * Covers the /app/settings page: appearance (theme, language, font size,
 * reduced motion) and the account/session panel. The sidebar label lives
 * in the eager `nav` namespace ('nav.item.settings') because the shell
 * renders before feature namespaces load.
 */
const settings = {
  // Page-level copy
  title: 'Settings',
  description: 'Console appearance and account session.',

  // Appearance panel
  'appearance.title': 'Appearance',
  'appearance.theme.label': 'Theme',
  'appearance.theme.aria': 'Theme',
  'appearance.theme.dark': 'Dark',
  'appearance.theme.light': 'Light',
  'appearance.language.label': 'Language',
  'appearance.language.description': 'Interface language of the console.',
  'appearance.fontScale.label': 'Font Size',
  'appearance.fontScale.aria': 'Font size',
  'appearance.fontScale.percent': '{{value}}%',
  'appearance.reducedMotion.label': 'Reduced Motion',
  'appearance.reducedMotion.description':
    'Turn off scanlines, chromatic effects and animations.',
  'appearance.reducedMotion.on': 'On',
  'appearance.reducedMotion.off': 'Off',

  // Account panel
  'account.title': 'Account',
  'account.username.label': 'Username',
  'account.username.placeholder': 'New username',
  'account.username.save': 'Save',
  'account.username.saving': 'Saving…',
  'account.username.saved': 'Saved.',
  'account.username.error': 'Failed to save the username.',
  'account.username.hint':
    'Display name - it may duplicate another user. Your account is always identified by the user ID below.',
  'account.role.label': 'Role',
  'account.role.user': 'User',
  'account.role.admin': 'Admin',
  'account.role.superAdmin': 'Super Admin',
  'account.userId.label': 'User ID',
  'account.sessionExpires.label': 'Session Expires',
  'account.stepUpUntil.label': 'Step-Up Valid Until',
  'account.stepUpUntil.none': 'None',
  'account.apiKeys.description': 'Manage API keys for programmatic access.',
  'account.apiKeys.link': 'API Keys',
  'account.logout': 'Sign Out',

  // States
  'error.load': 'Failed to load preferences.',
  'error.save': 'Failed to save preferences.',
};

export default settings;
