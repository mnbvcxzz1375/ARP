"""Phase 12: Routing Runtime Foundation (Shadow Mode) tests.

Tests the new routing runtime models, path optimizer shadow mode,
and REST API endpoints.
"""

import pytest
import uuid
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import SessionLocal
from app.models.relay_node import RelayNode
from app.models.route_decision import RouteDecision
from app.models.message_delivery_event import MessageDeliveryEvent
from sqlalchemy import select


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def user_api_key(client):
    resp = await client.post(
        "/v1/auth/register",
        json={"username": f"testuser-{uuid.uuid4().hex[:8]}", "key_name": "test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    return data["api_key"]


@pytest.fixture
async def other_api_key(client):
    resp = await client.post(
        "/v1/auth/register",
        json={"username": f"otheruser-{uuid.uuid4().hex[:8]}", "key_name": "other-key"},
    )
    assert resp.status_code == 200
    return resp.json()["api_key"]


class TestRelayNodeModel:
    """Test RelayNode model creation and relationships."""

    async def test_create_relay_node(self):
        async with SessionLocal() as session:
            node = RelayNode(
                node_name=f"test-relay-{uuid.uuid4().hex[:8]}",
                node_type="central",
                status="healthy",
                current_load=0.5,
                queue_depth=10,
                avg_latency_ms=50.0,
                success_rate=0.95,
                capabilities=["websocket", "task_delivery"],
                max_capacity=1000,
                region="us-west",
                zone="us-west-1a",
                enabled=True,
            )
            session.add(node)
            await session.commit()
            await session.refresh(node)

            assert node.id is not None
            assert node.node_name.startswith("test-relay-")
            assert node.node_type == "central"
            assert node.status == "healthy"
            assert node.current_load == 0.5
            assert node.queue_depth == 10


class TestRouteDecisionModel:
    """Test RouteDecision model creation."""

    async def test_create_route_decision(self, client, user_api_key):
        # Create agents and task
        resp = await client.post(
            "/v1/agents",
            json={"name": "Agent A", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        agent_a_number = resp.json()["agent_number"]

        resp = await client.post(
            "/v1/agents",
            json={"name": "Agent B", "runtime": "test", "inbound_policy": "public"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        agent_b_number = resp.json()["agent_number"]

        # Create task (this should trigger shadow route decision)
        resp = await client.post(
            "/v1/tasks",
            json={
                "assigned_to": agent_b_number,
                "from_agent_number": agent_a_number,
                "payload": {"action": "test"},
            },
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        # Verify route decision was created
        async with SessionLocal() as session:
            result = await session.execute(
                select(RouteDecision).where(RouteDecision.task_id == uuid.UUID(task_id))
            )
            decision = result.scalar_one_or_none()
            assert decision is not None
            assert decision.selected_route_type == "central_relay"
            # Phase 13: Now using enforced mode
            assert decision.shadow_mode is False
            assert decision.timeliness_mode == "normal"
            assert decision.decision_time_ms is not None


class TestPathOptimizerShadowMode:
    """Test path optimizer in shadow mode."""

    async def test_shadow_mode_does_not_change_delivery(self, client, user_api_key):
        """Verify enforced mode controls delivery (Phase 13 upgrade)."""
        # Create agents
        resp = await client.post(
            "/v1/agents",
            json={"name": "Sender", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        sender_number = resp.json()["agent_number"]

        resp = await client.post(
            "/v1/agents",
            json={"name": "Receiver", "runtime": "test", "inbound_policy": "public"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        receiver_number = resp.json()["agent_number"]

        # Create task
        resp = await client.post(
            "/v1/tasks",
            json={
                "assigned_to": receiver_number,
                "from_agent_number": sender_number,
                "payload": {"action": "test"},
            },
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        task_data = resp.json()

        # Task should be created successfully (existing behavior)
        assert task_data["status"] in ["created", "delivered"]

        # Route decision should be recorded in enforced mode
        async with SessionLocal() as session:
            result = await session.execute(
                select(RouteDecision).where(
                    RouteDecision.task_id == uuid.UUID(task_data["task_id"])
                )
            )
            decision = result.scalar_one_or_none()
            assert decision is not None
            # Phase 13: Now using enforced mode
            assert decision.shadow_mode is False


    async def test_connection_policy_filtering(self, client, user_api_key, other_api_key):
        """Test that path optimizer respects connection policy in shadow mode."""
        # Create sender agent (user 1)
        resp = await client.post(
            "/v1/agents",
            json={"name": "Sender", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        sender_number = resp.json()["agent_number"]

        # Create receiver agent (user 2) with private policy
        resp = await client.post(
            "/v1/agents",
            json={"name": "Receiver", "runtime": "test", "inbound_policy": "private"},
            headers={"X-API-Key": other_api_key},
        )
        assert resp.status_code == 201
        receiver_number = resp.json()["agent_number"]

        # Try to create task (should fail due to connection policy)
        resp = await client.post(
            "/v1/tasks",
            json={
                "assigned_to": receiver_number,
                "from_agent_number": sender_number,
                "payload": {"action": "test"},
            },
            headers={"X-API-Key": user_api_key},
        )
        # Should fail at connection policy enforcement (Phase 5)
        assert resp.status_code in [403, 409]


class TestRelayNodeAPI:
    """Test relay node REST API endpoints."""

    async def test_register_relay_node(self, client, user_api_key):
        resp = await client.post(
            "/v1/relay-nodes/register",
            json={
                "node_name": f"test-node-{uuid.uuid4().hex[:8]}",
                "node_type": "personal_edge",
                "region": "us-east",
                "zone": "us-east-1a",
                "capabilities": ["websocket"],
                "max_capacity": 5000,
                "metadata": {"version": "1.0"},
            },
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["node_type"] == "personal_edge"
        assert data["status"] == "unknown"
        assert data["enabled"] is True

    async def test_register_duplicate_node_name_fails(self, client, user_api_key):
        node_name = f"unique-node-{uuid.uuid4().hex[:8]}"

        # First registration succeeds
        resp = await client.post(
            "/v1/relay-nodes/register",
            json={"node_name": node_name, "node_type": "personal_edge"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201

        # Second registration with same name fails
        resp = await client.post(
            "/v1/relay-nodes/register",
            json={"node_name": node_name, "node_type": "personal_edge"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 409

    async def test_relay_node_heartbeat(self, client, user_api_key):
        # Register node
        resp = await client.post(
            "/v1/relay-nodes/register",
            json={
                "node_name": f"heartbeat-node-{uuid.uuid4().hex[:8]}",
                "node_type": "personal_edge",
            },
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        node_id = resp.json()["id"]

        # Send heartbeat
        resp = await client.post(
            f"/v1/relay-nodes/{node_id}/heartbeat",
            json={
                "current_load": 0.3,
                "queue_depth": 5,
                "avg_latency_ms": 45.0,
                "success_rate": 0.98,
            },
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["current_load"] == 0.3
        assert data["queue_depth"] == 5
        assert data["last_heartbeat_at"] is not None

    async def test_relay_node_status_degraded(self, client, user_api_key):
        # Register node
        resp = await client.post(
            "/v1/relay-nodes/register",
            json={
                "node_name": f"degraded-node-{uuid.uuid4().hex[:8]}",
                "node_type": "personal_edge",
            },
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        node_id = resp.json()["id"]

        # Send heartbeat with degraded metrics
        resp = await client.post(
            f"/v1/relay-nodes/{node_id}/heartbeat",
            json={
                "current_load": 0.85,
                "queue_depth": 300,
                "avg_latency_ms": 200.0,
                "success_rate": 0.75,
            },
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"

    async def test_list_relay_nodes(self, client, user_api_key):
        # Register a few nodes
        for i in range(3):
            await client.post(
                "/v1/relay-nodes/register",
                json={
                    "node_name": f"list-test-node-{i}-{uuid.uuid4().hex[:8]}",
                    "node_type": "central" if i == 0 else "regional",
                },
                headers={"X-API-Key": user_api_key},
            )

        # List all nodes
        resp = await client.get(
            "/v1/relay-nodes",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert len(data["nodes"]) >= 3

    async def test_list_relay_nodes_filtered_by_type(self, client, user_api_key):
        # Register nodes of different types
        await client.post(
            "/v1/relay-nodes/register",
            json={
                "node_name": f"filter-central-{uuid.uuid4().hex[:8]}",
                "node_type": "central",
            },
            headers={"X-API-Key": user_api_key},
        )
        await client.post(
            "/v1/relay-nodes/register",
            json={
                "node_name": f"filter-regional-{uuid.uuid4().hex[:8]}",
                "node_type": "regional",
            },
            headers={"X-API-Key": user_api_key},
        )

        # Filter by type
        resp = await client.get(
            "/v1/relay-nodes?node_type=regional",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(node["node_type"] == "regional" for node in data["nodes"])


class TestRouteDecisionAPI:
    """Test route decision REST API endpoints."""

    async def test_list_route_decisions(self, client, user_api_key):
        # Create task to generate route decision
        resp = await client.post(
            "/v1/agents",
            json={"name": "Agent A", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        agent_a = resp.json()["agent_number"]

        resp = await client.post(
            "/v1/agents",
            json={"name": "Agent B", "runtime": "test", "inbound_policy": "public"},
            headers={"X-API-Key": user_api_key},
        )
        agent_b = resp.json()["agent_number"]

        await client.post(
            "/v1/tasks",
            json={
                "assigned_to": agent_b,
                "from_agent_number": agent_a,
                "payload": {"test": "data"},
            },
            headers={"X-API-Key": user_api_key},
        )

        # List route decisions
        resp = await client.get(
            "/v1/routes/decisions",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["decisions"]) >= 1

    async def test_get_route_decision_by_id(self, client, user_api_key):
        # Create task
        resp = await client.post(
            "/v1/agents",
            json={"name": "Agent A", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        agent_a = resp.json()["agent_number"]

        resp = await client.post(
            "/v1/agents",
            json={"name": "Agent B", "runtime": "test", "inbound_policy": "public"},
            headers={"X-API-Key": user_api_key},
        )
        agent_b = resp.json()["agent_number"]

        resp = await client.post(
            "/v1/tasks",
            json={
                "assigned_to": agent_b,
                "from_agent_number": agent_a,
                "payload": {"test": "data"},
            },
            headers={"X-API-Key": user_api_key},
        )
        task_id = resp.json()["task_id"]

        # Get route decisions for task
        resp = await client.get(
            f"/v1/tasks/{task_id}/route-decisions",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        decision_id = data["decisions"][0]["id"]

        # Get specific decision
        resp = await client.get(
            f"/v1/routes/decisions/{decision_id}",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        decision = resp.json()
        assert decision["id"] == decision_id
        # Phase 13: Now using enforced mode
        assert decision["shadow_mode"] is False


class TestDeliveryEventsAPI:
    """Test delivery events REST API endpoints."""

    async def test_list_task_delivery_events(self, client, user_api_key):
        # Create task
        resp = await client.post(
            "/v1/agents",
            json={"name": "Agent A", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        agent_a = resp.json()["agent_number"]

        resp = await client.post(
            "/v1/agents",
            json={"name": "Agent B", "runtime": "test", "inbound_policy": "public"},
            headers={"X-API-Key": user_api_key},
        )
        agent_b = resp.json()["agent_number"]

        resp = await client.post(
            "/v1/tasks",
            json={
                "assigned_to": agent_b,
                "from_agent_number": agent_a,
                "payload": {"test": "data"},
            },
            headers={"X-API-Key": user_api_key},
        )
        task_id = resp.json()["task_id"]

        # Get delivery events (may be empty in Phase 12 since we don't record them yet)
        resp = await client.get(
            f"/v1/tasks/{task_id}/delivery-events",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "total" in data


class TestPathOptimizerScoring:
    """Test path optimizer scoring logic."""

    async def test_timeliness_mode_affects_scoring(self):
        """Verify different timeliness modes produce different scores."""
        from app.services.path_optimizer import RouteCandidate

        candidate = RouteCandidate("central_relay")
        candidate.latency_ms = 100.0
        candidate.relay_load = 0.5
        candidate.queue_depth = 10
        candidate.delivery_success_rate = 0.95
        candidate.failure_rate = 0.05

        # Realtime mode should heavily weight latency
        realtime_score = candidate.compute_final_score("realtime")

        # Batch mode should weight cost more
        batch_score = candidate.compute_final_score("batch")

        # Durable mode should weight success rate more
        durable_score = candidate.compute_final_score("durable")

        # Scores should be different
        assert realtime_score != batch_score
        assert realtime_score != durable_score
        assert batch_score != durable_score


class TestFailurePaths:
    """Test failure paths and error handling."""

    async def test_invalid_relay_node_id_format(self, client, user_api_key):
        resp = await client.post(
            "/v1/relay-nodes/invalid-uuid/heartbeat",
            json={"current_load": 0.5, "queue_depth": 10},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 400

    async def test_nonexistent_relay_node_heartbeat(self, client, user_api_key):
        fake_uuid = str(uuid.uuid4())
        resp = await client.post(
            f"/v1/relay-nodes/{fake_uuid}/heartbeat",
            json={"current_load": 0.5, "queue_depth": 10},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 404

    async def test_invalid_route_decision_id_format(self, client, user_api_key):
        resp = await client.get(
            "/v1/routes/decisions/invalid-uuid",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 400

    async def test_nonexistent_route_decision(self, client, user_api_key):
        fake_uuid = str(uuid.uuid4())
        resp = await client.get(
            f"/v1/routes/decisions/{fake_uuid}",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 404

    async def test_delivery_events_for_nonexistent_task(self, client, user_api_key):
        fake_uuid = str(uuid.uuid4())
        resp = await client.get(
            f"/v1/tasks/{fake_uuid}/delivery-events",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 404
