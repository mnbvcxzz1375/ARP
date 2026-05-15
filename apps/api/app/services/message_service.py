"""Message service for task-related messages."""

import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.protocol.constants import DeliveryStatus


async def list_task_messages(
    session: AsyncSession,
    task_id: uuid.UUID,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Message], int]:
    stmt = select(Message).where(Message.task_id == task_id)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Message.created_at.asc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def create_delivery_message(
    session: AsyncSession,
    task_id: uuid.UUID,
    msg_type: str,
    content: dict,
) -> Message:
    msg = Message(
        task_id=task_id,
        message_id=str(uuid.uuid4()),
        type=msg_type,
        delivery_status=DeliveryStatus.PENDING.value,
        content=content,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg
