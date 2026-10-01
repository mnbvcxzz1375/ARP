"""WebSocket endpoint for agent connections, heartbeat, and session resume."""

import asyncio
import hashlib
import logging
import uuid as uuid_mod
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, or_

from app.database import SessionLocal
from app.exceptions import DomainException
from app import metrics
from app.models.agent import Agent
from app.models.agent_token import AgentToken
from app.protocol.constants import ErrorCode, MessageType
from app.websocket.handlers import handle_ws_message
from app.websocket.manager import get_connection_manager
from app.websocket.protocol import (
    build_ack,
    build_error,
    build_ws_message,
    check_payload_size,
    parse_ws_message,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _authenticate_agent(token_raw: str) -> Agent:
    if not token_raw or not token_raw.startswith("agt_sk_"):
        raise DomainException(
            ErrorCode.INVALID_TOKEN,
            "Invalid agent token format",
            status_code=401,
        )

    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        stmt = (
            select(Agent, AgentToken)
            .join(AgentToken, AgentToken.agent_id == Agent.id)
            .where(
                AgentToken.token_hash == token_hash,
                AgentToken.is_revoked == False,
                or_(
                    AgentToken.expires_at == None,
                    AgentToken.expires_at > now,
                ),
            )
        )
        result = await session.execute(stmt)
        row = result.one_or_none()

        if row is None:
            raise DomainException(
                ErrorCode.INVALID_TOKEN,
                "Invalid or revoked agent token",
                status_code=401,
            )

        return row[0]


async def _update_agent_status(agent_id: str, status: str) -> None:
    """Update agent status in the database."""
    from sqlalchemy import update
    agent_uuid = uuid_mod.UUID(agent_id)
    async with SessionLocal() as session:
        await session.execute(
            update(Agent)
            .where(Agent.id == agent_uuid)
            .values(status=status)
        )
        await session.commit()


@router.websocket("/v1/ws")
async def agent_websocket(ws: WebSocket):
    # Prefer Authorization header (SDK default); fall back to query param
    auth_header = ws.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token_raw = auth_header[7:]
    else:
        token_raw = ws.query_params.get("token", "")
    session_id = ws.query_params.get("session_id", "")

    try:
        agent = await _authenticate_agent(token_raw)
    except DomainException as exc:
        metrics.ws_auth_failed()
        await ws.accept()
        await ws.send_text(build_error(exc.code, exc.message))
        await ws.close(code=4001)
        return

    # Phase 10: Rate limit check for WebSocket connections
    try:
        from app.services.rate_limit_service import check_rate_limit
        client_ip = ws.client.host if ws.client else None
        await check_rate_limit(
            user_id=str(agent.owner_id) if agent.owner_id else None,
            agent_id=str(agent.id),
            request_ip=client_ip,
        )
    except DomainException as exc:
        metrics.ws_auth_failed()
        await ws.accept()
        await ws.send_text(build_error(exc.code, exc.message))
        await ws.close(code=4429)
        return

    mgr = get_connection_manager()

    # Accept the socket BEFORE registering it with the connection manager.
    # Previously register() ran first: if ws.accept() then failed (client
    # dropped during the handshake), the in-memory ConnectionState and the
    # Redis presence entry would leak until the heartbeat cleaner timed
    # them out, and during that window send_to_agent would keep trying to
    # deliver to a dead socket.
    try:
        await ws.accept()
    except RuntimeError:
        logger.info(
            "WebSocket accept failed for agent=%s (client disconnected during handshake)",
            agent.agent_number,
        )
        return

    try:
        conn_state = await mgr.register(
            ws, agent.id, agent.agent_number, session_id or str(agent.id)
        )
    except DomainException as exc:
        await ws.send_text(build_error(exc.code, exc.message))
        await ws.close(code=4002)
        return

    metrics.ws_connected()
    await _update_agent_status(str(agent.id), "online")

    # Deliver any pending offline messages
    from app.services.routing_service import deliver_pending_on_connect
    delivered_ids = await deliver_pending_on_connect(agent, session_id=conn_state.session_id)

    await ws.send_text(
        build_ws_message(
            MessageType.SESSION_RESUME_RESULT.value,
            {
                "connection_id": conn_state.connection_id,
                "pending_delivered": len(delivered_ids),
            },
        )
    )

    # Audit: websocket connected
    from app.services.audit_service import write_audit
    async with SessionLocal() as audit_session:
        await write_audit(
            audit_session,
            actor_type="agent",
            actor_id=str(agent.id),
            action="ws.connected",
            resource_type="agent",
            resource_id=str(agent.id),
            details={"connection_id": conn_state.connection_id, "session_id": session_id},
        )

    logger.info(
        "WS connection established: agent=%s conn_id=%s",
        agent.agent_number,
        conn_state.connection_id,
    )

    try:
        while True:
            data = await ws.receive_text()
            try:
                await _process_receive(ws, data, conn_state)
            except DomainException as exc:
                await ws.send_text(
                    build_error(
                        exc.code, exc.message,
                        getattr(conn_state, "last_message_id", None)
                    )
                )
    except WebSocketDisconnect:
        logger.info(
            "WS disconnected: agent=%s conn_id=%s",
            agent.agent_number,
            conn_state.connection_id,
        )
    except Exception:
        logger.exception(
            "Unexpected WS error for agent=%s", agent.agent_number
        )
    finally:
        metrics.ws_disconnected()
        agent_id, agent_number = await mgr.unregister(conn_state.connection_id)
        if agent_id is not None:
            await _update_agent_status(str(agent_id), "offline")

        # Audit: websocket disconnected
        async with SessionLocal() as audit_session:
            await write_audit(
                audit_session,
                actor_type="agent",
                actor_id=str(agent.id),
                action="ws.disconnected",
                resource_type="agent",
                resource_id=str(agent.id),
                details={"connection_id": conn_state.connection_id},
            )


async def _process_receive(
    ws: WebSocket, raw_data: str, conn_state
) -> None:
    check_payload_size(raw_data)
    msg = parse_ws_message(raw_data)

    if msg.type == MessageType.PRESENCE_HEARTBEAT.value:
        mgr = get_connection_manager()
        await mgr.record_heartbeat(conn_state.connection_id)
        await ws.send_text(build_ack(msg.message_id))
        return

    if msg.type == MessageType.ACK.value:
        message_id = msg.payload.get("message_id", "")
        if message_id:
            from app.services.routing_service import ack_message as ack_routing
            await ack_routing(message_id)
        logger.debug("Processed ack for message_id=%s", message_id)
        return

    if msg.type == MessageType.SESSION_RESUME.value:
        from app.websocket.handlers import handle_session_resume
        await handle_session_resume(ws, msg, conn_state)
        return

    await handle_ws_message(ws, msg, conn_state)
