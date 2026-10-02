"""PersonalScope read service (hot path).

0033: personal routing strategy. The task creation hot path must perform
EXACTLY ONE PersonalScope point query per task (personal_scopes.user_id
is unique-indexed, so this is a cheap indexed point lookup). Both
routing_strategy and enable_edge_relay are derived from that single row
and passed explicitly to path_optimizer.select_route as arguments —
path_optimizer must NOT re-query PersonalScope.

Callers elsewhere (routers/personal.py) keep their own auto-create
logic; this service is read-only by design.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.personal_scope import PersonalScope

#: Values allowed for personal_scopes.routing_strategy.
ROUTING_STRATEGIES: tuple[str, ...] = ("fast", "normal", "reliable")

#: Server/column default, also the fallback for missing scopes.
DEFAULT_ROUTING_STRATEGY = "normal"


async def get_personal_scope(
    session: AsyncSession, user_id: uuid.UUID | None
) -> PersonalScope | None:
    """Return the caller's PersonalScope row, or None if absent.

    Hot-path point query on personal_scopes.user_id (unique index).
    Returns None (no auto-create) so callers can treat "no preference"
    as the default without a write.
    """
    if user_id is None:
        return None
    result = await session.execute(
        select(PersonalScope).where(PersonalScope.user_id == user_id)
    )
    return result.scalar_one_or_none()


def get_routing_strategy(scope: PersonalScope | None) -> str:
    """Return the effective routing strategy for a personal scope.

    Falls back to 'normal' when the scope is missing or holds a value
    outside the allowed set (defensive; the column is validated at the
    API layer by PersonalScopeUpdate's Literal).
    """
    if scope is None:
        return DEFAULT_ROUTING_STRATEGY
    strategy = scope.routing_strategy
    if strategy not in ROUTING_STRATEGIES:
        return DEFAULT_ROUTING_STRATEGY
    return strategy
