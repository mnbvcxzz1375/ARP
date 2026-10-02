/**
 * Overview page (namespace `overview`) - English source locale.
 *
 * Covers src/features/overview/OverviewPage.tsx plus the archipelago layout
 * & panel components (top bar, summary strip, agent detail panel + drawer,
 * activity bar, list mode). KPI stat cards and the recent tasks / recent
 * approvals tables belong to the legacy overview chrome.
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

  // Hero panel (relay scene + status summary line)
  'hero.title': 'Relay station status',
  'hero.agentA': 'Agent A',
  'hero.agentB': 'Agent B',

  // Status summary sentence
  'summary.failed': '{{count}} parcels stuck, need attention',
  'summary.idle': 'Station idling, no agent on duty',
  'summary.nominal': 'Station nominal · {{count}} agents online',

  // Sections
  'section.recentTasks': 'Recent Tasks',
  'section.recentApprovals': 'Recent Approvals',

  // Shared table columns
  'table.id': 'ID',
  'table.status': 'Status',
  'table.created': 'Created',
  'table.risk': 'Risk',

  // ── Archipelago top bar (64px, page-level) ──
  'brand.name': 'AgentNet',
  'brand.sub': 'Relay Archipelago',
  'viewMode.label': 'View mode',
  'viewMode.map': 'Map',
  'viewMode.list': 'List',
  'action.createTask': 'Create task',
  'action.taskGuide': 'Task guide',
  'action.account': 'Account',
  'gap.createTask':
    'No create-task entry in the console yet — the quickstart shows the API path.',

  // ── Summary strip (inline counts above the map) ──
  'strip.title': 'Overview summary',
  'strip.lag': 'Refreshes about every 15–30 seconds; counts may lag.',
  'strip.error': 'Overview summary unavailable (permission or network).',

  // ── Map canvas states, legend and overflow entry ──
  'map.label': 'Archipelago map',
  'map.noEdges': 'No routes between the visible islands yet.',
  'map.overflow': '{{hidden}} more islands not shown ({{total}} total).',
  'map.openList': 'Open list mode',
  'map.overflowList': 'Open list mode',
  'map.allAgents': 'All agents',
  'map.edgeNote': 'Routes stand for task relationships, not live network topology.',
  'map.legend.taskEdge': 'Task route',
  'map.legend.pendingEdge': 'Connection request',
  'map.tooltip.taskEdge': '{{from}} → {{to}} · task route',
  'map.tooltip.pendingEdge': '{{from}} → {{to}} · connection request',

  // ── Island node labels ──
  'island.label': '{{name}} ({{number}}), {{status}}, island {{index}} of {{total}}',

  // ── Bottom activity bar (128px) ──
  'activity.title': 'Recent activity',
  'activity.empty':
    'No agent actions yet. This list only carries audit events performed by your own ' +
    'agents (create, update, token rotation, firewall changes) — not presence flips, and ' +
    'actions you perform as a user are excluded too, so it is often empty.',
  'activity.viewAll': 'View all agents',

  // ── Agent detail panel (right column, 320px) and mobile drawer ──
  'detail.title': 'Agent details',
  'detail.noneSelected': 'Select an island to inspect its agent.',
  'detail.field.runtime': 'Runtime',
  'detail.field.policy': 'Inbound policy',
  'detail.field.discoverable': 'Discoverable',
  'detail.field.capabilities': 'Capabilities',
  'detail.field.created': 'Created',
  'detail.capabilities.empty': 'No capability tags registered.',
  'detail.value.yes': 'Yes',
  'detail.value.no': 'No',
  'detail.section.tasks': 'Related tasks',
  'detail.section.pending': 'Pending connection requests',
  'detail.pending.empty':
    'No pending request matched this agent — either there are none, or their target ' +
    'side is not exposed by the connections API.',
  'detail.task.empty': 'No task on the current page involves this agent.',
  'detail.task.scopeNote': 'Shows up to 5 priority tasks; open the task list for all records.',
  'detail.task.from': 'From',
  'detail.task.to': 'To',
  'detail.action.viewAgent': 'View agent page',
  'detail.action.viewTask': 'View task',
  'drawer.close': 'Close agent details',
  'drawer.defaultTitle': 'Agent details',

  // ── List mode ──
  'list.title': 'Agents',
  'list.empty': 'No agents visible to this account.',
  'list.action.view': 'Open',
  'list.pending.title': 'Pending connection requests',
  'list.pending.targetUnknown': 'target not exposed by the API',
  'list.pending.note':
    'Pending requests usually come from agents of other users, so they are listed here ' +
    'rather than drawn on the map.',

  // ── Data gaps stated in the UI (never faked fields) ──
  'gap.progress': 'Progress is only available on the task detail page; the list API does not return it.',
  'gap.tasks': 'The task feed failed to load (permission or network); routes and related tasks are unavailable.',
  'gap.connections': 'The connections feed failed to load (permission or network); pending requests are unavailable.',
  "map.group": "Archipelago {{page}} / {{pages}} · {{total}} agents",
  "map.previousGroup": "Previous archipelago",
  "map.nextGroup": "Next archipelago",
  "traffic.count": "{{active}} active · {{failed}} issues",
  "traffic.focus": "Focus: {{name}}",
  "traffic.showAll": "Show all routes",
  "traffic.breakdown": "{{running}} running · {{queued}} waiting · {{awaiting}} approvals · {{failed}} issues",
  "traffic.allTasks": "All tasks for this agent →",
  "traffic.scope": "Island totals include tasks sent or received by this agent; routes stay within this group. Issues: failed, expired or rejected in the last 24h.",
  "traffic.unavailable": "Task aggregates unavailable; partial task samples are not used as totals.",
  "traffic.focusHint": "Select an island to focus its task routes",
  "traffic.routeCounts": "Aggregated route counts",
  "traffic.scopeTitle": "Sent and received tasks · issues in 24h · count scope",
};

export default overview;
