"""Phase 6: Task Result / Progress / Approval tests."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.protocol.constants import ErrorCode, TaskStatus, DeliveryStatus
from app.exceptions import DomainException


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac





@pytest.fixture
async def api_key(client):
    resp = await client.post(
        "/v1/auth/register",
        json={"username": "phase6user", "key_name": "p6-key"},
    )
    assert resp.status_code == 200
    return resp.json()["api_key"]


@pytest.fixture
async def agent(client, api_key):
    resp = await client.post(
        "/v1/agents",
        json={"name": "Phase6 Agent", "runtime": "test"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def created_task(client, api_key, agent):
    resp = await client.post(
        "/v1/tasks",
        json={"assigned_to": agent["agent_number"], "payload": {"test": True}},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201
    return resp.json()


class TestTaskLifecycle:
    async def test_accept_task(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, get_task
        from app.database import SessionLocal

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            assert task.status == TaskStatus.ACCEPTED.value

    async def test_start_task(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, start_task, get_task
        from app.database import SessionLocal

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await start_task(session, task)
            assert task.status == TaskStatus.RUNNING.value
            assert task.lease_expires_at is not None

    async def test_record_progress(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, start_task, record_progress, get_task
        from app.database import SessionLocal

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await start_task(session, task)
            task = await record_progress(session, task, progress_pct=50, message="Half done")
            assert task.last_progress_at is not None

    async def test_complete_task(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, start_task, complete_task, get_task
        from app.database import SessionLocal

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await start_task(session, task)
            result_data = {"output": "hello", "status": "ok"}
            task = await complete_task(session, task, result=result_data)
            assert task.status == TaskStatus.COMPLETED.value
            assert task.result == result_data
            assert task.lease_expires_at is None

    async def test_fail_task(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, fail_task, get_task
        from app.database import SessionLocal

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await fail_task(session, task, error_message="Something broke")
            assert task.status == TaskStatus.FAILED.value
            assert task.error_message == "Something broke"

    async def test_complete_result_visible_via_api(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, start_task, complete_task, get_task
        from app.database import SessionLocal

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await start_task(session, task)
            await complete_task(session, task, result={"files": ["a.py", "b.py"]})

        # Fetch via REST
        resp = await client.get(f"/v1/tasks/{tid}", headers={"X-API-Key": api_key})
        assert resp.status_code == 200
        assert resp.json()["status"] == TaskStatus.COMPLETED.value
        assert resp.json()["result"] == {"files": ["a.py", "b.py"]}


class TestProgressHistory:
    async def test_progress_entries_created(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, start_task, record_progress, get_task
        from app.database import SessionLocal

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await start_task(session, task)
            task = await record_progress(session, task, progress_pct=25, message="Step 1")
            task = await record_progress(session, task, progress_pct=75, message="Step 2")

        resp = await client.get(f"/v1/tasks/{tid}/progress", headers={"X-API-Key": api_key})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["entries"][0]["progress_pct"] == 25
        assert data["entries"][1]["progress_pct"] == 75


class TestApprovalFlow:
    async def test_request_approval(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, start_task, request_approval, get_task
        from app.database import SessionLocal

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await start_task(session, task)
            task = await request_approval(
                session, task,
                risk_level="high",
                action_kind="shell_command",
                action_preview="rm -rf ./dist",
            )
            assert task.status == TaskStatus.AWAITING_APPROVAL.value

    async def test_approval_accepted_resumes_task(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, start_task, request_approval, get_task
        from app.services.approval_service import accept_approval
        from app.database import SessionLocal

        approval_id = None
        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await start_task(session, task)
            task = await request_approval(
                session, task, risk_level="high", action_kind="shell_command"
            )
            # Get the approval ID from the task
            from app.models.approval import Approval
            from sqlalchemy import select
            result = await session.execute(
                select(Approval).where(Approval.task_id == task.id)
            )
            approval = result.scalar_one()
            approval_id = approval.id

        async with SessionLocal() as session:
            await accept_approval(session, approval_id)
            task = await get_task(session, uuid.UUID(tid))
            assert task.status == TaskStatus.RUNNING.value

    async def test_approval_rejected_fails_task(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, start_task, request_approval, get_task
        from app.services.approval_service import reject_approval
        from app.database import SessionLocal

        approval_id = None
        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await start_task(session, task)
            task = await request_approval(
                session, task, risk_level="critical", action_kind="file_delete"
            )
            from app.models.approval import Approval
            from sqlalchemy import select
            result = await session.execute(
                select(Approval).where(Approval.task_id == task.id)
            )
            approval = result.scalar_one()
            approval_id = approval.id

        async with SessionLocal() as session:
            await reject_approval(session, approval_id)
            task = await get_task(session, uuid.UUID(tid))
            assert task.status == TaskStatus.REJECTED.value

    async def test_approval_expiry_fails_task(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, start_task, request_approval, get_task
        from app.database import SessionLocal

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await start_task(session, task)
            task = await request_approval(
                session, task, risk_level="medium", action_kind="network_request"
            )
            # Manually expire the approval
            from app.models.approval import Approval
            from sqlalchemy import select
            from datetime import UTC, datetime
            result = await session.execute(
                select(Approval).where(Approval.task_id == task.id)
            )
            approval = result.scalar_one()
            approval.expires_at = datetime.now(UTC)
            await session.commit()

        from app.services.approval_service import expire_stale_approvals
        await expire_stale_approvals()

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            assert task.status == TaskStatus.FAILED.value
            assert task.error_message == "Approval request expired"

    async def test_approvals_list_api(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, accept_task, start_task, request_approval, get_task
        from app.database import SessionLocal

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            task = await transition_state(session, task, "queued")
            task = await transition_state(session, task, "delivered")
            task = await accept_task(session, task)
            task = await start_task(session, task)
            await request_approval(
                session, task, risk_level="high", action_kind="shell_command"
            )

        resp = await client.get(
            f"/v1/approvals?task_id={tid}",
            headers={"X-API-Key": api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["approvals"][0]["risk_level"] == "high"


class TestStateTransitions:
    async def test_cannot_complete_non_running_task(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, complete_task, get_task
        from app.database import SessionLocal
        from app.exceptions import DomainException

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            with pytest.raises(DomainException) as exc_info:
                await complete_task(session, task)
            assert exc_info.value.code == ErrorCode.INVALID_TASK_STATE_TRANSITION.value

    async def test_cannot_progress_non_running_task(self, client, api_key, created_task):
        tid = created_task["task_id"]
        from app.services.task_service import transition_state, record_progress, get_task
        from app.database import SessionLocal
        from app.exceptions import DomainException

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            with pytest.raises(DomainException) as exc_info:
                await record_progress(session, task, progress_pct=50)
            assert exc_info.value.code == ErrorCode.INVALID_TASK_STATE_TRANSITION.value