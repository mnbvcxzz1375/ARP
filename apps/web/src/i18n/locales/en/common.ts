/**
 * Shared UI strings (namespace `common`) - English source locale.
 *
 * Starter set for shared components (ConfirmDialog/FormDialog/DataTable
 * defaults, loading/empty/error states) plus the sign-in page copy. The
 * sign-in strings live here rather than in a per-page namespace because
 * the login page is part of the public shell surface and is rendered
 * before any feature namespace is needed.
 *
 * Parallel translation shards: extend this file with the shared component
 * strings of your pages - do not create a second registration file
 * (locales are auto-gathered by import.meta.glob in ../core.ts).
 */
const common = {
  // Generic actions (shared dialogs, buttons)
  'action.confirm': 'Confirm',
  'action.cancel': 'Cancel',
  'action.close': 'Close',
  'action.save': 'Save',
  'action.delete': 'Delete',
  'action.retry': 'Retry',
  // PixelCopyButton (shared component; `common` is an eager namespace so the
  // key resolves inside every lazy page chunk)
  'action.copy': 'Copy',
  'action.copied': 'Copied',
  'action.copyFailed': 'Copy failed',

  // AgentAvatar (shared pixel component; `common` is an eager namespace so
  // the label resolves inside every lazy page chunk, including the admin
  // console which never loads the `agents` namespace)
  'agentAvatar.alt': 'Pixel avatar of agent {{name}}',

  // Generic states (LoadingState / EmptyState / ErrorState)
  'status.loading': 'Loading...',
  'status.empty': 'No results',
  'status.error': 'Something went wrong',

  // Pagination
  'pagination.page': 'Page {{current}} of {{total}}',
  'pagination.range': 'Showing {{start}}-{{end}} of {{total}}',
  'pagination.prev': 'Prev',
  'pagination.next': 'Next',

  // FormDialog buttons
  'action.submit': 'Submit',
  'status.saving': 'Saving...',

  // DataTable empty body
  'status.noData': 'No data',

  // LoadingState screen-reader label
  'status.loadingSr': 'Loading',

  // StepUpDialog
  'stepUp.title': 'Step-Up Verification',
  'stepUp.description': 'This action requires additional verification. Enter your API key to proceed.',
  'stepUp.placeholder': 'Enter your API key',
  'stepUp.error': 'Step-up verification failed',
  'stepUp.verifying': 'Verifying...',
  'stepUp.verify': 'Verify',

  // StatusBadge status labels (enum values rendered through the shared badge)
  'statusLabel.created': 'Created',
  'statusLabel.pending': 'Pending',
  'statusLabel.accepted': 'Accepted',
  'statusLabel.running': 'Running',
  'statusLabel.completed': 'Completed',
  'statusLabel.failed': 'Failed',
  'statusLabel.expired': 'Expired',
  'statusLabel.cancelled': 'Cancelled',
  'statusLabel.rejected': 'Rejected',
  // TaskStatus approval step (constants.py); feeds the journey map's
  // approval station badge (`common` is eager, every chunk resolves it).
  'statusLabel.awaitingApproval': 'Awaiting Approval',
  'statusLabel.online': 'Online',
  'statusLabel.offline': 'Offline',
  'statusLabel.healthy': 'Healthy',
  'statusLabel.degraded': 'Degraded',
  'statusLabel.down': 'Down',
  'statusLabel.unknown': 'Unknown',
  'statusLabel.queued': 'Queued',
  'statusLabel.routeSelected': 'Route Selected',
  'statusLabel.delivering': 'Delivering',
  'statusLabel.delivered': 'Delivered',
  'statusLabel.acknowledged': 'Acknowledged',
  'statusLabel.deliveryFailed': 'Delivery Failed',
  'statusLabel.unacked': 'Unacked',
  'statusLabel.approved': 'Approved',
  // M3 relay dataplane hop events (transports/relay_forwarder.py and the
  // dedicated-channel transport): same timeline as the delivery lifecycle.
  'statusLabel.relayForwarded': 'Relay Forwarded',
  'statusLabel.channelForwarded': 'Channel Forwarded',

  // RiskBadge levels (enum values rendered through the shared badge)
  'riskLevel.low': 'low',
  'riskLevel.medium': 'medium',
  'riskLevel.high': 'high',
  'riskLevel.critical': 'critical',

  // RoleBadge roles (enum values rendered through the shared badge)
  'role.user': 'user',
  'role.admin': 'admin',
  'role.superAdmin': 'super admin',

  // SecretMaskedText toggle (aria-label)
  'secret.show': 'Show secret',
  'secret.hide': 'Hide secret',

  // Sign-in page (public shell surface)
  'login.subtitle': 'Sign in to your dashboard',
  'login.username': 'Username',
  'login.apiKey': 'API Key',
  'login.submit': 'Sign In',
  'login.error': 'Invalid credentials. Please check your username and API key.',
  'login.requestAccess': 'Need access? Request it here',
  'login.docs': 'Read the docs',
  // Demo builds only (VITE_DEMO_MODE)
  'login.demoEntry': 'Enter demo as Super Admin',
};

export default common;
