"""Tests for Phase 17: Dedicated Channel functionality."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.agent import Agent
from app.models.channel_health_check import ChannelHealthCheck
from app.models.dedicated_channel import DedicatedChannel
from app.models.task import Task
from app.models.user import User
from app.services.dedicated_channel_service import (
    create_dedicated_channel,
    fallback_to_relay,
    select_dedicated_channel,
    verify_channel_health,
)
from app.services.path_optimizer import select_route


@pytest.fixture
async def test_user(session):
    """Create a test user."""
    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}",
        role="user",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def source_agent(session, test_user):
    """Create source agent."""
    agent = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:8].upper()}",
        name="Source Agent",
        runtime="python",
        inbound_policy="public",
        status="online",
    )
    session.add(agent)
    await session.flush()
    return agent


@pytest.fixture
async def target_agent(session, test_user):
    """Create target agent."""
    agent = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:8].upper()}",
        name="Target Agent",
        runtime="python",
        inbound_policy="public",
        status="online",
    )
    session.add(agent)
    await session.flush()
    return agent


@pytest.fixture
async def test_task(session, source_agent, target_agent):
    """Create a test task."""
    task = Task(
        created_by=source_agent.id,
        assigned_to=target_agent.id,
        status="created",
    )
    session.add(task)
    await session.flush()
    return task


class TestDedicatedChannelCreation:
    """Test dedicated channel creation."""

    async def test_create_vpn_channel(self, session, source_agent, target_agent):
        """Test creating a VPN channel."""
        channel = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="test-vpn-channel",
            channel_type="vpn",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={
                "endpoint": "vpn.example.com:443",
                "protocol": "wireguard",
                "public_key": "test_key_123",
            },
            encryption_config={
                "algorithm": "AES-256-GCM",
                "key_rotation_days": 30,
                "tls_version": "1.3",
            },
            bandwidth_mbps=100.0,
            latency_target_ms=10.0,
        )

        assert channel.id is not None
        assert channel.channel_name == "test-vpn-channel"
        assert channel.channel_type == "vpn"
        assert channel.source_agent_id == source_agent.id
        assert channel.target_agent_id == target_agent.id
        assert channel.enabled is True
        assert channel.bandwidth_mbps == 100.0
        assert channel.latency_target_ms == 10.0

    async def test_create_private_link_channel(self, session, source_agent, target_agent):
        """Test creating a private link channel."""
        channel = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="test-private-link",
            channel_type="private_link",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={
                "endpoint": "pl-endpoint.aws.com",
                "service_name": "com.amazonaws.vpce.us-east-1.vpce-svc-123",
            },
            encryption_config={"tls_version": "1.3"},
            bandwidth_mbps=1000.0,
            latency_target_ms=5.0,
        )

        assert channel.channel_type == "private_link"
        assert channel.bandwidth_mbps == 1000.0

    async def test_create_p2p_channel(self, session, source_agent, target_agent):
        """Test creating a P2P channel."""
        channel = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="test-p2p",
            channel_type="p2p",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={
                "protocol": "webrtc",
                "ice_servers": ["stun:stun.l.google.com:19302"],
            },
            encryption_config={"dtls": True},
        )

        assert channel.channel_type == "p2p"

    async def test_invalid_channel_type(self, session, source_agent, target_agent):
        """Test creating channel with invalid type."""
        from app.exceptions import DomainException

        with pytest.raises(DomainException) as exc_info:
            await create_dedicated_channel(
                session,
                scope_id=None,
                channel_name="test-invalid",
                channel_type="invalid_type",
                source_agent_id=source_agent.id,
                target_agent_id=target_agent.id,
                connection_config={},
                encryption_config={},
            )

        assert "Invalid channel_type" in str(exc_info.value)


class TestChannelHealthCheck:
    """Test channel health checking."""

    async def test_verify_healthy_channel(self, session, source_agent, target_agent):
        """Test health check on healthy channel."""
        channel = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="test-healthy",
            channel_type="vpn",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={
                "health_check": {
                    "status": "healthy",
                    "latency_ms": 10.0,
                    "packet_loss_percent": 0.0,
                    "bandwidth_mbps": 100.0,
                },
            },
            encryption_config={},
            latency_target_ms=10.0,
        )

        health_check = await verify_channel_health(session, channel.id)

        assert health_check.channel_id == channel.id
        assert health_check.status == "healthy"
        assert health_check.latency_ms == 10.0
        assert health_check.packet_loss_percent == 0.0
        assert health_check.bandwidth_mbps == 100.0
        assert health_check.error_message is None

    async def test_verify_enabled_channel_no_health_check(self, session, source_agent, target_agent):
        """Test health check on enabled channel without health_check report in connection_config."""
        channel = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="test-no-health-check",
            channel_type="vpn",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={},
            encryption_config={},
        )

        health_check = await verify_channel_health(session, channel.id)

        assert health_check.status == "down"
        assert health_check.error_message == "Dedicated channel health_check is missing or invalid"

        # select_dedicated_channel should also not select it
        selected = await select_dedicated_channel(
            session, source_agent.id, target_agent.id
        )
        assert selected is None

    async def test_verify_disabled_channel(self, session, source_agent, target_agent):
        """Test health check on disabled channel."""
        channel = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="test-disabled",
            channel_type="vpn",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={},
            encryption_config={},
        )

        # Disable channel
        channel.enabled = False
        await session.flush()

        health_check = await verify_channel_health(session, channel.id)

        assert health_check.status == "down"
        assert health_check.error_message == "Channel is disabled"


class TestChannelSelection:
    """Test dedicated channel selection."""

    async def test_select_dedicated_channel_db_error(
        self, session, source_agent, target_agent
    ):
        """Test that DB error querying DedicatedChannel raises DomainException (fail closed)."""
        from unittest.mock import patch

        from app.exceptions import DomainException
        from app.protocol.constants import ErrorCode

        async def failing_execute(*args, **kwargs):
            raise ConnectionError("DB connection lost")

        with patch.object(session, "execute", failing_execute):
            with pytest.raises(DomainException) as exc_info:
                await select_dedicated_channel(
                    session, source_agent.id, target_agent.id
                )

        assert exc_info.value.code == ErrorCode.INTERNAL_ERROR.value
        assert exc_info.value.status_code == 503
        assert "dedicated channels" in str(exc_info.value.message).lower()

    async def test_select_dedicated_channel_health_check_db_error(
        self, session, source_agent, target_agent
    ):
        """Test that DB error checking ChannelHealthCheck raises DomainException (fail closed)."""
        from unittest.mock import patch

        from app.exceptions import DomainException
        from app.protocol.constants import ErrorCode

        # Create a channel so DedicatedChannel query succeeds
        channel = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="hc-fail",
            channel_type="vpn",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={},
            encryption_config={},
        )
        assert channel.id is not None

        original_execute = session.execute
        call_count = 0

        async def mock_execute(stmt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return await original_execute(stmt, *args, **kwargs)
            raise ConnectionError("DB connection lost")

        with patch.object(session, "execute", mock_execute):
            with pytest.raises(DomainException) as exc_info:
                await select_dedicated_channel(
                    session, source_agent.id, target_agent.id
                )

        assert exc_info.value.code == ErrorCode.INTERNAL_ERROR.value
        assert exc_info.value.status_code == 503
        assert "channel" in str(exc_info.value.message).lower()

    async def test_select_best_channel(self, session, source_agent, target_agent):
        """Test selecting the best available channel."""
        # Create two channels with different latencies
        channel1 = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="channel-1",
            channel_type="vpn",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={
                "health_check": {
                    "status": "healthy",
                    "latency_ms": 20.0,
                    "packet_loss_percent": 0.0,
                },
            },
            encryption_config={},
            latency_target_ms=20.0,
        )

        channel2 = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="channel-2",
            channel_type="private_link",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={
                "health_check": {
                    "status": "healthy",
                    "latency_ms": 5.0,
                    "packet_loss_percent": 0.0,
                },
            },
            encryption_config={},
            latency_target_ms=5.0,
        )

        # Create health checks
        await verify_channel_health(session, channel1.id)
        await verify_channel_health(session, channel2.id)

        # Select best channel (should be channel2 with lower latency)
        selected = await select_dedicated_channel(
            session, source_agent.id, target_agent.id
        )

        assert selected is not None
        assert selected.id == channel2.id
        assert selected.latency_target_ms == 5.0

    async def test_select_no_channel(self, session, source_agent, target_agent):
        """Test selection when no channel exists."""
        selected = await select_dedicated_channel(
            session, source_agent.id, target_agent.id
        )

        assert selected is None

    async def test_select_only_healthy_channels(self, session, source_agent, target_agent):
        """Test that only healthy channels are selected."""
        # Create channel and mark it as unhealthy
        channel = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="unhealthy-channel",
            channel_type="vpn",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={},
            encryption_config={},
        )

        # Create unhealthy health check
        health_check = ChannelHealthCheck(
            channel_id=channel.id,
            check_time=datetime.now(UTC),
            status="down",
            error_message="Connection timeout",
        )
        session.add(health_check)
        await session.flush()

        # Should not select unhealthy channel
        selected = await select_dedicated_channel(
            session, source_agent.id, target_agent.id
        )

        assert selected is None


class TestPathOptimizerIntegration:
    """Test dedicated channel integration with path optimizer."""

    async def test_dedicated_channel_priority(
        self, session, source_agent, target_agent, test_task
    ):
        """Test that dedicated channel has highest priority in route selection."""
        # Create dedicated channel
        channel = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="priority-test",
            channel_type="vpn",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={
                "health_check": {
                    "status": "healthy",
                    "latency_ms": 5.0,
                    "packet_loss_percent": 0.0,
                },
            },
            encryption_config={},
            latency_target_ms=5.0,
        )

        # Create health check
        await verify_channel_health(session, channel.id)

        # Create default relay node
        from app.services.path_optimizer import ensure_default_relay_node

        await ensure_default_relay_node(session)

        # Select route
        decision = await select_route(
            session,
            task=test_task,
            from_agent=source_agent,
            to_agent=target_agent,
            message_id=str(uuid.uuid4()),
            timeliness_mode="realtime",
        )

        # Should select dedicated_channel
        assert decision.selected_route_type == "dedicated_channel"
        assert decision.shadow_mode is False


class TestFallbackMechanism:
    """Test fallback to relay when channel fails."""

    async def test_fallback_to_relay_audit(self, session, source_agent, target_agent):
        """Test that fallback to relay is audited."""
        channel = await create_dedicated_channel(
            session,
            scope_id=None,
            channel_name="fallback-test",
            channel_type="vpn",
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            connection_config={},
            encryption_config={},
        )

        # Record fallback
        await fallback_to_relay(
            session,
            channel_id=channel.id,
            reason="Channel health check failed",
        )

        # Verify audit log was created
        from app.models.audit_log import AuditLog

        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "fallback_to_relay",
                AuditLog.resource_id == str(channel.id),
            )
        )
        audit_log = result.scalar_one_or_none()

        assert audit_log is not None
        assert audit_log.resource_type == "dedicated_channel"
        assert "Channel health check failed" in audit_log.details["reason"]
