"""API key lifecycle service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.api_key import ApiKey
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.services.audit_service import write_audit
from app.services.auth import generate_api_key


async def create_api_key(
    session: AsyncSession,
    user: User,
    *,
    name: str,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    if expires_at is not None and expires_at <= datetime.now(UTC):
        # A past expiry would be rejected by authenticate() on first use,
        # handing the user an instantly-dead key.
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "expires_at must be in the future",
            status_code=400,
        )
    raw, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(
        user_id=user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.flush()
    await write_audit(
        session,
        actor_type="user",
        actor_id=str(user.id),
        action="api_key.created",
        resource_type="api_key",
        resource_id=str(api_key.id),
        details={"key_prefix": api_key.key_prefix, "name": api_key.name},
    )
    return api_key, raw


async def list_api_keys(session: AsyncSession, user: User) -> list[ApiKey]:
    result = await session.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_api_key(
    session: AsyncSession,
    user: User,
    *,
    api_key_id: uuid.UUID,
    allow_last_key: bool = False,
) -> ApiKey:
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == api_key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise DomainException(
            ErrorCode.INVALID_TOKEN,
            f"API key {api_key_id} not found",
            status_code=404,
        )
    if api_key.is_revoked:
        return api_key

    if not allow_last_key:
        # Lock this user's key rows for the duration of the transaction so two
        # concurrent revokes cannot both pass the "last active key" check and
        # lock the user out (check-then-act race).
        active_count = await _active_api_key_count(
            session, user, exclude_id=api_key.id, for_update=True
        )
        if active_count == 0:
            raise DomainException(
                ErrorCode.INVALID_REQUEST,
                "Refusing to revoke the last active API key without allow_last_key=true",
                status_code=409,
                details={"api_key_id": str(api_key.id)},
            )

    api_key.is_revoked = True
    api_key.revoked_at = datetime.now(UTC)
    await session.flush()
    await write_audit(
        session,
        actor_type="user",
        actor_id=str(user.id),
        action="api_key.revoked",
        resource_type="api_key",
        resource_id=str(api_key.id),
        details={"key_prefix": api_key.key_prefix, "name": api_key.name},
    )
    return api_key


async def _active_api_key_count(
    session: AsyncSession,
    user: User,
    *,
    exclude_id: uuid.UUID | None = None,
    for_update: bool = False,
) -> int:
    """Count the user's active (unrevoked, unexpired) keys.

    With for_update=True the user's key rows are locked (SELECT ... FOR UPDATE)
    so the count cannot be raced by a concurrent revoke of another key.
    Returns the count of matching rows, optionally excluding one key id.
    """
    now = datetime.now(UTC)
    stmt = select(ApiKey).where(ApiKey.user_id == user.id)
    if exclude_id is not None:
        stmt = stmt.where(ApiKey.id != exclude_id)
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    keys = list(result.scalars().all())
    return sum(
        1
        for k in keys
        if not k.is_revoked and (k.expires_at is None or k.expires_at > now)
    )
