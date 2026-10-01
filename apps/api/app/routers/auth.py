from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.user import User
from app.services.api_key_service import create_api_key, list_api_keys, revoke_api_key
from app.services.auth import authenticate
from app.services.user_service import create_user


router = APIRouter(prefix="/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=128,
        description="Display label for the new user. May duplicate an "
        "existing username; the returned user_id is the canonical "
        "identifier.",
    )
    key_name: str = Field(
        default="default",
        min_length=1,
        max_length=256,
        description="Human-readable name for the issued API key.",
    )


class RegisterResponse(BaseModel):
    user_id: str = Field(description="User UUID.")
    username: str = Field(description="Registered username.")
    api_key: str = Field(description="One-time raw API key. Store it securely.")


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256, description="Human-readable API key name.")
    expires_at: datetime | None = Field(default=None, description="Optional API key expiry time.")


class CreateApiKeyResponse(BaseModel):
    api_key_id: str = Field(description="API key UUID.")
    key_prefix: str = Field(description="Non-secret API key prefix for identification.")
    name: str = Field(description="Human-readable API key name.")
    expires_at: datetime | None = Field(description="Optional expiry time.")
    api_key: str = Field(description="One-time raw API key. Store it securely.")


class ApiKeyResponse(BaseModel):
    api_key_id: str = Field(description="API key UUID.")
    key_prefix: str = Field(description="Non-secret API key prefix for identification.")
    name: str = Field(description="Human-readable API key name.")
    expires_at: datetime | None = Field(description="Optional expiry time.")
    is_revoked: bool = Field(description="Whether this API key has been revoked.")
    created_at: datetime = Field(description="Creation time.")


class ApiKeyListResponse(BaseModel):
    api_keys: list[ApiKeyResponse] = Field(description="API keys for the authenticated user.")
    total: int = Field(description="Total API keys for the authenticated user.")


class RevokeApiKeyRequest(BaseModel):
    allow_last_key: bool = Field(
        default=False,
        description="Set true to allow revoking the user's final active API key.",
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    summary="Register a new user and issue an API key",
    description=(
        "Create a new user and return a newly issued API key. Usernames are "
        "display labels and may be non-unique (the user_id in the response is "
        "the canonical identifier); registering an existing name never issues "
        "a key for that account. The raw API key is shown only in this "
        "response."
    ),
)
async def register(
    body: RegisterRequest, session: AsyncSession = Depends(get_session)
):
    user = await create_user(body.username, session)
    _, api_key = await create_api_key(session, user, name=body.key_name)
    await session.commit()
    return RegisterResponse(
        user_id=str(user.id),
        username=user.username,
        api_key=api_key,
    )


@router.get(
    "/api-keys",
    response_model=ApiKeyListResponse,
    summary="List API keys",
    description="List API keys owned by the authenticated user. Raw key material is never returned.",
)
async def list_api_keys_endpoint(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
):
    keys = await list_api_keys(session, user)
    return ApiKeyListResponse(
        api_keys=[_api_key_to_response(key) for key in keys],
        total=len(keys),
    )


@router.post(
    "/api-keys",
    response_model=CreateApiKeyResponse,
    status_code=201,
    summary="Create an API key",
    description="Issue a new API key for the authenticated user. The raw key is returned only once.",
)
async def create_api_key_endpoint(
    body: CreateApiKeyRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
):
    key, raw = await create_api_key(
        session,
        user,
        name=body.name,
        expires_at=body.expires_at,
    )
    await session.commit()
    return CreateApiKeyResponse(
        api_key_id=str(key.id),
        key_prefix=key.key_prefix,
        name=key.name,
        expires_at=key.expires_at,
        api_key=raw,
    )


@router.post(
    "/api-keys/{api_key_id}/revoke",
    response_model=ApiKeyResponse,
    summary="Revoke an API key",
    description=(
        "Revoke an API key owned by the authenticated user. By default the API refuses "
        "to revoke the user's final active key to avoid accidental lockout."
    ),
)
async def revoke_api_key_endpoint(
    api_key_id: str,
    body: RevokeApiKeyRequest | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
):
    key = await revoke_api_key(
        session,
        user,
        api_key_id=UUID(api_key_id),
        allow_last_key=body.allow_last_key if body else False,
    )
    await session.commit()
    return _api_key_to_response(key)


def _api_key_to_response(key) -> ApiKeyResponse:
    return ApiKeyResponse(
        api_key_id=str(key.id),
        key_prefix=key.key_prefix,
        name=key.name,
        expires_at=key.expires_at,
        is_revoked=key.is_revoked,
        created_at=key.created_at,
    )
