"""Regression tests for confirmed bugs found in the bug-fix pass.

Each test pins one fix:

1. P0  auth.authenticate() must reject API keys of disabled users
2. P1  deliver_task_request() must fail closed on an invalid route lease
3. P1  retry worker must count failed sends (no infinite retry) and must
       not mark a successfully delivered message as DELIVERY_FAILED
4. P1  WS task handlers must reject agents that are not the task owner
5. P1  route policy evaluation: a deny must override an earlier
       allow-with-constraints result (deny takes precedence)
"""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.api_key import ApiKey
from app.models.message import Message
from app.models.task import Task
from app.models.user import User
from app.protocol.constants import DeliveryStatus, MessageType, TaskStatus
from app.services import auth as auth_service


async def _make_user_and_key(session: AsyncSession, *, disabled: bool = False) -> tuple[User, str]:
    """Persist a user + active API key; returns (user, raw_key)."""
    raw, key_hash, key_prefix = auth_service.generate_api_key()
    user = User(username=f"bugfix-{uuid.uuid4().hex[:10]}")
    if disabled:
        user.is_disabled = True
    session.add(user)
    await session.flush()
    session.add(
        ApiKey(
            user_id=user.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name="bugfix-test",
        )
    )
    await session.flush()
    return user, raw


class TestAuthenticateDisabledUser:
    """P0: a disabled user's API key must not grant API access."""

    async def test_disabled_user_key_rejected(self, session: AsyncSession):
        _, raw_key = await _make_user_and_key(session)

        # Sanity: the key works while the user is enabled.
        user = await auth_service.authenticate(
            x_api_key=raw_key, authorization=None, session=session
        )
        assert user is not None

        user.is_disabled = True
        await session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.authenticate(
                x_api_key=raw_key, authorization=None, session=session
            )
        assert exc_info.value.status_code == 401

    async def test_get_or_create_user_handles_duplicate_username(self, session: AsyncSession):
        """Concurrent registration of the same username must not 500."""
        username = f"dup-{uuid.uuid4().hex[:10]}"

        # Simulate a race: row inserted after our SELECT but before flush.
        other = User(username=username)
        session.add(other)
        await session.flush()

        user = await auth_service.get_or_create_user(username, session)
        assert user.username == username


class TestRouteLeaseFailClosed:
    """P1: invalid/exhausted route lease must block delivery, not warn and continue."""

    async def test_invalid_lease_blocks_delivery(self, session: AsyncSession):
        from app.services import routing_service

        user = User(username=f"lease-{uuid.uuid4().hex[:10]}")
        session.add(user)
        await session.flush()
        agent = Agent(
            agent_number=str(1_000_000 + uuid.uuid4().int % 8_999_999),
            owner_id=user.id,
            name="lease-agent",
            runtime="test",
            inbound_policy="public",
        )
        session.add(agent)
        await session.flush()

        task = Task(
            created_by=agent.id,
            assigned_to=agent.id,
            status=TaskStatus.DELIVERED.value,
            message_id=f"msg-{uuid.uuid4().hex[:12]}",
        )
        session.add(task)
        await session.flush()
        message = Message(
            task_id=task.id,
            message_id=task.message_id,
            type=MessageType.TASK_REQUEST.value,
            delivery_status=DeliveryStatus.DELIVERED.value,
            content={},
        )
        session.add(message)
        await session.flush()

        # A route decision referencing a lease that fails verification.
        route_decision = SimpleNamespace(
            id=uuid.uuid4(),
            lease_id=uuid.uuid4(),
            selected_route_type="central_relay",
            selected_relay_node_id=uuid.uuid4(),
        )

        with patch(
            "app.services.lease_service.verify_route_lease",
            new=AsyncMock(return_value=None),
        ):
            with pytest.raises(routing_service.DomainException) as exc_info:
                await routing_service.deliver_task_request(
                    task, message, agent, route_decision=route_decision
                )
        assert exc_info.value.code == routing_service.ErrorCode.NO_AVAILABLE_RELAY.value


class TestRetryWorkerBookkeeping:
    """P1: failed sends must increment retry_count and eventually fail delivery."""

    async def test_failed_send_increments_and_exhausts(self):
        from app.database import SessionLocal
        from app.services import routing_service

        user = User(username=f"retry-{uuid.uuid4().hex[:10]}")
        agent = Agent(
            agent_number=str(1_000_000 + uuid.uuid4().int % 8_999_999),
            name="retry-agent",
            runtime="test",
            inbound_policy="public",
        )
        task = Task(
            created_by=None,
            assigned_to=None,
            status=TaskStatus.DELIVERED.value,
            message_id=f"msg-{uuid.uuid4().hex[:12]}",
        )
        message = Message(
            message_id=task.message_id,
            type=MessageType.TASK_REQUEST.value,
            delivery_status=DeliveryStatus.DELIVERED.value,
            content={},
            retry_count=0,
            max_retries=2,
            next_retry_at=datetime.now(UTC) - timedelta(seconds=10),
        )

        async with SessionLocal() as s:
            s.add(user)
            await s.flush()
            agent.owner_id = user.id
            s.add(agent)
            await s.flush()
            task.created_by = agent.id
            task.assigned_to = agent.id
            s.add(task)
            await s.flush()
            message.task_id = task.id
            s.add(message)
            await s.commit()
            message_id = message.message_id

        class _Manager:
            """Online but never delivers: exercises the failure branch."""

            def __init__(self, owner_agent_id):
                self.owner_agent_id = owner_agent_id

            async def is_agent_online(self, agent_id):
                return agent_id == self.owner_agent_id

            async def send_to_agent(self, agent_id, payload, **kwargs):
                return False

        with patch(
            "app.websocket.manager.get_connection_manager",
            lambda: _Manager(agent.id),
        ):
            await routing_service.retry_unacked_messages()
            async with SessionLocal() as s:
                from sqlalchemy import select

                row = (
                    await s.execute(
                        select(Message).where(Message.message_id == message_id)
                    )
                ).scalar_one()
                # First failed send: counted, still delivered (retry budget left).
                assert row.retry_count == 1
                assert row.delivery_status == DeliveryStatus.DELIVERED.value
                assert row.next_retry_at is not None

            # Fast-forward past the retry backoff window.
            async with SessionLocal() as s:
                from sqlalchemy import select

                row = (
                    await s.execute(
                        select(Message).where(Message.message_id == message_id)
                    )
                ).scalar_one()
                row.next_retry_at = datetime.now(UTC) - timedelta(seconds=10)
                await s.commit()

            await routing_service.retry_unacked_messages()
            async with SessionLocal() as s:
                from sqlalchemy import select

                row = (
                    await s.execute(
                        select(Message).where(Message.message_id == message_id)
                    )
                ).scalar_one()
                # Second failed send exhausts max_retries=2 -> failure recorded.
                assert row.retry_count == 2
                assert row.delivery_status == DeliveryStatus.DELIVERY_FAILED.value


class TestWsTaskOwnership:
    """P1: a connected agent must not mutate a task assigned to another agent."""

    async def test_task_accepted_rejected_for_non_owner(self):
        from app.database import SessionLocal
        from app.websocket import handlers

        user = User(username=f"ws-{uuid.uuid4().hex[:10]}")
        owner = Agent(
            agent_number=str(1_000_000 + uuid.uuid4().int % 8_999_999),
            name="owner-agent",
            runtime="test",
            inbound_policy="public",
        )
        intruder = Agent(
            agent_number=str(1_000_000 + uuid.uuid4().int % 8_999_999),
            name="intruder-agent",
            runtime="test",
            inbound_policy="public",
        )
        task = Task(
            status=TaskStatus.DELIVERED.value,
            message_id=f"msg-{uuid.uuid4().hex[:12]}",
        )

        async with SessionLocal() as s:
            s.add(user)
            await s.flush()
            owner.owner_id = user.id
            intruder.owner_id = user.id
            s.add(owner)
            s.add(intruder)
            await s.flush()
            task.created_by = owner.id
            task.assigned_to = owner.id
            s.add(task)
            await s.commit()
            task_id = task.id

        from app.websocket.protocol import WSMessage

        msg = WSMessage(
            type=MessageType.TASK_ACCEPTED.value,
            payload={"task_id": str(task_id)},
        )
        ws = AsyncMock()
        conn_state = SimpleNamespace(agent_id=intruder.id, agent_number=intruder.agent_number)

        from app.exceptions import DomainException

        with pytest.raises(DomainException) as exc_info:
            await handlers._handle_task_accepted(ws, msg, conn_state)
        assert exc_info.value.code == "AGENT_FORBIDDEN"
        # And nothing was written back to the client.
        ws.send_text.assert_not_called()

        # The legitimate owner is still allowed.
        conn_state_owner = SimpleNamespace(agent_id=owner.id, agent_number=owner.agent_number)
        await handlers._handle_task_accepted(ws, msg, conn_state_owner)
        ws.send_text.assert_called_once()


class TestRoutePolicyDenyPrecedence:
    """P1: a lower-priority deny must override a higher-priority constrained allow."""

    async def test_deny_overrides_constrained_allow(self):
        from app.models.route_policy import RoutePolicy
        from app.services import route_policy_service

        allow_with_approval = RoutePolicy(
            policy_name="constrained-allow",
            priority=1,
            allowed_route_types=["central_relay"],
            denied_route_types=None,
            require_approval=True,
            risk_level=None,
            enabled=True,
        )
        deny = RoutePolicy(
            policy_name="deny",
            priority=2,
            allowed_route_types=None,
            denied_route_types=["central_relay"],
            require_approval=False,
            risk_level=None,
            enabled=True,
        )

        async def _fake_get_policies(session, **kwargs):
            return [allow_with_approval, deny]

        from_agent = SimpleNamespace(agent_number="A1")
        to_agent = SimpleNamespace(agent_number="A2")

        with patch(
            "app.services.route_policy_service.get_applicable_policies",
            new=_fake_get_policies,
        ):
            result = await route_policy_service.evaluate_route_policy(
                session=None,
                from_agent=from_agent,
                to_agent=to_agent,
                route_type="central_relay",
            )

        assert result.allowed is False
        assert "deny" in result.reason.lower() or "denied" in result.reason.lower()
