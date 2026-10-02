/**
 * Personal routing page (namespace `routing`) - English source locale.
 *
 * Covers features/routing/PersonalRoutingPage.tsx (routing scope toggles,
 * routing mode strip, edge relay health cards, recent route decisions).
 * Translation rules: src/i18n/glossary.md.
 */
const routing = {
  // Page chrome
  'page.title': 'My Routing',
  'error.loadScope': 'Failed to load routing scope',
  'error.loadEdgeRelays': 'Failed to load edge relays',
  'error.loadRouteDecisions': 'Failed to load route decisions',
  'error.updateScope': 'Failed to update scope',

  // Routing scope section
  'section.scope': 'Routing Scope',
  'field.defaultRelayType': 'Default Relay Type',
  'field.edgeRelay': 'Edge Relay',
  'field.edgeRelayHint': 'Opt in to sending via personal edge relay nodes. Any available personal edge relay may be used — relays are not isolated per user.',
  'field.secureChannel': 'Secure Channel',
  'field.secureChannelHint': 'Enable end-to-end encrypted channels',

  // Routing mode section
  'section.mode': 'Routing Mode',
  'mode.fast': 'Fast',
  'mode.fastDescription': 'Lowest latency, may skip reliability checks',
  'mode.normal': 'Normal',
  'mode.normalDescription': 'Balanced latency and reliability',
  'mode.reliable': 'Reliable',
  'mode.reliableDescription': 'Maximum delivery guarantee, higher latency',
  'mode.switchHint': 'Routing mode can be switched anytime, takes effect immediately',

  // Edge relay health section
  'section.edgeHealth': 'Edge Relay Health',
  'empty.noEdgeRelays': 'No personal edge relays configured',
  'relay.load': 'Load',
  'relay.latency': 'Latency',
  'relay.successRate': 'Success Rate',
  'relay.healthy': 'Healthy',
  'fieldValue.yes': 'Yes',
  'fieldValue.no': 'No',

  // Recent route decisions section
  'section.recentDecisions': 'Recent Route Decisions',
  'table.taskId': 'Task ID',
  'table.routeType': 'Route Type',
  'table.risk': 'Risk',
  'table.fallbackFrom': 'Fallback From',
  'table.fallbackReason': 'Fallback Reason',
  'table.shadow': 'Shadow',
  'table.decisionTime': 'Decision (ms)',
  'table.created': 'Created',
};

export default routing;
