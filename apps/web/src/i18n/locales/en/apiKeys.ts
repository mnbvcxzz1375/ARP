/**
 * API Keys page (namespace `apiKeys`) - English source locale.
 *
 * Covers src/features/api-keys/ApiKeysPage.tsx: the create-key form,
 * the raw-key success panel, the key table and the revoke confirm
 * dialog. Shared action labels (Close / Cancel) come from the `common`
 * namespace and are reused rather than duplicated.
 *
 * Parallel translation shards: extend this file for api-keys-page
 * strings - do not create a second registration file (locales are
 * auto-gathered by import.meta.glob in ../core.ts). Translation rules
 * live in src/i18n/glossary.md.
 */
const apiKeys = {
  // Page chrome
  'title': 'API Keys',
  'error.load': 'Failed to load API keys',

  // Create API Key form
  'create.title': 'Create API Key',
  'create.field.name': 'Name',
  'create.field.namePlaceholder': 'My API Key',
  'create.field.expires': 'Expires At (optional)',
  'create.action.creating': 'Creating...',
  'create.action.submit': 'Create Key',
  'error.create': 'Failed to create API key',

  // Raw key success panel
  'created.title': 'API Key Created: {{name}}',
  'created.note': 'Copy this key now. You will not be able to see it again.',

  // Key table
  'table.name': 'Name',
  'table.keyPrefix': 'Key Prefix',
  'table.created': 'Created',
  'table.expires': 'Expires',
  'table.revoked': 'Revoked',
  'table.actions': 'Actions',
  'action.revoke': 'Revoke',

  // Revoke confirm dialog
  'confirm.revokeTitle': 'Revoke API Key',
  'confirm.revokeMessage': 'Are you sure you want to revoke "{{name}}"? This action cannot be undone.',
  'error.revoke': 'Failed to revoke API key',
};

export default apiKeys;
