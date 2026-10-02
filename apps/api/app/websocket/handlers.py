from app.protocol.constants import ErrorCode, MessageType

"""WebSocket message handlers. Dispatches messages by type."""

import logging

from fastapi import WebSocket


from app.websocket.protocol import (
    WSMessage,
    build_ack,
    build_error,
    build_ws_message,
)

logger = logging.getLogger(__name__)


async def handle_ws_message(
    ws: WebSocket, msg: WSMessage, conn_state
) -> None:
    logger.debug(
        "WS message: type=%s message_id=%s agent=%s",
        msg.type,
        msg.message_id,
        conn_state.agent_number,
    )

    if msg.type == MessageType.SESSION_RESUME.value:
        await handle_session_resume(ws, msg, conn_state)
    elif msg.type == MessageType.ACK.value:
        await _handle_ack(ws, msg, conn_state)
    elif msg.type == MessageType.TASK_ACCEPTED.value:
        await _handle_task_accepted(ws, msg, conn_state)
    elif msg.type == MessageType.TASK_PROGRESS.value:
        await _handle_task_progress(ws, msg, conn_state)
    elif msg.type == MessageType.TASK_HEARTBEAT.value:
        await _handle_task_heartbeat(ws, msg, conn_state)
    elif msg.type == MessageType.TASK_RESULT.value:
        await _handle_task_result(ws, msg, conn_state)
    elif msg.type == MessageType.TASK_FAILED.value:
        await _handle_task_failed(ws, msg, conn_state)
    elif msg.type == MessageType.APPROVAL_REQUEST.value:
        await _handle_approval_request(ws, msg, conn_state)
    elif msg.type == MessageType.APPROVAL_ACCEPTED.value:
        await _handle_approval_accepted(ws, msg, conn_state)
    elif msg.type == MessageType.APPROVAL_REJECTED.value:
        await _handle_approval_rejected(ws, msg, conn_state)
    else:
        await ws.send_text(
            build_error(
                ErrorCode.UNSUPPORTED_MESSAGE_TYPE.value,
                f"Message type {msg.type} not supported",
                msg.message_id,
            )
        )





async def _handle_ack(ws, msg, conn_state):
    """Handle ack message."""
    message_id = msg.payload.get("message_id", msg.message_id)
    from app.services.routing_service import ack_message
    await ack_message(message_id)
    # No response needed for ack


def _ensure_task_owner(task, conn_state) -> None:
    """Verify the connected agent is the one this task was assigned to.

    Without this check any authenticated agent could mutate another
    agent's task (accept/progress/result/fail) by guessing task_id.
    Raises DomainException(AGENT_FORBIDDEN) when the task belongs to
    another agent.
    """
    from app.exceptions import DomainException
    from app.protocol.constants import ErrorCode

    if task.assigned_to is None or task.assigned_to != conn_state.agent_id:
        raise DomainException(
            ErrorCode.AGENT_FORBIDDEN,
            f"Task {task.id} is not assigned to agent {conn_state.agent_id}",
            status_code=403,
        )


async def _handle_task_accepted(ws, msg, conn_state):
    task_id = msg.payload.get("task_id")
    if not task_id:
        await ws.send_text(build_error("MISSING_TASK_ID", "task_id required", msg.message_id))
        return
    from uuid import UUID
    from app.database import SessionLocal
    from app.services.task_service import get_task, accept_task
    async with SessionLocal() as session:
        task = await get_task(session, UUID(task_id))
        _ensure_task_owner(task, conn_state)
        task = await accept_task(session, task, agent_id=conn_state.agent_id)
    await ws.send_text(build_ack(msg.message_id))


async def _handle_task_progress(ws, msg, conn_state):
    task_id = msg.payload.get("task_id")
    if not task_id:
        await ws.send_text(build_error("MISSING_TASK_ID", "task_id required", msg.message_id))
        return
    from uuid import UUID
    from app.database import SessionLocal
    from app.services.task_service import get_task, record_progress
    async with SessionLocal() as session:
        task = await get_task(session, UUID(task_id))
        _ensure_task_owner(task, conn_state)
        task = await record_progress(
            session, task,
            progress_pct=msg.payload.get("progress_pct"),
            message=msg.payload.get("message"),
            data=msg.payload.get("data"),
        )
    await ws.send_text(build_ack(msg.message_id))


async def _handle_task_heartbeat(ws, msg, conn_state):
    task_id = msg.payload.get("task_id")
    if not task_id:
        await ws.send_text(build_error("MISSING_TASK_ID", "task_id required", msg.message_id))
        return
    from uuid import UUID
    from app.database import SessionLocal
    from app.services.task_service import get_task, heartbeat_task
    async with SessionLocal() as session:
        task = await get_task(session, UUID(task_id))
        _ensure_task_owner(task, conn_state)
        task = await heartbeat_task(session, task, conn_state.agent_id)
    await ws.send_text(build_ack(msg.message_id))


async def _handle_task_result(ws, msg, conn_state):
    task_id = msg.payload.get("task_id")
    if not task_id:
        await ws.send_text(build_error("MISSING_TASK_ID", "task_id required", msg.message_id))
        return
    from uuid import UUID
    from app.database import SessionLocal
    from app.services.task_service import get_task, complete_task
    # M2: when the agent writes back a sealed result, the whole ciphertext
    # envelope is stored verbatim in task.result — no content-level
    # parsing, no keying material handling, no plaintext extraction.
    if msg.is_e2ee_sealed():
        result = msg.sealed_envelope()
    else:
        result = msg.payload.get("result")
    async with SessionLocal() as session:
        task = await get_task(session, UUID(task_id))
        _ensure_task_owner(task, conn_state)
        task = await complete_task(session, task, result=result)
    await ws.send_text(build_ack(msg.message_id))


async def _handle_task_failed(ws, msg, conn_state):
    task_id = msg.payload.get("task_id")
    if not task_id:
        await ws.send_text(build_error("MISSING_TASK_ID", "task_id required", msg.message_id))
        return
    from uuid import UUID
    from app.database import SessionLocal
    from app.services.task_service import get_task, fail_task
    async with SessionLocal() as session:
        task = await get_task(session, UUID(task_id))
        _ensure_task_owner(task, conn_state)
        task = await fail_task(
            session, task,
            error_message=msg.payload.get("error_message"),
        )
    await ws.send_text(build_ack(msg.message_id))


async def _handle_approval_request(ws, msg, conn_state):
    task_id = msg.payload.get("task_id")
    if not task_id:
        await ws.send_text(build_error("MISSING_TASK_ID", "task_id required", msg.message_id))
        return
    from uuid import UUID
    from app.database import SessionLocal
    from app.services.task_service import get_task, request_approval
    async with SessionLocal() as session:
        task = await get_task(session, UUID(task_id))
        _ensure_task_owner(task, conn_state)
        task = await request_approval(
            session, task,
            risk_level=msg.payload.get("risk_level", "medium"),
            action_kind=msg.payload.get("action", {}).get("kind", "unknown"),
            action_preview=msg.payload.get("action", {}).get("preview"),
            reason=msg.payload.get("reason"),
        )
    await ws.send_text(build_ack(msg.message_id))


async def _handle_approval_accepted(ws, msg, conn_state):
    approval_id = msg.payload.get("approval_id")
    if not approval_id:
        await ws.send_text(build_error("MISSING_APPROVAL_ID", "approval_id required", msg.message_id))
        return
    from uuid import UUID
    from app.database import SessionLocal
    from app.services.approval_service import accept_approval
    async with SessionLocal() as session:
        await accept_approval(session, UUID(approval_id))
    await ws.send_text(build_ack(msg.message_id))


async def _handle_approval_rejected(ws, msg, conn_state):
    approval_id = msg.payload.get("approval_id")
    if not approval_id:
        await ws.send_text(build_error("MISSING_APPROVAL_ID", "approval_id required", msg.message_id))
        return
    from uuid import UUID
    from app.database import SessionLocal
    from app.services.approval_service import reject_approval
    async with SessionLocal() as session:
        await reject_approval(session, UUID(approval_id))
    await ws.send_text(build_ack(msg.message_id))

async def handle_session_resume(
    ws: WebSocket, msg: WSMessage, conn_state
) -> None:
    from app.services.session_service import get_pending_messages

    session_id = msg.payload.get("session_id")
    last_message_id = msg.payload.get("last_message_id")

    if not session_id:
        await ws.send_text(
            build_error(
                ErrorCode.INVALID_SESSION.value,
                "session_id is required for session.resume",
                msg.message_id,
            )
        )
        return

    pending = await get_pending_messages(
        conn_state.agent_id, session_id, last_message_id
    )

    await ws.send_text(
        build_ws_message(
            MessageType.SESSION_RESUME_RESULT.value,
            {
                "session_id": session_id,
                "pending_count": len(pending),
                "resumed": True,
            },
        )
    )

    for pending_msg in pending:
        await ws.send_text(pending_msg)

    logger.info(
        "Session resume: agent=%s session=%s pending=%d",
        conn_state.agent_number,
        session_id,
        len(pending),
    )
