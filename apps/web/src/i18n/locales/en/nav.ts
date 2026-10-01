/**
 * Navigation labels (namespace `nav`) - English source locale.
 *
 * Keys are dotted: 'group.*' are sidebar/bottom-bar section headers,
 * 'item.*' are individual destinations. Adding a new nav destination in
 * src/app/navigation.ts means adding its key here AND in zh/nav.ts.
 */
const nav = {
  // Personal console section headers
  'group.home': 'Home',
  'group.agents': 'Agents',
  'group.work': 'Work',
  'group.trust': 'Trust',
  'group.access': 'Access',
  'group.network': 'Network',

  // Enterprise console section headers
  'group.commandCenter': 'Command Center',
  'group.topology': 'Topology',
  'group.traffic': 'Traffic',
  'group.governance': 'Governance',
  'group.continuity': 'Continuity',
  'group.audit': 'Audit',
  'group.system': 'System',

  // Personal console destinations
  'item.overview': 'Overview',
  'item.agents': 'Agents',
  'item.agentDetail': 'Agent Detail',
  'item.tasks': 'Tasks',
  'item.taskDetail': 'Task Detail',
  'item.approvals': 'Approvals',
  'item.connections': 'Connections',
  'item.apiKeys': 'API Keys',
  'item.localRouting': 'Local Routing',
  'item.settings': 'Settings',

  // Enterprise console destinations
  'item.networkScopes': 'Network Scopes',
  'item.networkZones': 'Network Zones',
  'item.relayNodes': 'Relay Nodes',
  'item.routePolicies': 'Route Policies',
  'item.routeDecisions': 'Route Decisions',
  'item.egressGateway': 'Egress Gateway',
  'item.dedicatedChannels': 'Dedicated Channels',
  'item.users': 'Users',
  'item.accessRequests': 'Access Requests',
  'item.approvalQueues': 'Approval Queues',
  'item.slaContinuity': 'SLA & Continuity',
  'item.auditLogs': 'Audit Logs',
  'item.systemHealth': 'System Health',
  'item.orgMembers': 'Organization Members',

  // Org-domain section header (org managers; hidden without a membership)
  'group.organization': 'Organization',
};

export default nav;
