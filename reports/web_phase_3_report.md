# Phase Web 3 Report: RBAC Permission Helpers

**Date:** 2026-05-19
**Status:** Complete

## Goal

Build backend RBAC layer: permission helper module and FastAPI dependencies for endpoint protection. No endpoint-level permission guards yet — infrastructure only.

## Files Changed

| File | Operation |
|------|-----------|
| `apps/api/app/services/rbac_service.py` | NEW — Permission constants, role mapping, `has_permission`, `has_step_up` |
| `apps/api/app/dependencies/rbac.py` | NEW — `require_permission`, `require_step_up`, `require_high_risk` dependencies |
| `apps/api/tests/test_phase_web_3_rbac.py` | NEW — 15 unit tests |

## Commands Executed

```bash
pytest apps/api/tests/test_phase_web_3_rbac.py -v
```

## Test Results

- TestRoleHierarchy: 3 passed (user ⊂ admin ⊂ super_admin nesting verified)
- TestHasPermission: 8 passed (own perms, global read, disabled user, unknown role, orphaned perm check)
- TestHasStepUp: 4 passed (None, expired, valid, edge case: exactly-now returns False)

## Security Verification

| Check | Result |
|-------|--------|
| No role string comparison in permission logic | PASS — all checks go through `has_permission()` |
| Disabled users get no permissions (even super_admin) | PASS |
| Unknown role returns False (no crash) | PASS |
| Permission check errors return generic messages | PASS — "Insufficient permissions" |
| Step-up check uses `step_up_until > now` (strict) | PASS — exactly-now returns False |
| High-risk requires super_admin + step-up | PASS — `require_high_risk` checks both |
| No permission name leaks in error responses | PASS |

## Unfinished Items

None. Phase 3 scope (RBAC infrastructure) is complete.

## Risks and Follow-up

- Phase 4 will apply these dependencies to actual endpoints.
- Permission constants are defined but not yet referenced by any endpoint — this is by design.
- The `_forbidden()` function uses `ErrorCode.INVALID_REQUEST` with a generic message. If a more specific error code is needed in the future, a new `PERMISSION_DENIED` code can be added to `protocol/constants.py`.
