/**
 * Application shell strings (namespace `shell`) - English source locale.
 *
 * Covers DashboardShell (sidebar scope chrome, footer buttons, mobile
 * bottom bar, enterprise banner), PublicLayout footer chrome and the
 * LanguageSwitcher component itself.
 */
const shell = {
  // Scope chrome
  'console.personal': 'Personal Console',
  'console.enterprise': 'Enterprise Console',
  'scope.personal': 'Personal',
  'scope.enterprise': 'Enterprise',
  'banner.enterprise': 'Enterprise Console -- actions affect all users and relay infrastructure',

  // Sidebar controls
  'sidebar.expand': 'Expand sidebar',
  'sidebar.collapse': 'Collapse sidebar',
  'sidebar.resize': 'Resize sidebar width',
  'sidebar.resizeHint': 'Drag to resize, or focus and use Left / Right arrow keys',
  'sidebar.open': 'Open navigation',
  'sidebar.close': 'Close navigation',
  'sidebar.menu': 'Menu',

  // Mobile bottom navigation
  'bottomNav.aria': 'Primary',

  // Footer / bottom-bar buttons
  'theme.switchToLight': 'Switch to light theme',
  'theme.switchToDark': 'Switch to dark theme',
  'theme.label': 'Theme',
  'logout': 'Sign out',
  'docs.entry': 'Open the documentation site',
  'docs.label': 'Docs',

  // StationMaster mascot (sidebar footer identity row, mobile drawer)
  'mascot.alt': 'Station Master',

  // User footer
  'user.defaultName': 'User',
  'user.unknownRole': 'unknown',
  'user.userIdTitle': 'User ID:',

  // LanguageSwitcher
  'language.aria': 'Switch language',
  'language.toggle': 'Switch language',
  'language.en': 'EN',
  'language.zh': '中文',

  // Public footer
  'footer.poweredBy': 'AgentNet Relay Platform',

  // Demo mode banner (VITE_DEMO_MODE builds only)
  'demo.badge': 'Demo',
  'demo.banner': 'Demo mode -- all data is fictional and kept in memory',
  'demo.persona.label': 'Persona',
  'demo.persona.super_admin': 'Super Admin',
  'demo.persona.org_manager': 'Org Manager',
  'demo.persona.personal': 'Personal User',
  'demo.reset': 'Reset demo data',
  'demo.reset.aria': 'Reset the demo fixture world',
};

export default shell;
