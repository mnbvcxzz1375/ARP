# Phase 6: Frontend Pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build React + TypeScript frontend application serving User Console and Admin Operations Console.

**Architecture:** Vite + React + TypeScript + Tailwind CSS. TanStack Query for data fetching. React Router for navigation. Axios with CSRF interceptors. Base components + feature modules.

**Tech Stack:** React 18, Vite, TypeScript, Tailwind CSS, TanStack Query, React Router, Axios, Lucide Icons, Vitest, Playwright.

---

## File Structure

```text
apps/web/
├── src/
│   ├── api/          # Axios instance, interceptors, typed endpoints
│   ├── app/          # React Router routes, layouts
│   ├── components/   # Reusable UI components
│   ├── features/     # Feature modules (auth, users, agents, etc.)
│   ├── hooks/        # Custom hooks (useAuth, useCSRF, useStepUp)
│   ├── lib/          # Utils, constants, types
│   └── main.tsx      # Entry point
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
└── package.json
```

---

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `apps/web/package.json`, `apps/web/tsconfig.json`, `apps/web/vite.config.ts`, `apps/web/tailwind.config.ts`, `apps/web/postcss.config.js`, `apps/web/index.html`

- [ ] **Step 1: Initialize the project**

Create `apps/web` directory structure and config files.

**Dependencies:**
- `react`, `react-dom`, `react-router-dom`
- `@tanstack/react-query`, `axios`
- `clsx`, `tailwind-merge`
- `lucide-react`
- Dev: `typescript`, `vite`, `@vitejs/plugin-react`, `tailwindcss`, `postcss`, `autoprefixer`, `vitest`, `@testing-library/react`, `@playwright/test`

- [ ] **Step 2: Configure Vite**

`vite.config.ts`:
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/v1': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
});
```

- [ ] **Step 3: Configure Tailwind**

`tailwind.config.ts`:
```typescript
import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: { extend: {} },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 4: Verify build**

```bash
cd apps/web && npm install && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "chore: scaffold apps/web with Vite, React, TypeScript, Tailwind"
```

---

### Task 2: API Client & Auth Context

**Files:**
- Create: `apps/web/src/api/client.ts`, `apps/web/src/hooks/useAuth.ts`, `apps/web/src/hooks/useCSRF.ts`

- [ ] **Step 1: Create Axios instance with interceptors**

`apps/web/src/api/client.ts`:
```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_AGENTNET_API_BASE || '/v1',
  withCredentials: true,
});

// CSRF Interceptor
api.interceptors.request.use((config) => {
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('agentnet_csrf='))
    ?.split('=')[1];
  if (csrfToken && ['post', 'put', 'patch', 'delete'].includes((config.method || '').toLowerCase())) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});

// Auth Interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export default api;
```

- [ ] **Step 2: Create Auth hooks**

`apps/web/src/hooks/useAuth.ts`:
```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/client';

export const useAuth = () => {
  return useQuery({
    queryKey: ['auth/me'],
    queryFn: () => api.get('/dashboard/auth/me').then(r => r.data),
    retry: false,
  });
};

export const useLogin = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ username, api_key }: { username: string; api_key: string }) =>
      api.post('/dashboard/auth/login', { username, api_key }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth/me'] });
      window.location.href = '/app/overview';
    },
  });
};

export const useLogout = () => {
  return useMutation({
    mutationFn: () => api.post('/dashboard/auth/logout'),
    onSuccess: () => {
      window.location.href = '/login';
    },
  });
};
```

- [ ] **Step 3: Setup TanStack Query Provider**

Wrap app in `QueryClientProvider` in `main.tsx`.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/api apps/web/src/hooks apps/web/src/main.tsx
git commit -m "feat: setup API client, CSRF interceptor, and auth hooks"
```

---

### Task 3: Base UI Components

**Files:**
- Create: `apps/web/src/components/` (Shell, Sidebar, TopBar, DataTable, StatCard, Badge, Dialog, Button, Input)

- [ ] **Step 1: Create Layout Components**

- `AppShell`: User console layout (Sidebar + TopBar + Content).
- `AdminShell`: Admin console layout (Sidebar + TopBar + Content + Danger banner).
- `Sidebar`: Navigation links based on role.
- `TopBar`: User info, logout button, role badge.

- [ ] **Step 2: Create UI Components**

- `DataTable`: Simple Tailwind table with pagination props.
- `StatCard`: KPI card with label, value, and optional delta.
- `StatusBadge`, `RiskBadge`, `RoleBadge`: Colored badges.
- `ConfirmDialog`, `StepUpDialog`: Modal dialogs for actions.
- `DangerActionButton`: Red button with confirmation.
- `JsonPreview`, `SecretMaskedText`: Content display components.
- `EmptyState`, `ErrorState`, `LoadingState`: Feedback states.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components
git commit -m "feat: add base UI components and layouts"
```

---

### Task 4: Login & Auth Flow

**Files:**
- Create: `apps/web/src/features/auth/LoginPage.tsx`, `apps/web/src/app/routes.tsx`

- [ ] **Step 1: Create Login Page**

Form with username and API key inputs. Uses `useLogin`. Shows errors. Redirects to `/app/overview` on success.

- [ ] **Step 2: Setup Routing**

`apps/web/src/app/routes.tsx`:
- Public: `/login`
- Protected User: `/app/*` (redirects to `/login` if not auth)
- Protected Admin: `/admin/*` (redirects to `/app/overview` if not admin)
- Fallback: Redirect to `/app/overview` or `/login`.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/auth apps/web/src/app/routes.tsx
git commit -m "feat: add login page and routing setup"
```

---

### Task 5: User Dashboard Pages

**Files:**
- Create: `apps/web/src/features/overview/`, `apps/web/src/features/agents/`, `apps/web/src/features/tasks/`, `apps/web/src/features/approvals/`, `apps/web/src/features/connections/`, `apps/web/src/features/api-keys/`

- [ ] **Step 1: Overview Page**

Fetches `/v1/dashboard/overview`. Displays `StatCard`s and recent lists. Polls every 15s.

- [ ] **Step 2: Agents Page**

List agents (`GET /v1/dashboard/agents`). Create agent modal. Agent detail view. Update/Delete actions.

- [ ] **Step 3: Tasks Page**

List tasks (`GET /v1/dashboard/tasks`). Filters. Task detail with masked payload/result.

- [ ] **Step 4: Approvals & Connections**

Approvals list with accept/reject. Connections/Firewall view.

- [ ] **Step 5: API Keys Page**

List keys. Create key (show secret once). Revoke key.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/features/overview apps/web/src/features/agents apps/web/src/features/tasks apps/web/src/features/approvals apps/web/src/features/connections apps/web/src/features/api-keys
git commit -m "feat: add user dashboard pages"
```

---

### Task 6: Admin Dashboard Pages

**Files:**
- Create: `apps/web/src/features/admin/`

- [ ] **Step 1: Admin Overview**

Global KPIs. Polls every 30s.

- [ ] **Step 2: Users & Agents**

User list with disable/enable/revoke actions. User detail with audit. Agent list with disable action.

- [ ] **Step 3: Tasks & Audit**

Global task list. Cancel/Expire actions with step-up. Audit log query and export.

- [ ] **Step 4: System Health**

Health dashboard. No secrets. Worker status. Migration revision.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/admin
git commit -m "feat: add admin dashboard pages"
```

---

### Task 7: Testing & Polish

**Files:**
- Create: `apps/web/src/**/*.test.tsx`, `apps/web/tests/e2e/`

- [ ] **Step 1: Component Tests**

Test critical components: `DataTable`, `StatusBadge`, `ConfirmDialog`, `SecretMaskedText`.

- [ ] **Step 2: E2E Tests**

Playwright tests: Login flow, User creates agent, Admin disables user, Step-up flow.

- [ ] **Step 3: Polish**

Tailwind theme tweaks. Responsive layout checks. Loading skeletons. Error boundaries.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src apps/web/tests
git commit -m "test: add component and E2E tests for dashboard"
```

---

### Task 8: Phase Report

**Files:**
- Create: `reports/web_phase_6_report.md`

- [ ] **Step 1: Create report**

Document tech stack, component inventory, routing map, test coverage, deployment notes.

- [ ] **Step 2: Commit**

```bash
git add -f reports/web_phase_6_report.md
git commit -m "docs: add Phase Web 6 report"
```

---

## Plan Self-Review

**1. Spec coverage:**
- Scaffolding & Config → Task 1 ✅
- API Client & Auth → Task 2 ✅
- Base Components → Task 3 ✅
- Login & Routing → Task 4 ✅
- User Pages → Task 5 ✅
- Admin Pages → Task 6 ✅
- Testing & Polish → Task 7 ✅

**2. Placeholder scan:** No TBD/TODO. All code blocks are complete or clearly scoped.

**3. Type consistency:**
- Axios instance uses base URL from env.
- CSRF interceptor reads cookie and sets header.
- Auth hook invalidates query on login.
- Routing protects `/admin/*` with role check.
- Components use Tailwind classes consistently.
