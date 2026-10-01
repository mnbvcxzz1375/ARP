/**
 * Agents pages (namespace `agents`) - English source locale.
 *
 * Covers features/agents/AgentsPage.tsx (list) and AgentDetailPage.tsx.
 * Shared strings live in `common`; only agents-specific copy is here.
 * Translation rules: src/i18n/glossary.md.
 */
const agents = {
  // Page chrome
  'page.title': 'Agents',
  'error.load': 'Failed to load agents',
  'error.loadDetail': 'Failed to load agent detail',
  'action.backToList': 'Back to Agents',

  // List table (AgentsPage)
  'table.name': 'Name',
  'table.agentNumber': 'Agent Number',
  'table.view': 'View',
  'table.runtime': 'Runtime',
  'table.status': 'Status',
  'table.policy': 'Policy',
  'table.created': 'Created',

  // Detail page (AgentDetailPage)
  'section.coreIdentity': 'Core Identity',
  'field.agentNumber': 'Agent Number',
  'field.name': 'Name',
  'field.runtime': 'Runtime',
  'field.status': 'Status',
  'field.inboundPolicy': 'Inbound Policy',
  'field.discoverable': 'Discoverable',
  'field.created': 'Created',
  'field.updated': 'Updated',
  'fieldValue.yes': 'Yes',
  'fieldValue.no': 'No',
  'fieldValue.never': 'Never',

  // Capabilities section
  'section.capabilities': 'Capabilities',
  'empty.noCapabilities': 'None',

  // Token metadata section
  'section.tokenMetadata': 'Token Metadata',
  'field.tokenPrefix': 'Token Prefix',
  'field.tokenCreated': 'Token Created',
  'field.tokenRotated': 'Token Rotated',
};

export default agents;
