# Phase 6 Design: Frontend Pages

**Date**: 2026-05-19
**Status**: Approved
**Scope**: AgentNet Enterprise Dashboard — Phase 6 of 13
**Predecessor**: Phase 5 (Admin Dashboard API)

## Summary

Build the React + TypeScript frontend application serving both the User Console and Admin Operations Console. The app integrates with the Phase 2-5 backend APIs, handling session auth, CSRF, and RBAC.

## Tech Stack

- **Framework**: React 18 + TypeScript
- **Build**: Vite
- **Styling**: Tailwind CSS + `clsx`
- **Routing**: React Router v6
- **Data Fetching**: TanStack Query v5
- **HTTP Client**: Axios (with interceptors for CSRF)
- **Icons**: Lucide React
- **Testing**: Vitest + React Testing Library + Playwright E2E

## Architecture

### Directory Structure

```text
apps/web/
├── src/
│   ├── api/          # Axios instance, interceptors, typed endpoints
│   ├── app/          # React Router routes, layouts
│   ├── components/   # Reusable UI components
│   ├── features/     # Feature modules (auth, users, agents, etc.)
│   ├── hooks/        # Custom hooks (useAuth, useCSRF, etc.)
│   ├── lib/          # Utils, constants, types
│   └── main.tsx      # Entry point
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
└── package.json
```

### Routing

```text
/                 → Redirect to /app/overview or /login
/login            → PublicLayout (Login page)
/app              → AppLayout (User Console)
  /overview       → User Overview
  /agents         → User Agents List
  /agents/:id     → User Agent Detail
  /tasks          → User Tasks List
  /tasks/:id      → User Task Detail
  /approvals      → User Approvals
  /connections    → User Connections/Firewall
  /api-keys       → User API Keys
/admin            → AdminLayout (Admin Console)
  /overview       → Admin Overview
  /users          → Admin Users List
  /users/:id      → Admin User Detail
  /agents         → Admin Agents List
  /agents/:id     → Admin Agent Detail
  /tasks          → Admin Tasks List
  /tasks/:id      → Admin Task Detail
  /audit          → Admin Audit Logs
  /system         → Admin System Health
```

### Layouts

- **PublicLayout**: Minimal layout for login/signup.
- **AppLayout**: User console layout with sidebar, top bar, auth check, CSRF provider.
- **AdminLayout**: Admin console layout with different sidebar, admin badge, high-risk warnings.

### State Management

- **TanStack Query**: Server state (API data, loading, error states).
- **React Context**: Client state (auth session, CSRF token, user role, theme).
- **Local State**: Form state, UI toggles.

### Security Integration

- **Session**: HttpOnly cookie (`agentnet_session`). Frontend never touches the token.
- **CSRF**: Cookie (`agentnet_csrf`) read by JS, sent in `X-CSRF-Token` header via Axios interceptor.
- **Auth Check**: `useAuth` hook checks `/v1/dashboard/auth/me`. Redirects to `/login` on 401.
- **RBAC**: `usePermissions` hook checks user role. Hides admin routes from non-admins. Shows/hides dangerous buttons.
- **Step-Up**: `useStepUp` hook manages step-up flow. Shows `StepUpDialog` before high-risk actions.

## Component Strategy

Base components follow the list in `web.md` Section 10:

- **Layout**: `AppShell`, `AdminShell`, `Sidebar`, `TopBar`
- **Data**: `DataTable`, `Pagination`, `FilterBar`
- **Feedback**: `StatCard`, `StatusBadge`, `RiskBadge`, `RoleBadge`, `EmptyState`, `ErrorState`, `LoadingState`
- **Actions**: `ConfirmDialog`, `StepUpDialog`, `DangerActionButton`
- **Content**: `JsonPreview`, `Timeline`, `AuditEventRow`, `SecretMaskedText`

Design principles:
- SaaS/ops tool style. High information density.
- Default to white background.
- Admin actions use red/danger styles.
- Long text/JSON collapsed by default.
- Secrets masked (`SecretMaskedText`).

## API Integration

Each feature module exposes TanStack Query hooks:

```typescript
// features/agents/api.ts
export const useAgents = (params: AgentListParams) =>
  useQuery({ queryKey: ['agents', params], queryFn: () => api.getAgents(params) });

export const useCreateAgent = () =>
  useMutation({ mutationFn: api.createAgent });
```

Axios instance configured with:
- Base URL from env `VITE_AGENTNET_API_BASE`.
- Credentials `include` (for cookies).
- Request interceptor: reads `agentnet_csrf` cookie, sets `X-CSRF-Token`.
- Response interceptor: handles 401 (redirect to login), 403 (show error), CSRF errors.

## Assumptions

- Backend APIs from Phase 2-5 are stable and documented in OpenAPI.
- No external UI library (MUI/AntD) — Tailwind + custom components for speed and bundle size.
- MVP uses polling for real-time updates (overview KPIs every 15s/30s). No WebSockets on frontend.
- Deployment: Static build served by nginx (from infra) or dev server for local.
