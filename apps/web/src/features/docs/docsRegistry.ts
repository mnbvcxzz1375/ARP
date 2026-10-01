/**
 * Docs site content registry.
 *
 * - Markdown pages are imported raw from the repository docs/ directory
 *   (Vite `?raw`), so the docs site always renders the committed docs.
 * - The repository docs are bilingual by document: eight are written in
 *   English, thirteen in Chinese. Each side gets a mirror under
 *   ./content/{en,zh}/ (also `?raw`), bound through `sourceEn` /
 *   `sourceZh` and selected by locale in docSourceFor(), so every doc
 *   renders fully English under 'en' and fully Chinese under 'zh'.
 *   The repository files themselves are not modified by these mirrors.
 * - One exception: docs/sdk-python-quickstart.md has no en mirror on
 *   purpose. Its rendered Chinese heading is pinned by
 *   DocsLayout.test.tsx and e2e/docs.spec.ts; see the entry below.
 * - The OpenAPI spec is imported from packages/protocol/openapi, the same
 *   artifact scripts/export_openapi.py exports in CI. No manual sync.
 *
 * Navigation strings (group headers, doc titles) live in the `docs`
 * i18n namespace; see src/i18n/locales/{en,zh}/docs.ts.
 */

import quickstartRaw from '../../../../../docs/quickstart.md?raw';
import architectureRaw from '../../../../../docs/architecture.md?raw';
import securityModelRaw from '../../../../../docs/security-model.md?raw';
import protocolRaw from '../../../../../docs/protocol.md?raw';
import apiExamplesRaw from '../../../../../docs/api-examples.md?raw';
import openapiDocRaw from '../../../../../docs/openapi.md?raw';
import cliRaw from '../../../../../docs/cli.md?raw';
import sdkQuickstartRaw from '../../../../../docs/sdk-python-quickstart.md?raw';
import sdkPythonRaw from '../../../../../docs/sdk-python.md?raw';
import openclawAdapterRaw from '../../../../../docs/openclaw-adapter.md?raw';
import consoleRbacRaw from '../../../../../docs/dashboard-rbac.md?raw';
import consoleSecurityRaw from '../../../../../docs/dashboard-security.md?raw';
import consoleDeployRaw from '../../../../../docs/dashboard-deploy.md?raw';
import opsProductionDeployRaw from '../../../../../docs/production-deploy.md?raw';
import opsChecklistRaw from '../../../../../docs/production-checklist.md?raw';
import opsCloseoutRaw from '../../../../../docs/production-closeout.md?raw';
import opsCiCdRaw from '../../../../../docs/ci-cd.md?raw';
import opsBackupRestoreRaw from '../../../../../docs/backup-restore.md?raw';
import opsSecretsRotationRaw from '../../../../../docs/secrets-rotation.md?raw';
import opsObservabilityRaw from '../../../../../docs/observability.md?raw';
import opsIncidentRaw from '../../../../../docs/incident-secret-leak.md?raw';
import openapiSpecRaw from '../../../../../packages/protocol/openapi/agentnet.openapi.json';

// Chinese mirrors of the eight repository docs that are still written in
// English. The other thirteen docs/*.md files are already Chinese, so they
// need no mirror and fall through to their repository source.
import protocolZhRaw from './content/zh/protocol.md?raw';
import quickstartZhRaw from './content/zh/quickstart.md?raw';
import cliZhRaw from './content/zh/cli.md?raw';
import consoleRbacZhRaw from './content/zh/dashboard-rbac.md?raw';
import consoleSecurityZhRaw from './content/zh/dashboard-security.md?raw';
import consoleDeployZhRaw from './content/zh/dashboard-deploy.md?raw';
import opsCiCdZhRaw from './content/zh/ci-cd.md?raw';
import opsProductionDeployZhRaw from './content/zh/production-deploy.md?raw';
import opsChecklistZhRaw from './content/zh/production-checklist.md?raw';
import opsCloseoutZhRaw from './content/zh/production-closeout.md?raw';

// English mirrors of the twelve repository docs that are written in Chinese
// (or carry a Chinese heading, like quickstart) but are not pinned by tests.
// The eight English repository docs need no en mirror. sdk-python-quickstart
// is deliberately excluded: its Chinese heading is pinned by
// DocsLayout.test.tsx and e2e/docs.spec.ts.
import quickstartEnRaw from './content/en/quickstart.md?raw';
import architectureEnRaw from './content/en/architecture.md?raw';
import securityModelEnRaw from './content/en/security-model.md?raw';
import apiExamplesEnRaw from './content/en/api-examples.md?raw';
import openapiDocEnRaw from './content/en/openapi.md?raw';
import cliEnRaw from './content/en/cli.md?raw';
import sdkPythonEnRaw from './content/en/sdk-python.md?raw';
import openclawAdapterEnRaw from './content/en/openclaw-adapter.md?raw';
import opsBackupRestoreEnRaw from './content/en/backup-restore.md?raw';
import opsSecretsRotationEnRaw from './content/en/secrets-rotation.md?raw';
import opsObservabilityEnRaw from './content/en/observability.md?raw';
import opsIncidentEnRaw from './content/en/incident-secret-leak.md?raw';

/** Sidebar groups in display order (the API Reference group is last). */
export type DocsGroupId =
  | 'quickstart'
  | 'protocol'
  | 'rest'
  | 'websocket'
  | 'cli'
  | 'sdk'
  | 'adapters'
  | 'console'
  | 'ops';

export const DOC_GROUP_ORDER: DocsGroupId[] = [
  'quickstart',
  'protocol',
  'rest',
  'websocket',
  'cli',
  'sdk',
  'adapters',
  'console',
  'ops',
];

export interface DocEntry {
  /** URL segment under /docs/ (also the lookup key). */
  docId: string;
  group: DocsGroupId;
  /** Dotted i18n key inside the `docs` namespace. */
  titleKey: string;
  /**
   * Raw markdown source (repository docs/*.md; the locale fallback when no
   * mirror applies).
   */
  source: string;
  /**
   * Chinese markdown mirror, only present for the repository docs that are
   * written in English. Absent means the repository source is already
   * Chinese and is reused for 'zh'.
   */
  sourceZh?: string;
  /**
   * English markdown mirror, only present for the repository docs that are
   * written in Chinese (or carry a Chinese heading). Absent means the
   * repository source is already English and is reused for 'en'.
   */
  sourceEn?: string;
}

export const DOCS_ENTRIES: DocEntry[] = [
  // Quickstart
  { docId: 'quickstart', group: 'quickstart', titleKey: 'title.quickstart', source: quickstartRaw, sourceZh: quickstartZhRaw, sourceEn: quickstartEnRaw },
  { docId: 'architecture', group: 'quickstart', titleKey: 'title.architecture', source: architectureRaw, sourceEn: architectureEnRaw },

  // Protocol
  { docId: 'security-model', group: 'protocol', titleKey: 'title.securityModel', source: securityModelRaw, sourceEn: securityModelEnRaw },
  { docId: 'protocol', group: 'protocol', titleKey: 'title.protocol', source: protocolRaw, sourceZh: protocolZhRaw },

  // REST API
  { docId: 'api-examples', group: 'rest', titleKey: 'title.apiExamples', source: apiExamplesRaw, sourceEn: apiExamplesEnRaw },
  { docId: 'openapi', group: 'rest', titleKey: 'title.openapi', source: openapiDocRaw, sourceEn: openapiDocEnRaw },

  // WebSocket (same source doc as 'protocol', navigated from the transport
  // angle; shares its zh mirror so zh renders Chinese too)
  { docId: 'websocket', group: 'websocket', titleKey: 'title.wsTransport', source: protocolRaw, sourceZh: protocolZhRaw },

  // CLI
  { docId: 'cli', group: 'cli', titleKey: 'title.cli', source: cliRaw, sourceZh: cliZhRaw, sourceEn: cliEnRaw },

  // Python SDK
  // sdk-python-quickstart has NO sourceEn on purpose: its Chinese heading
  // '# Python SDK 快速上手' is pinned by DocsLayout.test.tsx and
  // e2e/docs.spec.ts under the default (en) locale.
  { docId: 'sdk-python-quickstart', group: 'sdk', titleKey: 'title.sdkQuickstart', source: sdkQuickstartRaw },
  { docId: 'sdk-python', group: 'sdk', titleKey: 'title.sdkPython', source: sdkPythonRaw, sourceEn: sdkPythonEnRaw },

  // Adapters
  { docId: 'openclaw-adapter', group: 'adapters', titleKey: 'title.openclawAdapter', source: openclawAdapterRaw, sourceEn: openclawAdapterEnRaw },

  // Console guide
  { docId: 'dashboard-rbac', group: 'console', titleKey: 'title.consoleRbac', source: consoleRbacRaw, sourceZh: consoleRbacZhRaw },
  { docId: 'dashboard-security', group: 'console', titleKey: 'title.consoleSecurity', source: consoleSecurityRaw, sourceZh: consoleSecurityZhRaw },
  { docId: 'dashboard-deploy', group: 'console', titleKey: 'title.consoleDeploy', source: consoleDeployRaw, sourceZh: consoleDeployZhRaw },

  // Deploy & ops
  { docId: 'production-deploy', group: 'ops', titleKey: 'title.opsProductionDeploy', source: opsProductionDeployRaw, sourceZh: opsProductionDeployZhRaw },
  { docId: 'production-checklist', group: 'ops', titleKey: 'title.opsChecklist', source: opsChecklistRaw, sourceZh: opsChecklistZhRaw },
  { docId: 'production-closeout', group: 'ops', titleKey: 'title.opsCloseout', source: opsCloseoutRaw, sourceZh: opsCloseoutZhRaw },
  { docId: 'ci-cd', group: 'ops', titleKey: 'title.opsCiCd', source: opsCiCdRaw, sourceZh: opsCiCdZhRaw },
  { docId: 'backup-restore', group: 'ops', titleKey: 'title.opsBackupRestore', source: opsBackupRestoreRaw, sourceEn: opsBackupRestoreEnRaw },
  { docId: 'secrets-rotation', group: 'ops', titleKey: 'title.opsSecretsRotation', source: opsSecretsRotationRaw, sourceEn: opsSecretsRotationEnRaw },
  { docId: 'observability', group: 'ops', titleKey: 'title.opsObservability', source: opsObservabilityRaw, sourceEn: opsObservabilityEnRaw },
  { docId: 'incident-secret-leak', group: 'ops', titleKey: 'title.opsIncident', source: opsIncidentRaw, sourceEn: opsIncidentEnRaw },
];

export const DOCS_BY_ID: ReadonlyMap<string, DocEntry> = new Map(
  DOCS_ENTRIES.map((entry) => [entry.docId, entry]),
);

/**
 * Resolve the markdown body for one doc under the active locale.
 *
 * 'zh' prefers the Chinese mirror, 'en' (and any other locale) prefers the
 * English mirror; when an entry has no mirror for that locale the committed
 * repository source renders as-is. This keeps every doc fully English under
 * 'en' and fully Chinese under 'zh' regardless of which language the
 * repository file itself is written in.
 */
export function docSourceFor(entry: DocEntry, locale: string): string {
  if (locale === 'zh' && entry.sourceZh) return entry.sourceZh;
  if (locale !== 'zh' && entry.sourceEn) return entry.sourceEn;
  return entry.source;
}

// ---------------------------------------------------------------------------
// OpenAPI spec typing (minimal: only what the API Reference page renders).
// ---------------------------------------------------------------------------

export interface OpenApiParameter {
  name: string;
  in: string;
  required?: boolean;
  description?: string;
  schema?: {
    type?: string;
    format?: string;
    enum?: unknown[];
  };
}

export interface OpenApiOperation {
  method: string;
  path: string;
  summary?: string;
  description?: string;
  tags?: string[];
  operationId?: string;
  parameters?: OpenApiParameter[];
}

export interface OpenApiSpec {
  info?: { title?: string; version?: string; description?: string };
  paths?: Record<string, Record<string, unknown>>;
}

interface Specish {
  info?: { title?: string; version?: string; description?: string };
  paths?: Record<string, Record<string, unknown>>;
}

const spec: Specish = openapiSpecRaw as unknown as Specish;

export const OPENAPI_SPEC: OpenApiSpec = spec;

/** Known tag display order for the API Reference page; unknown tags sort after. */
export const API_TAG_ORDER = [
  'public',
  'auth',
  'dashboard-auth',
  'agents',
  'tasks',
  'approvals',
  'connections',
  'personal',
  'routing',
  'continuity',
  'sla',
  'dashboard',
  'dashboard-user',
  'dashboard-admin',
  'health',
];

const HTTP_METHODS = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'] as const;

/** Flatten the OpenAPI paths object into operations grouped by first tag. */
export function collectOpenApiOperations(spec: OpenApiSpec): OpenApiOperation[] {
  const operations: OpenApiOperation[] = [];
  for (const [path, pathItem] of Object.entries(spec.paths ?? {})) {
    if (!pathItem || typeof pathItem !== 'object') continue;
    for (const method of HTTP_METHODS) {
      const op = (pathItem as Record<string, unknown>)[method] as
        | Record<string, unknown>
        | undefined;
      if (!op || typeof op !== 'object') continue;
      operations.push({
        method: method.toUpperCase(),
        path,
        summary: op.summary as string | undefined,
        description: op.description as string | undefined,
        tags: (op.tags as string[] | undefined) ?? [],
        operationId: op.operationId as string | undefined,
        parameters: (op.parameters as OpenApiParameter[] | undefined) ?? [],
      });
    }
  }
  return operations;
}
