import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.api_key import ApiKey
from app.models.user import User


API_KEY_PREFIX = "ak_"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = hash_key(raw)
    key_prefix = raw[:16]
    return raw, key_hash, key_prefix


async def get_or_create_user(username: str, session: AsyncSession) -> User:
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is not None:
        return user
    user = User(username=username)
    session.add(user)
    await session.flush()
    return user


async def create_api_key_for_user(
    user: User, name: str, session: AsyncSession
) -> str:
    raw, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(
        user_id=user.id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=name,
    )
    session.add(api_key)
    await session.flush()
    return raw


async def authenticate(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_session),
) -> User:
    # Accept both X-API-Key and Authorization: Bearer <key>
    key = x_api_key
    if not key and authorization and authorization.startswith("Bearer "):
        key = authorization[7:]
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key or Authorization header",
        )
    key_hash = hash_key(key)
    stmt = (
        select(User)
        .join(ApiKey, ApiKey.user_id == User.id)
        .where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_revoked == False,
            or_(ApiKey.expires_at == None, ApiKey.expires_at > datetime.now(UTC)),
        )
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )
    return user
