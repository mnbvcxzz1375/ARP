/**
 * Admin console pages (namespace `admin`) - English source locale.
 *
 * Covers the 9 admin pages under src/features/admin/:
 * AdminOverviewPage, AdminAgentsPage, AdminAgentDetailPage,
 * AdminTasksPage, AdminTaskDetailPage, AdminUsersPage,
 * AdminUserDetailPage, AuditLogsPage, SystemHealthPage.
 *
 * Parallel translation shards: extend this file for admin-page strings -
 * do not create a second registration file (locales are auto-gathered
 * by import.meta.glob in ../core.ts). Translation rules live in
 * src/i18n/glossary.md.
 */
const admin = {
  // Shared across admin pages
  'action.view': 'View',
  'action.enable': 'Enable',
  'action.disable': 'Disable',
  'action.cancel': 'Cancel',
  'action.expire': 'Expire',
  'action.revokeKeys': 'Revoke Keys',
  'value.yes': 'Yes',
  'value.no': 'No',
  'value.never': 'Never',
  'hint.superAdminRequired': 'Super admin required',
  'hint.adminRequired': 'Admin required',
  'table.status': 'Status',
  'table.owner': 'Owner',
  'table.created': 'Created',
  'table.actions': 'Actions',
  'worker.retry': 'Retry Worker',
  'worker.timeout': 'Timeout Worker',

  // AdminOverviewPage
  'error.loadOverview': 'Failed to load admin overview',
  'title.overview': 'Admin Overview',
  'stat.totalUsers': 'Total Users',
  'stat.activeUsers': 'Active Users',
  'stat.disabledUsers': 'Disabled Users',
  'stat.totalAgents': 'Total Agents',
  'stat.onlineAgents': 'Online Agents',
  'stat.wsConnections': 'WS Connections',
  'stat.tasks1h': 'Tasks (1h)',
  'stat.tasks24h': 'Tasks (24h)',
  'stat.tasks7d': 'Tasks (7d)',
  'stat.failedTasks': 'Failed Tasks',
  'stat.expiredTasks': 'Expired Tasks',
  'stat.pendingApprovals': 'Pending Approvals',
  'stat.pendingMessages': 'Pending Messages',

  // AdminAgentsPage
  'error.loadAgents': 'Failed to load agents',
  'error.updateAgent': 'Failed to update agent',
  'title.agents': 'Agents',
  'agents.table.name': 'Name',
  'agents.table.agentNumber': 'Agent Number',
  'agents.table.runtime': 'Runtime',
  'agents.table.policy': 'Policy',
  'agents.table.tasks24h': 'Tasks (24h)',
  'agents.table.failed': 'Failed',
  'agents.confirm.disableTitle': 'Disable Agent',
  'agents.confirm.enableTitle': 'Enable Agent',
  'agents.confirm.disableMessage':
    'Disable agent "{{name}}"? It will go offline and stop accepting tasks.',
  'agents.confirm.enableMessage':
    'Enable agent "{{name}}"? It will be able to come online and accept tasks.',

  // AdminAgentDetailPage
  'error.loadAgentDetail': 'Failed to load agent detail',
  'back.agents': 'Back to Agents',
  'agentDetail.panel.coreIdentity': 'Core Identity',
  'agentDetail.field.agentNumber': 'Agent Number',
  'agentDetail.field.name': 'Name',
  'agentDetail.field.runtime': 'Runtime',
  'agentDetail.field.inboundPolicy': 'Inbound Policy',
  'agentDetail.field.discoverable': 'Discoverable',
  'agentDetail.field.updated': 'Updated',
  'agentDetail.field.failedTasks24h': 'Failed Tasks (24h)',
  'agentDetail.panel.capabilities': 'Capabilities',
  'agentDetail.text.none': 'None',
  'agentDetail.panel.tokenMetadata': 'Token Metadata',
  'agentDetail.field.tokenPrefix': 'Token Prefix',
  'agentDetail.field.tokenCreated': 'Token Created',
  'agentDetail.field.tokenRotated': 'Token Rotated',

  // AdminTasksPage
  'error.loadTasks': 'Failed to load tasks',
  'error.cancelTask': 'Failed to cancel task',
  'error.expireTask': 'Failed to expire task',
  'title.tasks': 'Tasks',
  'tasks.table.id': 'ID',
  'tasks.table.sender': 'Sender',
  'tasks.table.target': 'Target',
  'tasks.confirm.expireTitle': 'Expire Task',
  'tasks.confirm.cancelTitle': 'Cancel Task',
  'tasks.confirm.expireMessage':
    'Force expire task "{{id}}"? This will mark the task as expired and stop further processing.',
  'tasks.confirm.cancelRunningMessage':
    'Cancel running task "{{id}}"? This will immediately stop the task and may leave it in an incomplete state.',
  'tasks.confirm.cancelPendingMessage':
    'Cancel pending task "{{id}}"? The task will be marked as cancelled and will not execute.',
  'tasks.confirm.expireLabel': 'Expire Task',
  'tasks.confirm.cancelLabel': 'Cancel Task',

  // AdminTaskDetailPage
  'error.loadTaskDetail': 'Failed to load task detail',
  'back.tasks': 'Back to Tasks',
  'taskDetail.title': 'Task {{id}}',
  'taskDetail.panel.details': 'Details',
  'taskDetail.field.deliveryStatus': 'Delivery Status',
  'taskDetail.field.retryCount': 'Retry Count',
  'taskDetail.panel.content': 'Content',
  'taskDetail.field.payload': 'Payload',
  'taskDetail.field.result': 'Result',
  'taskDetail.field.error': 'Error',

  // AdminUsersPage
  'error.loadUsers': 'Failed to load users',
  'error.updateUser': 'Failed to update user',
  'error.revokeKeys': 'Failed to revoke keys',
  'title.users': 'Users',
  'users.table.username': 'Username',
  'users.table.role': 'Role',
  'users.table.disabled': 'Disabled',
  'users.table.agents': 'Agents',
  'users.table.apiKeys': 'API Keys',
  'users.table.failed': 'Failed',
  'users.confirm.revokeTitle': 'Force Revoke API Keys',
  'users.confirm.disableTitle': 'Disable User',
  'users.confirm.enableTitle': 'Enable User',
  'users.confirm.revokeMessage':
    'Revoke all API keys for user "{{name}}"? This will invalidate all their API keys immediately.',
  'users.confirm.disableMessage':
    'Disable user "{{name}}"? They will be unable to log in or use the platform.',
  'users.confirm.enableMessage':
    'Enable user "{{name}}"? They will regain access to the platform.',

  // AdminUserDetailPage
  'error.loadUserDetail': 'Failed to load user detail',
  'back.users': 'Back to Users',
  'userDetail.panel.userDetails': 'User Details',
  'userDetail.field.username': 'Username',
  'userDetail.field.role': 'Role',
  'userDetail.field.disabled': 'Disabled',
  'userDetail.field.agents': 'Agents',
  'userDetail.field.activeApiKeys': 'Active API Keys',
  'userDetail.field.tasks24h': 'Tasks (24h)',
  'userDetail.field.failedTasks24h': 'Failed Tasks (24h)',
  'userDetail.field.activeSessions': 'Active Sessions',
  'userDetail.field.recentAuditEvents': 'Recent Audit Events',

  // AuditLogsPage
  'error.loadAuditLogs': 'Failed to load audit logs',
  'title.auditLogs': 'Audit Logs',
  'audit.table.id': 'ID',
  'audit.table.actorType': 'Actor Type',
  'audit.table.actor': 'Actor',
  'audit.table.action': 'Action',
  'audit.table.resource': 'Resource',

  // SystemHealthPage
  'error.loadSystemHealth': 'Failed to load system health',
  'title.systemHealth': 'System Health',
  'health.tile.api': 'API',
  'health.tile.postgres': 'PostgreSQL',
  'health.tile.redis': 'Redis',
  'health.tile.httpsWss': 'HTTPS/WSS',
  'health.panel.systemInfo': 'System Info',
  'health.field.appVersion': 'App Version',
  'health.field.migration': 'Migration',
  'health.field.pendingQueue': 'Pending Queue',
  'health.panel.workers': 'Workers',
  'health.note.noSecrets': 'No secrets are exposed on this page.',
};

export default admin;
