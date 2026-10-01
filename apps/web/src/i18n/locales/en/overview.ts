/**
 * Overview page (namespace `overview`) - English source locale.
 *
 * Covers src/features/overview/OverviewPage.tsx: KPI stat cards, the
 * recent tasks / recent approvals tables and the page-level error state.
 *
 * Parallel translation shards: extend this file for overview-page
 * strings - do not create a second registration file (locales are
 * auto-gathered by import.meta.glob in ../core.ts). Translation rules
 * live in src/i18n/glossary.md.
 */
const overview = {
  // Page chrome
  'title': 'Overview',
  'error.load': 'Failed to load overview',

  // KPI stat cards
  'stat.onlineAgents': 'Online Agents',
  'stat.tasksToday': 'Tasks Today',
  'stat.failedTasks': 'Failed Tasks',
  'stat.pendingApprovals': 'Pending Approvals',
  'stat.pendingMessages': 'Pending Messages',

  // Sections
  'section.recentTasks': 'Recent Tasks',
  'section.recentApprovals': 'Recent Approvals',

  // Shared table columns
  'table.id': 'ID',
  'table.status': 'Status',
  'table.created': 'Created',
  'table.risk': 'Risk',
};

export default overview;
