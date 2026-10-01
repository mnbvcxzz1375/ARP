/**
 * Organization-domain console E2E (org manager / org member).
 *
 * The org-domain permissions live in the backend RBAC map
 * (apps/api/app/services/rbac_service.py, ORG_ROLE_PERMISSIONS) and are
 * echoed by GET /v1/dashboard/auth/me. This spec drives the frontend
 * behavior only: Playwright route interception stands in for /me and the
 * organization endpoints, modeling the two org personas exactly as the
 * backend contract describes them (manager = the full org set,
 * member = ['overview:read:org'] only).
 *
 * No backend or seeded e2e user is required: nothing here touches a real
 * session. Compare no-access.spec.ts for the same interception style.
 */
import { test, expect } from '@playwright/test';

const ORG_ID = '00000000-0000-0000-0000-0000000000a1';

/** /me as the backend echoes it for an org MANAGER. */
const ORG_MANAGER_ME = {
  user_id: '00000000-0000-0000-0000-000000000010',
  username: 'org_manager',
  role: 'user',
  permissions: [
    'overview:read:org',
    'agent:read:org',
    'task:read:org',
    'approval:handle:org',
    'connection:read:org',
    'policy:read:org',
    'sla:read:org',
    'audit:read:org',
    'org:manage',
  ],
  organizations: [{ org_id: ORG_ID, name: 'E2E Org', role: 'manager' }],
  csrf_required: true,
  session_expires_at: '2030-01-01T00:00:00+00:00',
  step_up_until: null,
};

/** /me as the backend echoes it for a plain org MEMBER. */
const ORG_MEMBER_ME = {
  ...ORG_MANAGER_ME,
  user_id: '00000000-0000-0000-0000-000000000011',
  username: 'org_member',
  permissions: ['overview:read:org'],
  organizations: [{ org_id: ORG_ID, name: 'E2E Org', role: 'member' }],
};

/** GET /v1/organizations/mine as either persona sees it. */
const ORG_MINE = {
  organizations: [
    {
      org_id: ORG_ID,
      name: 'E2E Org',
      slug: 'e2e-org',
      role: 'manager',
      is_disabled: false,
      created_at: '2026-01-01T00:00:00Z',
    },
  ],
};

const ORG_MEMBERS = {
  members: [
    {
      user_id: '00000000-0000-0000-0000-000000000010',
      username: 'org_manager',
      role: 'manager',
      created_at: '2026-01-15T10:00:00Z',
    },
    {
      user_id: '00000000-0000-0000-0000-000000000011',
      username: 'org_member',
      role: 'member',
      created_at: '2026-02-01T10:00:00Z',
    },
  ],
};

/** Stand-in for GET /v1/dashboard/admin/overview so the Overview page
 *  renders its stat cards instead of an error state. */
const ADMIN_OVERVIEW = {
  total_users: 2,
  active_users: 2,
  disabled_users: 0,
  total_agents: 4,
  online_agents: 3,
  active_ws_connections: 5,
  tasks_1h: 6,
  tasks_24h: 20,
  tasks_7d: 120,
  failed_tasks: 1,
  expired_tasks: 2,
  pending_approvals: 1,
  pending_messages: 0,
  retry_worker_health: 'ok',
  timeout_worker_health: 'ok',
};

/** Intercept every endpoint the org persona consoles hit on this page. */
async function mockOrgWorld(
  page: import('@playwright/test').Page,
  me: typeof ORG_MANAGER_ME,
  mine = ORG_MINE,
) {
  await page.route('**/v1/dashboard/auth/me', (route) => route.fulfill({ json: me }));
  await page.route('**/v1/organizations/mine', (route) =>
    route.fulfill({ json: mine }),
  );
  await page.route(`**/v1/organizations/${ORG_ID}/members`, (route) => {
    if (route.request().method() === 'GET') {
      route.fulfill({ json: ORG_MEMBERS });
    } else {
      route.fulfill({ status: 200, json: { ok: true } });
    }
  });
  await page.route('**/v1/dashboard/admin/overview', (route) =>
    route.fulfill({ json: ADMIN_OVERVIEW }),
  );
}

test.describe('Org manager console (org-domain permissions)', () => {
  test('enterprise console is reachable: overview, banner org context, members nav', async ({
    page,
  }) => {
    await mockOrgWorld(page, ORG_MANAGER_ME);

    await page.goto('/enterprise/overview');

    // The guard admits the org manager (org-domain strings alone).
    await expect(page).toHaveURL(/\/enterprise\/overview$/);

    // The shell rendered: enterprise banner carries the org context.
    const banner = page.locator('[data-testid="enterprise-banner"]');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText('E2E Org');

    // Overview nav entry (org variant of overview:read:global) +
    // the org members destination gated on org:manage.
    const nav = page.locator('nav').first();
    await expect(nav.getByText('Overview')).toBeVisible();
    await expect(nav.getByRole('link', { name: 'Organization Members' })).toBeVisible();
    // Org-permission items (route policies via policy:read:org) are
    // visible; global-only ones (Users) are not.
    await expect(nav.getByText('Route Policies')).toBeVisible();
    await expect(nav.getByText('Users')).not.toBeVisible();

    // The overview page itself renders (intercepted admin overview).
    await expect(
      page.getByRole('heading', { name: 'Enterprise Overview' }),
    ).toBeVisible();
  });

  test('organization members page lists members and offers add/remove actions', async ({
    page,
  }) => {
    await mockOrgWorld(page, ORG_MANAGER_ME);

    await page.goto('/enterprise/members');
    await expect(page).toHaveURL(/\/enterprise\/members$/);

    await expect(page.getByRole('heading', { name: 'Organization Members' })).toBeVisible();
    // The table cells (the sidebar footer also echoes the username).
    await expect(page.getByRole('cell', { name: 'org_manager' })).toBeVisible();
    await expect(page.getByRole('cell', { name: 'org_member' })).toBeVisible();
    await expect(page.getByText('Manager', { exact: true })).toBeVisible();
    await expect(page.getByText('Member', { exact: true })).toBeVisible();

    // A manager of this org can manage members.
    await expect(page.getByRole('button', { name: 'Add Member' })).toBeVisible();
    await expect(page.getByText('Change Role').first()).toBeVisible();
  });

  test('personal console shows the enterprise entry for an org manager', async ({ page }) => {
    await mockOrgWorld(page, ORG_MANAGER_ME);

    await page.goto('/app/overview');
    await expect(page).toHaveURL(/\/app\/overview$/);

    // The scope switcher is visible for org-domain accounts...
    const scopeSwitcher = page.getByRole('button', { name: 'Enterprise' }).first();
    await expect(scopeSwitcher).toBeVisible();
  });
});

test.describe('Org member console (read-only)', () => {
  test('overview is reachable but the members entry and actions stay hidden', async ({
    page,
  }) => {
    await mockOrgWorld(page, ORG_MEMBER_ME, {
      organizations: [{ ...ORG_MINE.organizations[0], role: 'member' }],
    });

    await page.goto('/enterprise/overview');

    // The guard admits the member's single org permission (read-only).
    await expect(page).toHaveURL(/\/enterprise\/overview$/);
    const nav = page.locator('nav').first();
    await expect(nav.getByText('Overview')).toBeVisible();

    // No org members entry (org:manage not held), no admin-level entries.
    await expect(nav.getByText('Organization Members')).not.toBeVisible();
    await expect(nav.getByText('Users')).not.toBeVisible();
    await expect(nav.getByText('Audit Logs')).not.toBeVisible();
    await expect(nav.getByText('System Health')).not.toBeVisible();

    // The org context echo shows the membership role.
    const banner = page.locator('[data-testid="enterprise-banner"]');
    await expect(banner).toContainText('Member');
  });

  test('members page renders read-only: notice shown, no add/remove actions', async ({ page }) => {
    await mockOrgWorld(page, ORG_MEMBER_ME, {
      organizations: [{ ...ORG_MINE.organizations[0], role: 'member' }],
    });

    await page.goto('/enterprise/members');
    await expect(page).toHaveURL(/\/enterprise\/members$/);

    // Shell + page render without an Add Member affordance.
    await expect(page.getByRole('heading', { name: 'Organization Members' })).toBeVisible();
    await expect(page.getByText(/only an organization manager can/i)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Member' })).not.toBeVisible();
    await expect(page.getByText('Change Role')).not.toBeVisible();
  });
});

test.describe('Personal accounts keep the pre-org behavior', () => {
  test('a pure personal account still lands on /no-access from the enterprise console', async ({
    page,
  }) => {
    await page.route('**/v1/dashboard/auth/me', (route) =>
      route.fulfill({
        json: {
          ...ORG_MANAGER_ME,
          username: 'plain_user',
          permissions: ['agent:read:own', 'task:read:own'],
          organizations: [],
        },
      }),
    );

    await page.goto('/enterprise/overview');
    await expect(page).toHaveURL(/\/no-access$/);
  });
});
