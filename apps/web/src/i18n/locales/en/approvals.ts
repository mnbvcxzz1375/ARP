/**
 * Approvals page (namespace `approvals`) - English source locale.
 *
 * Covers features/approvals/ApprovalsPage.tsx (approval queue with
 * accept / reject confirm dialogs).
 * Translation rules: src/i18n/glossary.md.
 */
const approvals = {
  // Page chrome
  'page.title': 'Approvals',
  'error.load': 'Failed to load approvals',

  // Table columns
  'table.id': 'ID',
  'table.type': 'Type',
  'table.status': 'Status',
  'table.risk': 'Risk',
  'table.action': 'Action',
  'table.created': 'Created',
  'table.actions': 'Actions',

  // Row action buttons (idle / mutating states)
  'button.accept': 'Accept',
  'button.accepting': 'Accepting...',
  'button.reject': 'Reject',
  'button.rejecting': 'Rejecting...',

  // Confirm dialog
  'dialog.acceptTitle': 'Accept Approval',
  'dialog.rejectTitle': 'Reject Approval',
  'dialog.acceptMessage': 'Are you sure you want to accept this approval request?',
  'dialog.rejectMessage': 'Are you sure you want to reject this approval request?',
  'dialog.acceptConfirm': 'Accept',
  'dialog.rejectConfirm': 'Reject',

  // Mutation fallback errors
  'error.acceptFailed': 'Failed to accept approval',
  'error.rejectFailed': 'Failed to reject approval',
};

export default approvals;
