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
};

export default tasks;
