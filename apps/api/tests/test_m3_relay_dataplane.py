"""M3: relay dataplane dispatch — transport layer, cross-node, locks.

Covers the acceptance criteria of the m3-relay-dataplane-dispatch module:

1) route_type=regional_relay delivery through RelayForwarder
   (receive -> heartbeat -> forward) with a full delivery event chain.
2) route_type=dedicated_channel delivery through ChannelTransport
   (consumes connection_config.endpoint/protocol).
3) Cross-node delivery with TWO ConnectionManager instances bound to one
   InMemoryRedis: a single instance talking to itself cannot demonstrate
   publish -> subscribe.
4) SKIP LOCKED claim semantics: two concurrent retry_unacked_messages
   instances on the same delivered-unacked batch — only one claims.
5) Redis pub/sub fault degradation, injected via InMemoryRedis
   (an AsyncMock's publish never raises).
6) session_service redis binding coverage: store_pending_message under a
   patched module-level binding never touches real Redis.
7) Offline delivery worker: queue-intact messages are left to the
   connect-time flow; queue-lost messages are delivered.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.models.agent import Agent
from app.models.channel_health_check import ChannelHealthCheck
from app.models.dedicated_channel import DedicatedChannel
from app.models.message import Message
from app.models.message_delivery_event import MessageDeliveryEvent
from app.models.relay_node import RelayNode
from app.models.route_decision import RouteDecision
from app.models.task import Task
from app.models.user import User
from app.protocol.constants import DeliveryStatus, MessageType
from app.services.routing_service import (
    deliver_task_request,
    retry_unacked_messages,
)
from app.transports.central import CentralTransport
from app.websocket.manager import ConnectionManager
from tests.helpers.ws_e2e import InMemoryRedis


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mem_redis(monkeypatch):
    """An InMemoryRedis wired into every module-level redis binding.

    The autouse conftest mock patches app.redis / rate_limit_service /
    session_service, but the default ConnectionManager resolves
    `from app.redis import redis_client` at construction time, so this
    fixture rebinds all three to the same InMemoryRedis instance and
    resets the manager singletons.
    """
    import app.redis as redis_module
    import app.services.rate_limit_service as rate_limit_service
    import app.services.session_service as session_service
    import app.websocket.manager as manager_module

    redis = InMemoryRedis()
    monkeypatch.setattr(redis_module, "redis_client", redis)
    monkeypatch.setattr(rate_limit_service, "redis_client", redis)
    monkeypatch.setattr(session_service, "redis_client", redis)
    manager_module._manager = None
    manager_module._managers_by_node.clear()
    yield redis
    manager_module._manager = None
    manager_module._managers_by_node.clear()


def _fake_ws():
    ws = AsyncMock()
    return ws


async def _commit(data_object):
    async with SessionLocal() as session:
        session.add(data_object)
        await session.commit()
        await session.refresh(data_object)
        return data_object


async def _make_task_and_message(
    *, source_agent: Agent, target_agent: Agent, content: dict | None = None
) -> tuple[Task, Message]:
    message_id = str(uuid.uuid4())
    task = Task(
        created_by=source_agent.id,
        assigned_to=target_agent.id,
        status="created",
        message_id=message_id,
    )
    msg = Message(
        task_id=None,  # set after flush
        message_id=message_id,
        type=MessageType.TASK_REQUEST.value,
        delivery_status=DeliveryStatus.QUEUED.value,
        content=content if content is not None else {"hello": "m3"},
        max_retries=3,
    )
    async with SessionLocal() as session:
        session.add(task)
        await session.flush()
        msg.task_id = task.id
        session.add(msg)
        await session.commit()
        await session.refresh(task)
        await session.refresh(msg)
    return task, msg


async def _make_agents() -> tuple[Agent, Agent]:
    async with SessionLocal() as session:
        user = User(username=f"m3user_{uuid.uuid4().hex[:8]}")
        session.add(user)
        await session.flush()
        src = Agent(
            owner_id=user.id,
            agent_number=f"AN-M3SRC-{uuid.uuid4().hex[:8].upper()}",
            name="M3 Source",
            runtime="python",
            inbound_policy="public",
        )
        dst = Agent(
            owner_id=user.id,
            agent_number=f"AN-M3DST-{uuid.uuid4().hex[:8].upper()}",
            name="M3 Target",
            runtime="python",
            inbound_policy="public",
        )
        session.add_all([src, dst])
        await session.flush()
        ids = (src.id, dst.id)
        src_number, dst_number = src.agent_number, dst.agent_number
        await session.commit()
    async with SessionLocal() as session:
        src = await session.get(Agent, ids[0])
        dst = await session.get(Agent, ids[1])
        return src, dst


async def _delivery_events(task_id) -> list[MessageDeliveryEvent]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(MessageDeliveryEvent)
            .where(MessageDeliveryEvent.task_id == task_id)
            .order_by(MessageDeliveryEvent.created_at)
        )
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# 1) regional_relay through RelayForwarder
# ---------------------------------------------------------------------------


class TestRelayForwarderDelivery:
    async def test_regional_relay_full_delivery_chain(self, mem_redis):
        from app.services.routing_service import RETRY_BACKOFF_BASE_S  # noqa: F401

        src, dst = await _make_agents()
        task, msg = await _make_task_and_message(
            source_agent=src, target_agent=dst
        )

        # A regional relay with a STALE heartbeat: the forwarder must
        # refresh it through the real heartbeat endpoint.
        relay = await _commit(
            RelayNode(
                node_name=f"m3-relay-{uuid.uuid4().hex[:8]}",
                node_type="regional",
                status="healthy",
                current_load=0.2,
                queue_depth=0,
                enabled=True,
                last_heartbeat_at=datetime.now(UTC) - timedelta(hours=2),
            )
        )
        stale_before = relay.last_heartbeat_at

        decision = await _commit(
            RouteDecision(
                task_id=task.id,
                message_id=msg.message_id,
                selected_route_type="regional_relay",
                selected_relay_node_id=relay.id,
                candidate_routes=[],
                rejection_reasons={},
                shadow_mode=False,
            )
        )

        # The target agent holds one live local connection.
        from app.websocket.manager import get_connection_manager

        ws = _fake_ws()
        mgr = get_connection_manager()
        await mgr.register(ws, dst.id, dst.agent_number, str(dst.id))

        status = await deliver_task_request(task, msg, dst, route_decision=decision)

        assert status == DeliveryStatus.DELIVERED.value

        events = await _delivery_events(task.id)
        event_types = [e.event_type for e in events]
        assert "route_selected" in event_types
        assert "relay_forwarded" in event_types
        assert "delivered" in event_types
        # Chain order: route_selected before relay_forwarded before delivered.
        assert (
            event_types.index("route_selected")
            < event_types.index("relay_forwarded")
            < event_types.index("delivered")
        )

        # The ws received exactly one task.request with the right message_id.
        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == MessageType.TASK_REQUEST.value
        assert sent["message_id"] == msg.message_id

        # The relay heartbeat was really refreshed (forwarder called the
        # routing heartbeat endpoint, not a hand-written UPDATE).
        async with SessionLocal() as session:
            refreshed = await session.get(RelayNode, relay.id)
        assert refreshed.last_heartbeat_at > stale_before
        assert (
            datetime.now(UTC) - refreshed.last_heartbeat_at
        ).total_seconds() < 30
        assert refreshed.status in ("healthy", "degraded")

        await mgr.shutdown()


# ---------------------------------------------------------------------------
# 2) dedicated_channel through ChannelTransport
# ---------------------------------------------------------------------------


class TestChannelTransportDelivery:
    async def test_dedicated_channel_delivers_and_records_endpoint(self, mem_redis):
        src, dst = await _make_agents()
        task, msg = await _make_task_and_message(
            source_agent=src, target_agent=dst
        )

        channel = await _commit(
            DedicatedChannel(
                scope_id=None,
                channel_name=f"m3-channel-{uuid.uuid4().hex[:8]}",
                channel_type="vpn",
                source_agent_id=src.id,
                target_agent_id=dst.id,
                connection_config={
                    "endpoint": "vpn.m3.example.com:443",
                    "protocol": "wireguard",
                },
                encryption_config={"algorithm": "AES-256-GCM"},
                enabled=True,
            )
        )
        # select_dedicated_channel requires a recent healthy check.
        await _commit(
            ChannelHealthCheck(
                channel_id=channel.id,
                check_time=datetime.now(UTC),
                latency_ms=5.0,
                packet_loss_percent=0.0,
                bandwidth_mbps=100.0,
                status="healthy",
            )
        )

        decision = await _commit(
            RouteDecision(
                task_id=task.id,
                message_id=msg.message_id,
                selected_route_type="dedicated_channel",
                selected_relay_node_id=None,
                candidate_routes=[],
                rejection_reasons={},
                shadow_mode=False,
            )
        )

        from app.websocket.manager import get_connection_manager

        ws = _fake_ws()
        mgr = get_connection_manager()
        await mgr.register(ws, dst.id, dst.agent_number, str(dst.id))

        status = await deliver_task_request(task, msg, dst, route_decision=decision)

        assert status == DeliveryStatus.DELIVERED.value

        events = await _delivery_events(task.id)
        forwarded = [e for e in events if e.event_type == "channel_forwarded"]
        assert len(forwarded) == 1
        assert forwarded[0].extra_metadata["endpoint"] == "vpn.m3.example.com:443"
        assert forwarded[0].extra_metadata["protocol"] == "wireguard"
        assert "delivered" in [e.event_type for e in events]

        ws.send_text.assert_awaited_once()
        await mgr.shutdown()


# ---------------------------------------------------------------------------
# 3) cross-node delivery (two instances, one InMemoryRedis)
# ---------------------------------------------------------------------------


class TestCrossNodeDelivery:
    async def test_two_instances_real_pubsub(self, mem_redis):
        src, dst = await _make_agents()
        task, msg = await _make_task_and_message(
            source_agent=src, target_agent=dst
        )

        mgr_a = ConnectionManager(mem_redis, node_id="node_a")
        mgr_b = ConnectionManager(mem_redis, node_id="node_b")
        await mgr_a.start_pubsub()
        await mgr_b.start_pubsub()
        # Let both subscription loops actually subscribe.
        await asyncio.sleep(0.2)

        ws_b = _fake_ws()
        # The agent is connected on node B only.
        await mgr_b.register(ws_b, dst.id, dst.agent_number, str(dst.id))
        await asyncio.sleep(0.1)

        # Node A has NO local connection for the agent.
        assert await mgr_a.get_connection_count(dst.id) == 0

        transport = CentralTransport(manager=mgr_a)
        result = await transport.deliver(
            agent_id=dst.id,
            message=json.dumps({"message_id": msg.message_id, "n": 1}),
            message_id=msg.message_id,
            task_id=task.id,
            source_agent_id=src.id,
            track_pending=True,
        )
        # Let node B's pubsub loop process the message.
        await asyncio.sleep(0.3)

        assert result.outcome == "sent_cross_node"
        assert result.node_id == "node_b"

        # The bytes really reached node B's local connection.
        ws_b.send_text.assert_awaited_once()
        received = json.loads(ws_b.send_text.call_args[0][0])
        assert received["message_id"] == msg.message_id

        # Presence on the shared Redis points at node B.
        assert await mgr_a.get_agent_node(dst.id) == "node_b"

        await mgr_a.shutdown()
        await mgr_b.shutdown()

    async def test_single_instance_self_send_is_not_cross_node(self, mem_redis):
        """A single instance must not be mistaken for cross-node delivery:
        the message lands on a local connection, outcome sent_locally."""
        src, dst = await _make_agents()

        mgr_a = ConnectionManager(mem_redis, node_id="node_a")
        ws_a = _fake_ws()
        await mgr_a.register(ws_a, dst.id, dst.agent_number, str(dst.id))

        transport = CentralTransport(manager=mgr_a)
        result = await transport.deliver(
            agent_id=dst.id,
            message=json.dumps({"message_id": "m-self"}),
            message_id="m-self",
            task_id=None,
            track_pending=False,
        )
        assert result.outcome == "sent_locally"
        assert result.node_id == "node_a"
        ws_a.send_text.assert_awaited_once()
        await mgr_a.shutdown()


# ---------------------------------------------------------------------------
# 4) SKIP LOCKED: concurrent retry instances claim disjoint rows
# ---------------------------------------------------------------------------


class TestSkipLockedClaims:
    async def test_two_concurrent_retry_instances_single_claim(self, mem_redis):
        src, dst = await _make_agents()
        task, msg = await _make_task_and_message(
            source_agent=src, target_agent=dst
        )

        # delivered-unacked, retry window due.
        async with SessionLocal() as session:
            row = await session.get(Message, msg.id)
            row.delivery_status = DeliveryStatus.DELIVERED.value
            row.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()

        from app.websocket.manager import get_connection_manager

        ws = _fake_ws()
        mgr = get_connection_manager()
        await mgr.register(ws, dst.id, dst.agent_number, str(dst.id))

        # Two concurrent instances of the SAME worker statement.
        results = await asyncio.gather(
            retry_unacked_messages(),
            retry_unacked_messages(),
        )

        # Exactly one instance claimed and re-sent the message.
        assert sorted(results) == [0, 1]
        ws.send_text.assert_awaited_once()

        # The message is back to delivered-unacked with an armed retry
        # window and a counted attempt.
        async with SessionLocal() as session:
            row = await session.get(Message, msg.id)
            assert row.delivery_status == DeliveryStatus.DELIVERED.value
            assert row.retry_count == 1
            assert row.next_retry_at is not None

        await mgr.shutdown()


# ---------------------------------------------------------------------------
# 5) Redis pub/sub fault degradation (InMemoryRedis fault injection)
# ---------------------------------------------------------------------------


class TestPubsubDegradation:
    async def test_pubsub_down_no_local_connection_degrades(self, mem_redis):
        src, dst = await _make_agents()

        mgr_a = ConnectionManager(mem_redis, node_id="node_a")
        # The agent lives on node_b (presence says so) but pub/sub is broken.
        await mem_redis.set(f"ws:presence:{dst.id}", "node_b")
        mem_redis.pubsub_failing = True

        transport = CentralTransport(manager=mgr_a)
        result = await transport.deliver(
            agent_id=dst.id,
            message=json.dumps({"message_id": "m-degraded"}),
            message_id="m-degraded",
            track_pending=True,
        )
        assert result.outcome == "sent_locally_queued_crossnode_down"
        assert result.error_code == "CROSSNODE_PUBSUB_FAILED"
        await mgr_a.shutdown()

    async def test_pubsub_down_local_connection_still_delivers(self, mem_redis):
        src, dst = await _make_agents()

        mgr_a = ConnectionManager(mem_redis, node_id="node_a")
        ws_a = _fake_ws()
        await mgr_a.register(ws_a, dst.id, dst.agent_number, str(dst.id))
        mem_redis.pubsub_failing = True

        transport = CentralTransport(manager=mgr_a)
        result = await transport.deliver(
            agent_id=dst.id,
            message=json.dumps({"message_id": "m-local-down"}),
            message_id="m-local-down",
            track_pending=False,
        )
        assert result.outcome == "sent_locally"
        ws_a.send_text.assert_awaited_once()
        await mgr_a.shutdown()

    async def test_agent_offline_queues_cleanly(self, mem_redis):
        src, dst = await _make_agents()
        task, msg = await _make_task_and_message(
            source_agent=src, target_agent=dst
        )
        decision = await _commit(
            RouteDecision(
                task_id=task.id,
                message_id=msg.message_id,
                selected_route_type="central_relay",
                selected_relay_node_id=None,
                candidate_routes=[],
                rejection_reasons={},
                shadow_mode=False,
            )
        )

        # No connection, no presence: plain offline.
        status = await deliver_task_request(task, msg, dst, route_decision=decision)
        assert status == DeliveryStatus.QUEUED.value

        events = await _delivery_events(task.id)
        queued = [e for e in events if e.event_type == "queued"]
        assert len(queued) == 1
        # A plain offline queue has no error code; only a degraded
        # pub/sub path would carry one.
        assert queued[0].error_code is None


# ---------------------------------------------------------------------------
# 6) session_service redis binding coverage
# ---------------------------------------------------------------------------


class TestRedisBindingCoverage:
    async def test_store_pending_message_never_touches_real_redis(self):
        """The module-level `from app.redis import redis_client` binding in
        session_service.py must be patchable and, when patched, be the only
        client the function uses — otherwise a test against a live
        `agentnet-test-redis` would silently pass while hitting the real
        server."""
        from app.services.session_service import store_pending_message

        mock = AsyncMock()
        agent_id = uuid.uuid4()
        with patch("app.services.session_service.redis_client", mock):
            await store_pending_message(agent_id, "sess-m3", json.dumps({"m": 1}))

        mock.lpush.assert_awaited_once()
        mock.expire.assert_awaited_once()
        # The call went to THIS mock and nowhere else.
        assert mock.lpush.call_args[0][0] == f"ws:session_pending:{agent_id}:sess-m3"


# ---------------------------------------------------------------------------
# 7) offline delivery worker
# ---------------------------------------------------------------------------


class TestOfflineDeliveryWorker:
    async def test_queue_intact_message_is_skipped(self, mem_redis):
        from app.workers.offline_delivery_worker import (
            deliver_offline_queued_messages,
        )

        src, dst = await _make_agents()
        task, msg = await _make_task_and_message(
            source_agent=src, target_agent=dst
        )
        async with SessionLocal() as session:
            row = await session.get(Message, msg.id)
            row.delivery_status = DeliveryStatus.QUEUED.value
            await session.commit()

        # The message IS in the pending queue (queue intact), and the
        # agent is online — connect-time delivery owns it, not the worker.
        from app.services.session_service import store_pending_message

        await store_pending_message(dst.id, str(dst.id), json.dumps({"message_id": msg.message_id}))

        from app.websocket.manager import get_connection_manager

        ws = _fake_ws()
        mgr = get_connection_manager()
        await mgr.register(ws, dst.id, dst.agent_number, str(dst.id))

        delivered = await deliver_offline_queued_messages()
        assert delivered == 0
        ws.send_text.assert_not_awaited()

        async with SessionLocal() as session:
            row = await session.get(Message, msg.id)
            assert row.delivery_status == DeliveryStatus.QUEUED.value

        await mgr.shutdown()

    async def test_queue_lost_message_is_delivered(self, mem_redis):
        from app.workers.offline_delivery_worker import (
            deliver_offline_queued_messages,
        )

        src, dst = await _make_agents()
        task, msg = await _make_task_and_message(
            source_agent=src, target_agent=dst
        )
        async with SessionLocal() as session:
            row = await session.get(Message, msg.id)
            row.delivery_status = DeliveryStatus.QUEUED.value
            await session.commit()

        # Queue entry lost (Redis restarted): nothing in the pending
        # queues, but the agent is online now. Arm the retry window so
        # the claim (which orders due rows first) picks this message
        # deterministically regardless of unrelated backlog rows.
        async with SessionLocal() as session:
            row = await session.get(Message, msg.id)
            row.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()

        from app.websocket.manager import get_connection_manager

        ws = _fake_ws()
        mgr = get_connection_manager()
        await mgr.register(ws, dst.id, dst.agent_number, str(dst.id))

        delivered = await deliver_offline_queued_messages()
        assert delivered == 1

        ws.send_text.assert_awaited_once()
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["message_id"] == msg.message_id

        async with SessionLocal() as session:
            row = await session.get(Message, msg.id)
            assert row.delivery_status == DeliveryStatus.DELIVERED.value
            assert row.next_retry_at is not None

        events = await _delivery_events(task.id)
        assert any(
            e.event_type == "delivered"
            and (e.extra_metadata or {}).get("source") == "offline_worker"
            for e in events
        )

        await mgr.shutdown()
