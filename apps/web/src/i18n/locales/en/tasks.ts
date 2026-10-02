/**
 * Tasks pages (namespace `tasks`) - English source locale.
 *
 * Covers features/tasks/TasksPage.tsx (list) and TaskDetailPage.tsx
 * (status / content / messages / progress / delivery events / route
 * decisions sections).
 * Translation rules: src/i18n/glossary.md.
 */
const tasks = {
  // Page chrome
  'page.title': 'Tasks',
  'page.detailTitle': 'Task {{taskId}}',
  'error.load': 'Failed to load tasks',
  'error.loadDetail': 'Failed to load task detail',
  'action.backToList': 'Back to Tasks',

  // Story empty state (TasksPage, empty list)
  'empty.title': 'The conveyor is quiet',
  'empty.subtitle': 'Send the first task and the first parcel rolls out.',
  // Points at the docs quickstart; no tasks/new route exists yet.
  'empty.action.quickstart': 'See how to send tasks',

  // List table (TasksPage)
  'table.id': 'ID',
  'table.view': 'View',
  'table.status': 'Status',
  'table.sender': 'Sender',
  'table.target': 'Target',
  'table.created': 'Created',

  // Status section
  'section.status': 'Status',
  'field.deliveryStatus': 'Delivery Status',
  'field.retryCount': 'Retry Count',
  'field.created': 'Created',
  'field.updated': 'Updated',

  // Content section
  'section.content': 'Content',
  'field.payload': 'Payload',
  'field.result': 'Result',
  'field.error': 'Error',
  // Encryption state of a preview (mirrors the backend read-side
  // degradation view, build_content_view: encrypted rows carry an
  // encrypted flag + raw ciphertext, malformed rows a parse-error flag).
  'content.encrypted': 'E2EE Ciphertext',
  'content.parseError': 'Ciphertext Parse Error',
  'content.keyId': 'Key ID',

  // Messages section
  'section.messages': 'Messages',
  'error.loadMessages': 'Failed to load messages',
  'table.messageId': 'ID',
  'table.type': 'Type',
  'table.delivery': 'Delivery',

  // Progress section
  'section.progress': 'Progress',
  'error.loadProgress': 'Failed to load progress',
  'table.seq': 'Seq',
  'table.percent': '%',
  'table.message': 'Message',

  // Delivery events section
  'section.deliveryEvents': 'Delivery Events',
  'error.loadDeliveryEvents': 'Failed to load delivery events',
  'empty.noDeliveryEvents': 'No delivery events recorded',
  'table.event': 'Event',
  'table.routeType': 'Route Type',
  'table.relayNode': 'Relay Node',
  'table.latency': 'Latency (ms)',
  'table.queueWait': 'Queue Wait (ms)',
  'table.errorCode': 'Error Code',

  // Journey map (TaskDetailPage): 5-station status line
  'section.journey': 'Journey',
  'journey.station.queued': 'Queued',
  'journey.station.delivery': 'Delivery',
  'journey.station.execution': 'Execution',
  'journey.station.approval': 'Approval',
  'journey.station.completed': 'Completed',
  // The failed endpoint only links when an error message exists (the error
  // section renders conditionally); otherwise it stays a plain-text hint.
  'journey.terminal.failed': 'Failed',
  'journey.terminal.cancelled': 'Cancelled',
  'journey.terminal.failedHint': 'See the error details below',

  // Route decisions section
  'section.routeDecisions': 'Route Decisions',
  'error.loadRouteDecisions': 'Failed to load route decisions',
  'empty.noRouteDecisions': 'No route decisions recorded',
  'table.risk': 'Risk',
  'table.fallbackReason': 'Fallback Reason',
  'table.decisionTime': 'Decision (ms)',
  'table.shadow': 'Shadow',
  'fieldValue.yes': 'Yes',
  'fieldValue.no': 'No',
  "filter.view": "Task view",
  "filter.view.all": "All tasks",
  "filter.view.attention": "Active and issues first",
  "filter.view.active": "Active tasks",
  "filter.view.history": "History",
  "filter.status": "Execution status",
  "filter.anyStatus": "Any status",
  "filter.agent": "Agent",
  "filter.anyAgent": "All agents",
  "filter.search": "Search tasks",
  "filter.placeholder": "Task ID, agent name or number",
  "filter.submit": "Search",
  "filter.reset": "Clear filters",
  "filter.total": "{{count}} matching tasks",
  "filter.empty": "No matching tasks",
  "filter.emptyHint": "Adjust or clear the filters and try again.",
  "filter.agentLimit": "The selector lists the first 200 agents; search other agents by name or number.",
  "filter.status.created": "Created",
  "filter.status.queued": "Queued",
  "filter.status.delivered": "Delivered",
  "filter.status.accepted": "Accepted",
  "filter.status.running": "Running",
  "filter.status.awaiting_approval": "Awaiting approval",
  "filter.status.completed": "Completed",
  "filter.status.failed": "Failed",
  "filter.status.cancelled": "Cancelled",
  "filter.status.expired": "Expired",
  "filter.status.rejected": "Rejected",
  "filter.scrollHint": "Swipe the table horizontally to see all columns.",
};

export default tasks;
