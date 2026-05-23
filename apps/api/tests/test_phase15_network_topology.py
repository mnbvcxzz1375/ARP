"""Tests for Phase 15 Network Topology models and service."""

import uuid

import pytest
from sqlalchemy import select

from app.exceptions import DomainException
from app.models.network_scope import NetworkScope
from app.models.network_zone import NetworkZone
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.services import network_topology_service


@pytest.fixture
async def test_user(session):
    """Create a test user."""
    user = User(id=uuid.uuid4(), username=f"testuser-{uuid.uuid4().hex[:8]}")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


class TestNetworkScopeModel:
    """Test NetworkScope model."""

    async def test_create_network_scope(self, session, test_user):
        """Test creating a network scope."""
        scope = NetworkScope(
            id=uuid.uuid4(),
            user_id=test_user.id,
            scope_name="Test Enterprise Scope",
            scope_type="enterprise",
            network_cidr="10.0.0.0/8",
            agent_ids=[],
            zone_ids=[],
        )

        session.add(scope)
        await session.flush()
        await session.refresh(scope)

        assert scope.id is not None
        assert scope.user_id == test_user.id
        assert scope.scope_name == "Test Enterprise Scope"
        assert scope.scope_type == "enterprise"
        assert scope.network_cidr == "10.0.0.0/8"
        assert scope.agent_ids == []
        assert scope.zone_ids == []
        assert scope.created_at is not None
        assert scope.updated_at is not None

    async def test_network_scope_user_relationship(self, session, test_user):
        """Test NetworkScope -> User relationship."""
        scope = NetworkScope(
            id=uuid.uuid4(),
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="personal",
        )

        session.add(scope)
        await session.flush()
        await session.refresh(scope)

        # Test relationship
        assert scope.user is not None
        assert scope.user.id == test_user.id
        assert scope.user.username == test_user.username

    async def test_network_scope_cascade_delete(self, session, test_user):
        """Test that deleting user cascades to network scopes."""
        scope = NetworkScope(
            id=uuid.uuid4(),
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )

        session.add(scope)
        await session.flush()
        scope_id = scope.id

        # Delete user
        await session.delete(test_user)
        await session.flush()

        # Verify scope is deleted
        result = await session.execute(select(NetworkScope).where(NetworkScope.id == scope_id))
        deleted_scope = result.scalar_one_or_none()
        assert deleted_scope is None


class TestNetworkZoneModel:
    """Test NetworkZone model."""

    async def test_create_network_zone(self, session, test_user):
        """Test creating a network zone."""
        # Create scope first
        scope = NetworkScope(
            id=uuid.uuid4(),
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )
        session.add(scope)
        await session.flush()

        # Create zone
        zone = NetworkZone(
            id=uuid.uuid4(),
            scope_id=scope.id,
            zone_name="US West Region",
            zone_type="regional",
            relay_node_ids=[],
            zone_metadata={"region": "us-west-2", "latency_target_ms": 50},
        )

        session.add(zone)
        await session.flush()
        await session.refresh(zone)

        assert zone.id is not None
        assert zone.scope_id == scope.id
        assert zone.zone_name == "US West Region"
        assert zone.zone_type == "regional"
        assert zone.parent_zone_id is None
        assert zone.relay_node_ids == []
        assert zone.zone_metadata == {"region": "us-west-2", "latency_target_ms": 50}
        assert zone.created_at is not None
        assert zone.updated_at is not None

    async def test_network_zone_scope_relationship(self, session, test_user):
        """Test NetworkZone -> NetworkScope relationship."""
        scope = NetworkScope(
            id=uuid.uuid4(),
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )
        session.add(scope)
        await session.flush()

        zone = NetworkZone(
            id=uuid.uuid4(),
            scope_id=scope.id,
            zone_name="Test Zone",
            zone_type="local",
        )
        session.add(zone)
        await session.flush()
        await session.refresh(zone)

        # Test relationship
        assert zone.scope is not None
        assert zone.scope.id == scope.id
        assert zone.scope.scope_name == "Test Scope"

    async def test_network_zone_hierarchical_relationship(self, session, test_user):
        """Test NetworkZone parent-child relationship."""
        scope = NetworkScope(
            id=uuid.uuid4(),
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )
        session.add(scope)
        await session.flush()

        # Create parent zone
        parent_zone = NetworkZone(
            id=uuid.uuid4(),
            scope_id=scope.id,
            zone_name="Global Zone",
            zone_type="global",
        )
        session.add(parent_zone)
        await session.flush()

        # Create child zone
        child_zone = NetworkZone(
            id=uuid.uuid4(),
            scope_id=scope.id,
            zone_name="Regional Zone",
            zone_type="regional",
            parent_zone_id=parent_zone.id,
        )
        session.add(child_zone)
        await session.flush()
        await session.refresh(child_zone)
        await session.refresh(parent_zone)

        # Test parent relationship
        assert child_zone.parent_zone is not None
        assert child_zone.parent_zone.id == parent_zone.id
        assert child_zone.parent_zone.zone_name == "Global Zone"

        # Test child relationship
        assert len(parent_zone.child_zones) == 1
        assert parent_zone.child_zones[0].id == child_zone.id

    async def test_network_zone_cascade_delete(self, session, test_user):
        """Test that deleting scope cascades to zones."""
        scope = NetworkScope(
            id=uuid.uuid4(),
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )
        session.add(scope)
        await session.flush()

        zone = NetworkZone(
            id=uuid.uuid4(),
            scope_id=scope.id,
            zone_name="Test Zone",
            zone_type="local",
        )
        session.add(zone)
        await session.flush()
        zone_id = zone.id

        # Delete scope
        await session.delete(scope)
        await session.flush()

        # Verify zone is deleted
        result = await session.execute(select(NetworkZone).where(NetworkZone.id == zone_id))
        deleted_zone = result.scalar_one_or_none()
        assert deleted_zone is None

    async def test_network_zone_parent_set_null_on_delete(self, session, test_user):
        """Test that deleting parent zone sets parent_zone_id to NULL."""
        scope = NetworkScope(
            id=uuid.uuid4(),
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )
        session.add(scope)
        await session.flush()

        parent_zone = NetworkZone(
            id=uuid.uuid4(),
            scope_id=scope.id,
            zone_name="Parent Zone",
            zone_type="global",
        )
        session.add(parent_zone)
        await session.flush()

        child_zone = NetworkZone(
            id=uuid.uuid4(),
            scope_id=scope.id,
            zone_name="Child Zone",
            zone_type="regional",
            parent_zone_id=parent_zone.id,
        )
        session.add(child_zone)
        await session.flush()
        child_zone_id = child_zone.id

        # Delete parent zone
        await session.delete(parent_zone)
        await session.flush()

        # Verify child zone still exists but parent_zone_id is NULL
        result = await session.execute(select(NetworkZone).where(NetworkZone.id == child_zone_id))
        updated_child = result.scalar_one_or_none()
        assert updated_child is not None
        assert updated_child.parent_zone_id is None


class TestNetworkTopologyService:
    """Test network topology service."""

    async def test_create_network_scope_success(self, session, test_user):
        """Test creating a network scope via service."""
        scope = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Enterprise Network",
            scope_type="enterprise",
            network_cidr="10.0.0.0/8",
        )

        assert scope.id is not None
        assert scope.user_id == test_user.id
        assert scope.scope_name == "Enterprise Network"
        assert scope.scope_type == "enterprise"
        assert scope.network_cidr == "10.0.0.0/8"

    async def test_create_network_scope_user_not_found(self, session):
        """Test creating scope with non-existent user fails."""
        fake_user_id = uuid.uuid4()

        with pytest.raises(DomainException) as exc_info:
            await network_topology_service.create_network_scope(
                session,
                user_id=fake_user_id,
                scope_name="Test Scope",
                scope_type="enterprise",
            )

        assert exc_info.value.code == ErrorCode.INVALID_REQUEST
        assert str(fake_user_id) in exc_info.value.message

    async def test_create_network_scope_invalid_type(self, session, test_user):
        """Test creating scope with invalid type fails."""
        with pytest.raises(DomainException) as exc_info:
            await network_topology_service.create_network_scope(
                session,
                user_id=test_user.id,
                scope_name="Test Scope",
                scope_type="invalid_type",
            )

        assert exc_info.value.code == ErrorCode.INVALID_REQUEST
        assert "Invalid scope_type" in exc_info.value.message

    async def test_get_network_scope_success(self, session, test_user):
        """Test getting a network scope."""
        created_scope = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="personal",
        )

        retrieved_scope = await network_topology_service.get_network_scope(
            session, scope_id=created_scope.id
        )

        assert retrieved_scope.id == created_scope.id
        assert retrieved_scope.scope_name == "Test Scope"

    async def test_get_network_scope_not_found(self, session):
        """Test getting non-existent scope fails."""
        fake_scope_id = uuid.uuid4()

        with pytest.raises(DomainException) as exc_info:
            await network_topology_service.get_network_scope(session, scope_id=fake_scope_id)

        assert exc_info.value.code == ErrorCode.INVALID_REQUEST
        assert str(fake_scope_id) in exc_info.value.message

    async def test_list_network_scopes(self, session, test_user):
        """Test listing network scopes."""
        # Create multiple scopes
        await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Personal Scope",
            scope_type="personal",
        )
        await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Enterprise Scope",
            scope_type="enterprise",
        )

        # List all scopes
        all_scopes = await network_topology_service.list_network_scopes(
            session, user_id=test_user.id
        )
        assert len(all_scopes) == 2

        # List filtered by type
        personal_scopes = await network_topology_service.list_network_scopes(
            session, user_id=test_user.id, scope_type="personal"
        )
        assert len(personal_scopes) == 1
        assert personal_scopes[0].scope_type == "personal"

    async def test_create_network_zone_success(self, session, test_user):
        """Test creating a network zone via service."""
        scope = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )

        zone = await network_topology_service.create_network_zone(
            session,
            scope_id=scope.id,
            zone_name="US West",
            zone_type="regional",
            zone_metadata={"region": "us-west-2"},
        )

        assert zone.id is not None
        assert zone.scope_id == scope.id
        assert zone.zone_name == "US West"
        assert zone.zone_type == "regional"
        assert zone.zone_metadata == {"region": "us-west-2"}

    async def test_create_network_zone_scope_not_found(self, session):
        """Test creating zone with non-existent scope fails."""
        fake_scope_id = uuid.uuid4()

        with pytest.raises(DomainException) as exc_info:
            await network_topology_service.create_network_zone(
                session,
                scope_id=fake_scope_id,
                zone_name="Test Zone",
                zone_type="local",
            )

        assert exc_info.value.code == ErrorCode.INVALID_REQUEST
        assert str(fake_scope_id) in exc_info.value.message

    async def test_create_network_zone_invalid_type(self, session, test_user):
        """Test creating zone with invalid type fails."""
        scope = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )

        with pytest.raises(DomainException) as exc_info:
            await network_topology_service.create_network_zone(
                session,
                scope_id=scope.id,
                zone_name="Test Zone",
                zone_type="invalid_type",
            )

        assert exc_info.value.code == ErrorCode.INVALID_REQUEST
        assert "Invalid zone_type" in exc_info.value.message

    async def test_create_network_zone_parent_not_found(self, session, test_user):
        """Test creating zone with non-existent parent fails."""
        scope = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )

        fake_parent_id = uuid.uuid4()

        with pytest.raises(DomainException) as exc_info:
            await network_topology_service.create_network_zone(
                session,
                scope_id=scope.id,
                zone_name="Child Zone",
                zone_type="local",
                parent_zone_id=fake_parent_id,
            )

        assert exc_info.value.code == ErrorCode.INVALID_REQUEST
        assert str(fake_parent_id) in exc_info.value.message

    async def test_create_network_zone_parent_wrong_scope(self, session, test_user):
        """Test creating zone with parent from different scope fails."""
        scope1 = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Scope 1",
            scope_type="enterprise",
        )

        scope2 = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Scope 2",
            scope_type="enterprise",
        )

        parent_zone = await network_topology_service.create_network_zone(
            session,
            scope_id=scope1.id,
            zone_name="Parent Zone",
            zone_type="global",
        )

        with pytest.raises(DomainException) as exc_info:
            await network_topology_service.create_network_zone(
                session,
                scope_id=scope2.id,
                zone_name="Child Zone",
                zone_type="regional",
                parent_zone_id=parent_zone.id,
            )

        assert exc_info.value.code == ErrorCode.INVALID_REQUEST
        assert "does not belong to scope" in exc_info.value.message

    async def test_get_zones_in_scope(self, session, test_user):
        """Test getting zones in a scope."""
        scope = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )

        # Create multiple zones
        await network_topology_service.create_network_zone(
            session,
            scope_id=scope.id,
            zone_name="Zone 1",
            zone_type="regional",
        )
        await network_topology_service.create_network_zone(
            session,
            scope_id=scope.id,
            zone_name="Zone 2",
            zone_type="local",
        )

        # Get all zones
        all_zones = await network_topology_service.get_zones_in_scope(
            session, scope_id=scope.id
        )
        assert len(all_zones) == 2

        # Get filtered by type
        regional_zones = await network_topology_service.get_zones_in_scope(
            session, scope_id=scope.id, zone_type="regional"
        )
        assert len(regional_zones) == 1
        assert regional_zones[0].zone_type == "regional"

    async def test_get_zones_in_scope_not_found(self, session):
        """Test getting zones for non-existent scope fails."""
        fake_scope_id = uuid.uuid4()

        with pytest.raises(DomainException) as exc_info:
            await network_topology_service.get_zones_in_scope(session, scope_id=fake_scope_id)

        assert exc_info.value.code == ErrorCode.INVALID_REQUEST

    async def test_update_network_scope(self, session, test_user):
        """Test updating a network scope."""
        scope = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Original Name",
            scope_type="enterprise",
        )

        updated_scope = await network_topology_service.update_network_scope(
            session,
            scope_id=scope.id,
            scope_name="Updated Name",
            network_cidr="192.168.0.0/16",
        )

        assert updated_scope.scope_name == "Updated Name"
        assert updated_scope.network_cidr == "192.168.0.0/16"

    async def test_delete_network_scope(self, session, test_user):
        """Test deleting a network scope."""
        scope = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )

        scope_id = scope.id

        await network_topology_service.delete_network_scope(session, scope_id=scope_id)

        # Verify scope is deleted
        with pytest.raises(DomainException) as exc_info:
            await network_topology_service.get_network_scope(session, scope_id=scope_id)

        assert exc_info.value.code == ErrorCode.INVALID_REQUEST

    async def test_delete_network_zone(self, session, test_user):
        """Test deleting a network zone."""
        scope = await network_topology_service.create_network_scope(
            session,
            user_id=test_user.id,
            scope_name="Test Scope",
            scope_type="enterprise",
        )

        zone = await network_topology_service.create_network_zone(
            session,
            scope_id=scope.id,
            zone_name="Test Zone",
            zone_type="local",
        )

        zone_id = zone.id

        await network_topology_service.delete_network_zone(session, zone_id=zone_id)

        # Verify zone is deleted
        with pytest.raises(DomainException) as exc_info:
            await network_topology_service.get_network_zone(session, zone_id=zone_id)

        assert exc_info.value.code == ErrorCode.INVALID_REQUEST
