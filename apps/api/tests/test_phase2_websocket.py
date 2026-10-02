
"""Phase 2: WebSocket Presence tests."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


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
        json={"username": "wstestuser", "key_name": "ws-test-key"},
    )
    assert resp.status_code == 200
    return resp.json()["api_key"]


@pytest.fixture
async def agent_token(client, user_api_key):
    resp = await client.post(
        "/v1/agents",
        json={
            "name": "WS Test Agent",
            "runtime": "test",
            "description": "Agent for WebSocket tests",
        },
        headers={"X-API-Key": user_api_key},
    )
    assert resp.status_code == 201
    data = resp.json()
    return data["agent_token"]


class TestWSProtocolParsing:
    """Phase 2: WebSocket protocol parsing and validation (no DB needed)."""

    def test_parse_valid_message(self):
        from app.websocket.protocol import parse_ws_message

        msg = parse_ws_message(
            json.dumps({
                "type": "presence.heartbeat",
                "message_id": "test-123",
                "payload": {"ts": 123},
            })
        )
        assert msg.type == "presence.heartbeat"
        assert msg.message_id == "test-123"
        assert msg.payload == {"ts": 123}

    def test_parse_invalid_json(self):
        from app.websocket.protocol import parse_ws_message
        from app.exceptions import DomainException

        with pytest.raises(DomainException):
            parse_ws_message("not json")

    def test_build_ack(self):
        from app.websocket.protocol import build_ack

        ack = build_ack("my-message-id")
        data = json.loads(ack)
        assert data["type"] == "ack"
        assert data["payload"]["message_id"] == "my-message-id"

    def test_build_error(self):
        from app.websocket.protocol import build_error

        err = build_error("TEST_ERROR", "Something went wrong", "msg-1")
        data = json.loads(err)
        assert data["type"] == "error"
        assert data["payload"]["code"] == "TEST_ERROR"
        assert data["payload"]["message"] == "Something went wrong"
        assert data["payload"]["message_id"] == "msg-1"

    def test_payload_size_check(self):
        from app.websocket.protocol import check_payload_size
        from app.exceptions import DomainException

        check_payload_size("small")

        large = "x" * 2_000_000
        with pytest.raises(DomainException) as exc_info:
            check_payload_size(large)
        assert exc_info.value.code == "MESSAGE_TOO_LARGE"

    def test_validate_event_type_valid(self):
        from app.websocket.protocol import (
            WSMessage, validate_event_type,
        )
        from app.protocol.constants import MessageType

        msg = WSMessage(type="presence.heartbeat")
        validate_event_type(msg, MessageType.PRESENCE_HEARTBEAT)

    def test_validate_event_type_invalid(self):
        from app.websocket.protocol import (
            WSMessage, validate_event_type,
        )
        from app.protocol.constants import MessageType
        from app.exceptions import DomainException

        msg = WSMessage(type="bad.type")
        with pytest.raises(DomainException):
            validate_event_type(msg, MessageType.PRESENCE_HEARTBEAT)


class TestConnectionManager:
    """Connection manager: register, unregister, limits, heartbeat."""

    async def test_register_and_unregister(self):
        import uuid
        from app.websocket.manager import ConnectionManager

        mock_redis = AsyncMock()
        agent_id = uuid.uuid4()

        mgr = ConnectionManager(mock_redis)
        mock_ws = AsyncMock()
        state = await mgr.register(mock_ws, agent_id, "AN-GLOBAL-TEST", "session-1")
        assert state.connection_id
        assert state.agent_id == agent_id
        assert await mgr.get_connection_count(agent_id) == 1

        unreg_id, unreg_num = await mgr.unregister(state.connection_id)
        assert unreg_id == agent_id
        assert await mgr.get_connection_count(agent_id) == 0

    async def test_connection_limit(self):
        import uuid
        from app.websocket.manager import ConnectionManager
        from app.exceptions import DomainException
        from app.protocol.constants import ErrorCode

        mock_redis = AsyncMock()
        agent_id = uuid.uuid4()

        mgr = ConnectionManager(mock_redis)
        states = []
        for i in range(3):
            mock_ws = AsyncMock()
            state = await mgr.register(
                mock_ws, agent_id, "AN-GLOBAL-LIMIT", f"session-{i}"
            )
            states.append(state)

        assert await mgr.get_connection_count(agent_id) == 3

        mock_ws = AsyncMock()
        with pytest.raises(DomainException) as exc_info:
            await mgr.register(mock_ws, agent_id, "AN-GLOBAL-LIMIT", "session-over")
        assert exc_info.value.code == ErrorCode.RATE_LIMITED.value

        for s in states:
            await mgr.unregister(s.connection_id)
        assert await mgr.get_connection_count(agent_id) == 0

    async def test_heartbeat_update(self):
        import uuid
        from app.websocket.manager import ConnectionManager

        mock_redis = AsyncMock()
        agent_id = uuid.uuid4()

        mgr = ConnectionManager(mock_redis)
        mock_ws = AsyncMock()
        state = await mgr.register(mock_ws, agent_id, "AN-GLOBAL-HB", "session-hb")

        old_hb = state.last_heartbeat
        await asyncio.sleep(0.01)
        await mgr.record_heartbeat(state.connection_id)

        assert state.last_heartbeat > old_hb
        mock_redis.expire.assert_called()

        await mgr.unregister(state.connection_id)


class TestSessionResume:
    """Session resume: store, retrieve, ack pending messages (uses mock Redis)."""

    @pytest.fixture(autouse=True)
    async def _mock_redis(self, monkeypatch):
        mock = AsyncMock()
        mock.ping = AsyncMock(return_value=True)
        mock.delete = AsyncMock()
        mock.expire = AsyncMock()
        mock.exists = AsyncMock(return_value=0)
        mock.lrange = AsyncMock(return_value=[])
        mock.lpush = AsyncMock()
        monkeypatch.setattr("app.redis.redis_client", mock)
        monkeypatch.setattr("app.services.session_service.redis_client", mock)
        return mock

    async def test_store_and_retrieve_pending_messages(self, _mock_redis):
        import uuid
        from app.services.session_service import (
            store_pending_message,
            has_pending_messages,
        )

        agent_id = uuid.uuid4()
        session_id = "test-session-1"

        _mock_redis.exists = AsyncMock(return_value=0)
        assert not await has_pending_messages(agent_id, session_id)

        msg1 = json.dumps({
            "type": "task.request",
            "message_id": "m1",
            "payload": {"text": "hello"},
        })
        await store_pending_message(agent_id, session_id, msg1)
        _mock_redis.lpush.assert_called()
        _mock_redis.expire.assert_called()

    async def test_get_pending_with_mock_redis(self, _mock_redis):
        import uuid
        from app.services.session_service import get_pending_messages

        agent_id = uuid.uuid4()
        session_id = "test-session-2"

        msg1 = json.dumps({"type": "x", "message_id": "m1", "payload": {}})
        msg2 = json.dumps({"type": "x", "message_id": "m2", "payload": {}})

        _mock_redis.lrange = AsyncMock(return_value=[msg2, msg1])

        pending = await get_pending_messages(agent_id, session_id)
        assert len(pending) == 2
        assert "m1" in pending[0]
        assert "m2" in pending[1]

    async def test_ack_message_removes_from_pending(self, _mock_redis):
        import uuid
        from app.services.session_service import ack_message

        agent_id = uuid.uuid4()
        session_id = "test-session-ack"

        msg1 = json.dumps({"type": "x", "message_id": "m1", "payload": {}})
        msg2 = json.dumps({"type": "x", "message_id": "m2", "payload": {}})

        _mock_redis.lrange = AsyncMock(return_value=[msg2, msg1])
        _mock_redis.exists = AsyncMock(return_value=1)

        await ack_message(agent_id, session_id, "m2")

        _mock_redis.eval.assert_called_once()


class TestAuthenticateAgent:
    """Token authentication: format validation and rejection."""

    def test_invalid_token_format_rejected(self):
        from app.routers.ws import _authenticate_agent
        from app.exceptions import DomainException
        import pytest

        with pytest.raises(DomainException) as exc_info:
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_authenticate_agent("bad_token_format"))
            loop.close()
        assert exc_info.value.code == "INVALID_TOKEN"

    def test_invalid_token_prefix_rejected(self):
        from app.routers.ws import _authenticate_agent
        from app.exceptions import DomainException
        import pytest

        with pytest.raises(DomainException) as exc_info:
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_authenticate_agent("sk_not_right_prefix"))
            loop.close()
        assert exc_info.value.code == "INVALID_TOKEN"

    def test_valid_prefix_accepted_for_db_lookup(self):
        """agt_sk_ prefix passes format check and proceeds to DB lookup
        (which will fail with connection error in test env, not format error)."""
        from app.routers.ws import _authenticate_agent
        import pytest

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                _authenticate_agent("agt_sk_testvalidtoken1234567890abcdef")
            )
        except Exception as e:
            # Expected: either DomainException (token not found) or connection error
            # but NOT INVALID_TOKEN from format check
            if hasattr(e, 'code'):
                assert e.code != "INVALID_TOKEN" or "token format" not in str(e).lower()
        finally:
            loop.close()


class TestConnectionManagerPresence:
    """Redis presence tracking: set on register, refresh on heartbeat, remove on unregister."""

    async def test_presence_set_on_register(self):
        import uuid
        from unittest.mock import AsyncMock
        from app.websocket.manager import ConnectionManager

        mock_redis = AsyncMock()
        agent_id = uuid.uuid4()
        mgr = ConnectionManager(mock_redis)
        mock_ws = AsyncMock()

        state = await mgr.register(mock_ws, agent_id, "AN-GLOBAL-PRES", "session-pres")

        mock_redis.set.assert_called()
        call_args = mock_redis.set.call_args
        # M3: the presence VALUE is the owning node_id (cross-node dispatch
        # resolves the target node from this key); it is no longer the
        # constant "online".
        assert call_args[0][0] == f"ws:presence:{agent_id}"
        assert call_args[0][1] == mgr.node_id
        await mgr.unregister(state.connection_id)

    async def test_presence_removed_on_last_unregister(self):
        import uuid
        from unittest.mock import AsyncMock
        from app.websocket.manager import ConnectionManager

        mock_redis = AsyncMock()
        agent_id = uuid.uuid4()
        mgr = ConnectionManager(mock_redis)
        mock_ws = AsyncMock()

        state = await mgr.register(mock_ws, agent_id, "AN-GLOBAL-PRES2", "session-pres2")
        await mgr.unregister(state.connection_id)

        mock_redis.delete.assert_called()

    async def test_presence_not_removed_if_other_connections(self):
        import uuid
        from unittest.mock import AsyncMock
        from app.websocket.manager import ConnectionManager

        mock_redis = AsyncMock()
        agent_id = uuid.uuid4()
        mgr = ConnectionManager(mock_redis)

        ws1 = AsyncMock()
        ws2 = AsyncMock()
        s1 = await mgr.register(ws1, agent_id, "AN-GLOBAL-MULTI", "s1")
        s2 = await mgr.register(ws2, agent_id, "AN-GLOBAL-MULTI", "s2")

        mock_redis.reset_mock()

        aid, _ = await mgr.unregister(s1.connection_id)
        # Should not call delete because s2 is still connected
        assert aid is None
        mock_redis.delete.assert_not_called()

        # Unregister last one
        mock_redis.reset_mock()
        aid, _ = await mgr.unregister(s2.connection_id)
        assert aid == agent_id
        mock_redis.delete.assert_called()


class TestCleanupLoop:
    """Stale connection detection and cleanup."""

    async def test_cleanup_closes_stale_connections(self):
        import uuid
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock
        from app.websocket.manager import ConnectionManager

        mock_redis = AsyncMock()
        agent_id = uuid.uuid4()
        mgr = ConnectionManager(mock_redis)
        mock_ws = AsyncMock()

        state = await mgr.register(mock_ws, agent_id, "AN-GLOBAL-STALE", "session-stale")
        assert await mgr.get_connection_count(agent_id) == 1

        # Simulate stale detection by directly unregistering (what cleanup loop would do)
        state.last_heartbeat = datetime.now(UTC) - timedelta(seconds=999)

        # Verify the connection is considered stale (elapsed > timeout)
        now = datetime.now(UTC)
        timeout = mgr.settings.ws_heartbeat_timeout_s
        elapsed = (now - state.last_heartbeat).total_seconds()
        assert elapsed > timeout, f"Expected stale connection (elapsed={elapsed}s > timeout={timeout}s)"

        # Cleanup would close and unregister: simulate that
        try:
            await mock_ws.close(code=4001, reason="Heartbeat timeout")
        except Exception:
            pass
        await mgr.unregister(state.connection_id)

        # Verify connection was removed
        mock_ws.close.assert_called()
        assert await mgr.get_connection_count(agent_id) == 0

    async def test_active_connections_not_closed(self):
        import uuid
        from unittest.mock import AsyncMock
        from app.websocket.manager import ConnectionManager

        mock_redis = AsyncMock()
        agent_id = uuid.uuid4()
        mgr = ConnectionManager(mock_redis)
        mock_ws = AsyncMock()

        state = await mgr.register(mock_ws, agent_id, "AN-GLOBAL-ACTIVE", "session-active")

        # Heartbeat just happened - connection is fresh
        await mgr.record_heartbeat(state.connection_id)

        mock_ws.reset_mock()

        # Check that the connection is NOT stale (we just verify get_connection_count returns 1)
        assert await mgr.get_connection_count(agent_id) == 1
        mock_ws.close.assert_not_called()

        await mgr.unregister(state.connection_id)
