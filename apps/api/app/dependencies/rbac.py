"""RBAC FastAPI dependencies: require_permission, require_step_up, require_high_risk."""
from datetime import UTC, datetime

from fastapi import Depends

from app.dependencies.auth import CurrentSession
from app.exceptions import DomainException
from app.models.dashboard_session import DashboardSession
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.services.rbac_service import PERM_DISABLE_USER, has_permission, has_step_up


def _forbidden():
    """Raise 403 with generic message."""
    from fastapi import status as http_status
    raise DomainException(
        ErrorCode.INVALID_REQUEST,
        "Insufficient permissions for this operation",
        status_code=http_status.HTTP_403_FORBIDDEN,
    )


def _step_up_required():
    """Raise 403 STEP_UP_REQUIRED."""
    from fastapi import status as http_status
    raise DomainException(
        ErrorCode.STEP_UP_REQUIRED,
        "Step-up authentication required for this operation",
        status_code=http_status.HTTP_403_FORBIDDEN,
    )


def require_permission(permission: str):
    """Return a FASTAPI dependency that checks the given permission.

    Usage:
        @router.post("/agents")
        async def create_agent(
            ds: CurrentSession,
            _: User = Depends(require_permission("agent:create")),
        ):
            ...
    """
    def _check(ds: CurrentSession) -> User:
        if not has_permission(ds.user, permission):
            _forbidden()
        return ds.user
    return _check


def require_step_up():
    """Require valid step-up auth window.

    Usage:
        @router.post("/high-risk")
        async def high_risk(
            ds: CurrentSession,
            _: None = Depends(require_step_up()),
        ):
            ...
    """
    def _check(ds: CurrentSession) -> None:
        if not has_step_up(ds):
            _step_up_required()
    return _check


def require_high_risk():
    """Combined: super_admin + step-up required.

    Usage:
        @router.post("/disable-user")
        async def disable_user(
            ds: CurrentSession,
            _: None = Depends(require_high_risk()),
        ):
            ...
    """
    def _check(ds: CurrentSession) -> None:
        if not has_permission(ds.user, PERM_DISABLE_USER):
            _forbidden()
        if not has_step_up(ds):
            _step_up_required()
    return _check
