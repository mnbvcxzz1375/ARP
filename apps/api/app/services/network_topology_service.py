"""Network Topology Service: manage enterprise network scopes and zones."""

import ipaddress
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.network_scope import NetworkScope
from app.models.network_zone import NetworkZone
from app.models.user import User
from app.protocol.constants import ErrorCode

logger = logging.getLogger(__name__)


def validate_network_cidr(network_cidr: str | None) -> None:
    """Registration-time validation of a scope's network_cidr.

    The egress policy decision point filters target IPs against this
    CIDR, so an unparseable value would silently disable the CIDR filter
    (fail open). Reject it here instead: it must parse as an IPv4/IPv6
    network via ipaddress. None or "" (clear) are allowed.
    """
    if network_cidr is None or network_cidr == "":
        return
    try:
        ipaddress.ip_network(network_cidr, strict=False)
    except (ValueError, TypeError) as exc:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Invalid network_cidr {network_cidr!r}: {exc}",
            status_code=400,
        )


async def create_network_scope(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    scope_name: str,
    scope_type: str,
    network_cidr: str | None = None,
    agent_ids: list[uuid.UUID] | None = None,
    zone_ids: list[uuid.UUID] | None = None,
) -> NetworkScope:
    """Create a new network scope.

    Args:
        session: Database session
        user_id: Owner user ID
        scope_name: Human-readable scope name
        scope_type: Type of scope (personal, enterprise)
        network_cidr: Optional network CIDR (e.g., "10.0.0.0/8")
        agent_ids: Optional list of agent IDs in this scope
        zone_ids: Optional list of zone IDs in this scope

    Returns:
        Created NetworkScope

    Raises:
        DomainException: If user not found or validation fails
    """
    # Verify user exists
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            f"User {user_id} not found",
            status_code=404,
        )

    # Validate scope_type
    valid_scope_types = ["personal", "enterprise"]
    if scope_type not in valid_scope_types:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Invalid scope_type '{scope_type}'. Must be one of: {valid_scope_types}",
        )

    # The egress policy decision point filters target IPs against this
    # CIDR; reject unparseable values at registration time.
    validate_network_cidr(network_cidr)

    scope = NetworkScope(
        id=uuid.uuid4(),
        user_id=user_id,
        scope_name=scope_name,
        scope_type=scope_type,
        network_cidr=network_cidr,
        agent_ids=agent_ids or [],
        zone_ids=zone_ids or [],
    )

    session.add(scope)
    await session.flush()
    await session.refresh(scope)

    logger.info(
        "Created network scope: id=%s user_id=%s scope_name=%s scope_type=%s",
        scope.id,
        user_id,
        scope_name,
        scope_type,
    )

    return scope


async def get_network_scope(
    session: AsyncSession,
    *,
    scope_id: uuid.UUID,
) -> NetworkScope:
    """Get a network scope by ID.

    Args:
        session: Database session
        scope_id: Scope ID

    Returns:
        NetworkScope

    Raises:
        DomainException: If scope not found
    """
    result = await session.execute(select(NetworkScope).where(NetworkScope.id == scope_id))
    scope = result.scalar_one_or_none()

    if not scope:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            f"Network scope {scope_id} not found",
            status_code=404,
        )

    return scope


async def list_network_scopes(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    scope_type: str | None = None,
) -> list[NetworkScope]:
    """List network scopes for a user.

    Args:
        session: Database session
        user_id: Owner user ID
        scope_type: Optional filter by scope type

    Returns:
        List of NetworkScope objects
    """
    query = select(NetworkScope).where(NetworkScope.user_id == user_id)

    if scope_type:
        query = query.where(NetworkScope.scope_type == scope_type)

    result = await session.execute(query)
    scopes = result.scalars().all()

    return list(scopes)


async def create_network_zone(
    session: AsyncSession,
    *,
    scope_id: uuid.UUID,
    zone_name: str,
    zone_type: str,
    parent_zone_id: uuid.UUID | None = None,
    relay_node_ids: list[uuid.UUID] | None = None,
    zone_metadata: dict[str, Any] | None = None,
) -> NetworkZone:
    """Create a new network zone.

    Args:
        session: Database session
        scope_id: Parent scope ID
        zone_name: Human-readable zone name
        zone_type: Type of zone (local, regional, global, local_edge, central, cloud, egress)
        parent_zone_id: Optional parent zone ID for hierarchical zones
        relay_node_ids: Optional list of relay node IDs in this zone
        zone_metadata: Optional zone metadata

    Returns:
        Created NetworkZone

    Raises:
        DomainException: If scope not found, parent zone not found, or validation fails
    """
    # Verify scope exists
    scope_result = await session.execute(select(NetworkScope).where(NetworkScope.id == scope_id))
    scope = scope_result.scalar_one_or_none()
    if not scope:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            f"Network scope {scope_id} not found",
            status_code=404,
        )

    # Validate zone_type
    valid_zone_types = ["local", "regional", "global", "local_edge", "central", "cloud", "egress"]
    if zone_type not in valid_zone_types:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Invalid zone_type '{zone_type}'. Must be one of: {valid_zone_types}",
        )

    # Verify parent zone exists if specified
    if parent_zone_id:
        parent_result = await session.execute(
            select(NetworkZone).where(NetworkZone.id == parent_zone_id)
        )
        parent_zone = parent_result.scalar_one_or_none()
        if not parent_zone:
            raise DomainException(
                ErrorCode.RESOURCE_NOT_FOUND,
                f"Parent zone {parent_zone_id} not found",
                status_code=404,
            )

        # Verify parent zone belongs to same scope
        if parent_zone.scope_id != scope_id:
            raise DomainException(
                ErrorCode.INVALID_REQUEST,
                f"Parent zone {parent_zone_id} does not belong to scope {scope_id}",
            )

    zone = NetworkZone(
        id=uuid.uuid4(),
        scope_id=scope_id,
        zone_name=zone_name,
        zone_type=zone_type,
        parent_zone_id=parent_zone_id,
        relay_node_ids=relay_node_ids or [],
        zone_metadata=zone_metadata or {},
    )

    session.add(zone)
    await session.flush()
    await session.refresh(zone)

    logger.info(
        "Created network zone: id=%s scope_id=%s zone_name=%s zone_type=%s parent_zone_id=%s",
        zone.id,
        scope_id,
        zone_name,
        zone_type,
        parent_zone_id,
    )

    return zone


async def get_network_zone(
    session: AsyncSession,
    *,
    zone_id: uuid.UUID,
) -> NetworkZone:
    """Get a network zone by ID.

    Args:
        session: Database session
        zone_id: Zone ID

    Returns:
        NetworkZone

    Raises:
        DomainException: If zone not found
    """
    result = await session.execute(select(NetworkZone).where(NetworkZone.id == zone_id))
    zone = result.scalar_one_or_none()

    if not zone:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            f"Network zone {zone_id} not found",
            status_code=404,
        )

    return zone


async def get_zones_in_scope(
    session: AsyncSession,
    *,
    scope_id: uuid.UUID,
    zone_type: str | None = None,
) -> list[NetworkZone]:
    """Get all zones in a scope.

    Args:
        session: Database session
        scope_id: Scope ID
        zone_type: Optional filter by zone type

    Returns:
        List of NetworkZone objects

    Raises:
        DomainException: If scope not found
    """
    # Verify scope exists
    scope_result = await session.execute(select(NetworkScope).where(NetworkScope.id == scope_id))
    scope = scope_result.scalar_one_or_none()
    if not scope:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            f"Network scope {scope_id} not found",
            status_code=404,
        )

    query = select(NetworkZone).where(NetworkZone.scope_id == scope_id)

    if zone_type:
        query = query.where(NetworkZone.zone_type == zone_type)

    result = await session.execute(query)
    zones = result.scalars().all()

    return list(zones)


async def update_network_scope(
    session: AsyncSession,
    *,
    scope_id: uuid.UUID,
    scope_name: str | None = None,
    network_cidr: str | None = None,
    agent_ids: list[uuid.UUID] | None = None,
    zone_ids: list[uuid.UUID] | None = None,
) -> NetworkScope:
    """Update a network scope.

    Args:
        session: Database session
        scope_id: Scope ID
        scope_name: Optional new scope name
        network_cidr: Optional new network CIDR
        agent_ids: Optional new agent IDs list
        zone_ids: Optional new zone IDs list

    Returns:
        Updated NetworkScope

    Raises:
        DomainException: If scope not found
    """
    scope = await get_network_scope(session, scope_id=scope_id)

    if scope_name is not None:
        scope.scope_name = scope_name
    if network_cidr is not None:
        # Re-run the registration-time CIDR validation on update too:
        # a scope-level CIDR change reaches the egress policy point.
        validate_network_cidr(network_cidr)
        scope.network_cidr = network_cidr
    if agent_ids is not None:
        scope.agent_ids = agent_ids
    if zone_ids is not None:
        scope.zone_ids = zone_ids

    await session.flush()
    await session.refresh(scope)

    logger.info("Updated network scope: id=%s", scope_id)

    return scope


async def delete_network_scope(
    session: AsyncSession,
    *,
    scope_id: uuid.UUID,
) -> None:
    """Delete a network scope.

    Args:
        session: Database session
        scope_id: Scope ID

    Raises:
        DomainException: If scope not found
    """
    scope = await get_network_scope(session, scope_id=scope_id)

    await session.delete(scope)
    await session.flush()

    logger.info("Deleted network scope: id=%s", scope_id)


async def delete_network_zone(
    session: AsyncSession,
    *,
    zone_id: uuid.UUID,
) -> None:
    """Delete a network zone.

    Args:
        session: Database session
        zone_id: Zone ID

    Raises:
        DomainException: If zone not found
    """
    zone = await get_network_zone(session, zone_id=zone_id)

    await session.delete(zone)
    await session.flush()

    logger.info("Deleted network zone: id=%s", zone_id)
