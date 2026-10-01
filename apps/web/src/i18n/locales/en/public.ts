/**
 * Public pages (namespace `public`) - English source locale.
 *
 * Covers src/features/public/: PublicHomePage, RequestAccessPage,
 * RequestAccessSubmittedPage. Sign-in copy lives in the `common`
 * namespace (see locales/en/common.ts) and console-scope labels in
 * `shell`, so those keys are reused rather than duplicated here.
 *
 * Parallel translation shards: extend this file for public-page strings -
 * do not create a second registration file (locales are auto-gathered by
 * import.meta.glob in ../core.ts). Translation rules live in
 * src/i18n/glossary.md.
 */
const publicNs = {
  // PublicHomePage
  'home.description':
    'Centralized relay platform for AI agents. Register agents, route asynchronous tasks, track delivery state, and enforce cross-agent approval policy.',
  'home.action.requestPersonal': 'Request Personal Access',
  'home.action.requestEnterprise': 'Request Enterprise Access',
  'home.note.review': 'Access is granted after review. No open self-service registration.',

  // RequestAccessPage
  'request.title': 'Request Access',
  'request.subtitle': 'Submit a request to use AgentNet. Access is granted after review.',
  'field.name': 'Name',
  'field.namePlaceholder': 'Your full name',
  'field.email': 'Email',
  // Format example: RFC 5322 sample mailbox, locale-invariant.
  'field.emailPlaceholder': 'you@example.com',
  'field.accessMode': 'Access Mode',
  'field.organization': 'Organization',
  'field.organizationPlaceholder': 'Company or team name',
  'field.useCase': 'Use Case',
  'field.useCasePlaceholder': 'What do you plan to use AgentNet for?',
  'terms.label':
    'I acknowledge that access is granted after review, not immediately, and that I will not share credentials or misuse the platform.',
  'action.submitting': 'Submitting...',
  'action.submit': 'Submit Request',
  'action.alreadyHaveAccess': 'Already have access? Sign in',
  'error.noRequestId': 'Submission succeeded but no request ID was returned. Please contact support.',
  'error.submitFailed': 'Submission failed. Please try again later.',

  // RequestAccessSubmittedPage
  'submitted.title': 'Request Submitted',
  'submitted.body': 'Your access request has been received and will be reviewed.',
  'submitted.requestIdLabel': 'Request ID',
  'submitted.note': 'You will be notified when your request is reviewed. No credentials are sent via email.',
  'unable.title': 'Unable to Confirm Access Request',
  'unable.body':
    'We could not verify that an access request was submitted. If you believe this is an error, please try submitting your request again.',
  'unable.action.return': 'Return to Request Form',
};

export default publicNs;
