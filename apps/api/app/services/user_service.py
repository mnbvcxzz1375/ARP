"""User provisioning and identity resolution.

Identity model (migration 0030):
- ``user_id`` (UUID) is the canonical identifier everywhere internally
  (audit logs, RBAC, org memberships, API keys).
- ``username`` is a NON-unique display label. Same-named users are
  disambiguated in the UI with a short user_id suffix.

Resolution strategy for authentication: the raw API key uniquely
identifies a user (its hash matches exactly one active ApiKey row), so
authentication resolves key-first and never matches users by username.
This keeps duplicate usernames from creating ambiguity at login.

Registration always creates a NEW user: returning an API key for an
existing same-named account would hand one user's credentials to
another (the pre-0030 "get or create" semantics were only safe while
usernames were unique).
"""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.user import User

USERNAME_MIN = 1
USERNAME_MAX = 128
# Printable ASCII minus control characters; unicode letters are allowed.
_USERNAME_RE = re.compile(r"^[^\x00-\x1f\x7f]+$")


def validate_username(username: str) -> str:
    """Return the trimmed username or raise ValueError."""
    trimmed = username.strip()
    if not (USERNAME_MIN <= len(trimmed) <= USERNAME_MAX):
        raise ValueError("Username must be 1-128 characters.")
    if not _USERNAME_RE.match(trimmed):
        raise ValueError("Username must not contain control characters.")
    return trimmed


async def create_user(username: str, session: AsyncSession) -> User:
    """Create a new user. Usernames may duplicate; the caller's intent
    is always a fresh account (registration)."""
    user = User(username=validate_username(username))
    session.add(user)
    await session.flush()
    return user


async def find_user_by_api_key(
    session: AsyncSession, key_hash: str
) -> tuple[User, ApiKey] | None:
    """Resolve (user, api_key) for a raw key hash, or None.

    Key-first resolution: the ApiKey row is matched on its (unique) hash,
    then the user is loaded by primary key. Neither step matches users
    by username, so duplicate usernames cannot misroute authentication.

    A disabled user IS returned (with their valid key): the caller
    decides the response code (login answers 403 "account disabled" so
    the operator can tell a locked account from a bad key). Revoked or
    expired keys resolve to None.
    """
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_revoked.is_(False),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None
    if api_key.expires_at and api_key.expires_at <= datetime.now(UTC):
        return None
    user = await session.get(User, api_key.user_id)
    if user is None:
        return None
    return user, api_key


async def update_username(
    session: AsyncSession, user: User, username: str
) -> str:
    """Set a new display label for an existing user."""
    new_name = validate_username(username)
    user.username = new_name
    await session.flush()
    return new_name
