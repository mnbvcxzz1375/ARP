import base64
import binascii
import hashlib
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.agent import Agent
from app.models.agent_token import AgentToken
from app.models.user import User
from app.protocol.constants import ErrorCode, InboundPolicy
from app.services.agent_number import generate_agent_number


AGENT_TOKEN_PREFIX = "agt_sk_"

# E2EE trust root (M1): raw public key length for X25519 / Ed25519.
PUBLIC_KEY_RAW_LENGTH = 32
PUBLIC_KEYS_VERSION = 1


def validate_public_keys(public_keys: dict[str, Any]) -> dict[str, Any]:
    """Validate a published composite public-key bundle.

    Accepts {"kem": <base64>, "sig": <base64>, "v": 1} (``v`` defaults to
    1 when omitted) and returns the normalized column value. Raises
    DomainException(INVALID_REQUEST) on malformed input — the platform
    must never store a key bundle it cannot interpret.
    """
    if not isinstance(public_keys, dict):
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "public_keys must be an object",
            status_code=422,
        )
    version = public_keys.get("v", PUBLIC_KEYS_VERSION)
    if version != PUBLIC_KEYS_VERSION:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"unsupported public_keys version: {version!r}",
            status_code=422,
        )
    for field in ("kem", "sig"):
        value = public_keys.get(field)
        if not isinstance(value, str) or not value:
            raise DomainException(
                ErrorCode.INVALID_REQUEST,
                f"public_keys.{field} must be a non-empty base64 string",
                status_code=422,
            )
        try:
            raw = base64.standard_b64decode(value.encode("ascii"))
        except (binascii.Error, ValueError) as exc:
            raise DomainException(
                ErrorCode.INVALID_REQUEST,
                f"public_keys.{field} is not valid base64: {exc}",
                status_code=422,
            ) from exc
        if len(raw) != PUBLIC_KEY_RAW_LENGTH:
            raise DomainException(
                ErrorCode.INVALID_REQUEST,
                (
                    f"public_keys.{field} must decode to "
                    f"{PUBLIC_KEY_RAW_LENGTH} bytes, got {len(raw)}"
                ),
                status_code=422,
            )
    return {"kem": public_keys["kem"], "sig": public_keys["sig"], "v": version}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_agent_token() -> tuple[str, str, str]:
    raw = AGENT_TOKEN_PREFIX + secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    token_prefix = raw[:16]
    return raw, token_hash, token_prefix


async def create_agent(
    session: AsyncSession,
    owner: User,
    name: str,
    runtime: str,
    *,
    description: str | None = None,
    capabilities: list[str] | None = None,
    inbound_policy: str = "request_approval",
    discoverable: bool = False,
    public_keys: dict[str, Any] | None = None,
) -> Agent:
    if inbound_policy not in {p.value for p in InboundPolicy}:
        raise DomainException(
            ErrorCode.INVALID_AGENT_POLICY,
            f"Invalid inbound_policy: {inbound_policy}",
            status_code=422,
        )

    validated_public_keys = (
        validate_public_keys(public_keys) if public_keys is not None else None
    )

    agent_number = generate_agent_number()
    raw_token, token_hash, token_prefix = _generate_agent_token()

    agent = Agent(
        owner_id=owner.id,
        agent_number=agent_number,
        name=name,
        runtime=runtime,
        description=description,
        capabilities=capabilities or [],
        inbound_policy=inbound_policy,
        discoverable=discoverable,
        public_keys=validated_public_keys,
    )
    session.add(agent)
    await session.flush()

    agent_token = AgentToken(
        agent_id=agent.id,
        token_hash=token_hash,
        token_prefix=token_prefix,
    )
    session.add(agent_token)
    await session.flush()

    agent._raw_token = raw_token
    return agent


async def get_agent_by_id(
    session: AsyncSession, agent_id: uuid.UUID, owner: User
) -> Agent:
    stmt = select(Agent).where(Agent.id == agent_id, Agent.owner_id == owner.id)
    result = await session.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent is None:
        raise DomainException(
            ErrorCode.AGENT_NOT_FOUND,
            f"Agent {agent_id} not found",
            status_code=404,
        )
    return agent


async def list_agents(
    session: AsyncSession,
    owner: User,
    *,
    page: int = 1,
    page_size: int = 20,
    status_filter: str | None = None,
    search: str | None = None,
    order: str = "newest",
) -> tuple[list[Agent], int]:
    stmt = select(Agent).where(Agent.owner_id == owner.id)
    if status_filter:
        stmt = stmt.where(Agent.status == status_filter)
    if search:
        stmt = stmt.where(
            Agent.name.ilike(f"%{search}%") | Agent.agent_number.ilike(f"%{search}%")
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    stmt = stmt.order_by(Agent.created_at.asc() if order == "oldest" else Agent.created_at.desc(), Agent.id).offset(
        (page - 1) * page_size
    ).limit(page_size)
    result = await session.execute(stmt)
    agents = list(result.scalars().all())

    return agents, total


async def rotate_agent_token(
    session: AsyncSession, agent_id: uuid.UUID, owner: User
) -> str:
    agent = await get_agent_by_id(session, agent_id, owner)

    stmt = select(AgentToken).where(
        AgentToken.agent_id == agent.id, AgentToken.is_revoked == False
    )
    result = await session.execute(stmt)
    old_tokens = list(result.scalars().all())
    for t in old_tokens:
        t.is_revoked = True
        t.rotated_at = datetime.now(UTC)

    raw_token, token_hash, token_prefix = _generate_agent_token()
    new_token = AgentToken(
        agent_id=agent.id,
        token_hash=token_hash,
        token_prefix=token_prefix,
    )
    session.add(new_token)
    await session.flush()

    return raw_token


async def delete_agent(
    session: AsyncSession, agent_id: uuid.UUID, owner: User
) -> None:
    agent = await get_agent_by_id(session, agent_id, owner)
    await session.delete(agent)
    await session.flush()
