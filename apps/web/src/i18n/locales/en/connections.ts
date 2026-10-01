/**
 * Connections page (namespace `connections`) - English source locale.
 *
 * Covers features/connections/ConnectionsPage.tsx (agent inbound-policy
 * firewall table + pending connection requests) and the shared pixel
 * primitives in features/connections/pixel-ui.tsx used by other user-facing
 * pages (YesNoChip).
 * Translation rules: src/i18n/glossary.md.
 */
const connections = {
  // Page chrome
  'page.title': 'Connections & Firewall',
  'error.load': 'Failed to load connections',

  // Agents panel
  'panel.agents': 'Agents',
  'table.agentNumber': 'Agent Number',
  'table.inboundPolicy': 'Inbound Policy',
  'table.pending': 'Pending',
  'table.accepted': 'Accepted',
  'table.rejected': 'Rejected',

  // Inbound policy enum labels (API values stay raw in `value`)
  'policy.private': 'private',
  'policy.contactsOnly': 'contacts_only',
  'policy.requestApproval': 'request_approval',
  'policy.public': 'public',

  // Saving indicator
  'status.saving': 'Saving...',

  // Pending requests panel
  'panel.pendingRequests': 'Pending Requests',
  'table.connectionId': 'ID',
  'table.agent': 'Agent',
  'table.requester': 'Requester',
  'table.requestedPolicy': 'Requested Policy',
  'table.created': 'Created',
  'table.actions': 'Actions',

  // Row action buttons (idle / mutating states)
  'button.accept': 'Accept',
  'button.accepting': 'Accepting...',
  'button.reject': 'Reject',
  'button.rejecting': 'Rejecting...',

  // Confirm dialog
  'dialog.acceptTitle': 'Accept Connection',
  'dialog.rejectTitle': 'Reject Connection',
  'dialog.acceptMessage': 'Are you sure you want to accept this connection request?',
  'dialog.rejectMessage': 'Are you sure you want to reject this connection request?',
  'dialog.acceptConfirm': 'Accept',
  'dialog.rejectConfirm': 'Reject',

  // Mutation fallback errors
  'error.acceptFailed': 'Failed to accept connection',
  'error.rejectFailed': 'Failed to reject connection',
  'error.firewallFailed': 'Failed to update firewall policy',

  // Shared chip (pixel-ui YesNoChip)
  'chip.yes': 'Yes',
  'chip.no': 'No',
};

export default connections;
