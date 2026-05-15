"""Tests for TaskContext."""

import asyncio
import tempfile
import os

import pytest

from agentnet.session_store import SessionStore
from agentnet.task import TaskContext
from agentnet.types import TaskStatus


async def _noop_send(msg_type, payload):
    return "generated-message-id"


class TestTaskContext:
    def setup_method(self):
        self.tmp = tempfile.mktemp(suffix=".json")
        self.store = SessionStore(self.tmp)
        self.sent: list[tuple[str, dict]] = []

        async def capture_send(msg_type, payload):
            self.sent.append((msg_type, payload or {}))
            return "mid_" + msg_type

        self.send_fn = capture_send

    def teardown_method(self):
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    @pytest.mark.asyncio
    async def test_accept_sends_task_accepted(self):
        ctx = TaskContext("task-1", {"cmd": "test"}, self.store, self.send_fn)
        await ctx.accept()
        assert len(self.sent) == 1
        assert self.sent[0][0] == "task.accepted"
        assert self.sent[0][1]["task_id"] == "task-1"
        assert ctx.status == TaskStatus.RUNNING
        assert self.store.is_task_running("task-1")

    @pytest.mark.asyncio
    async def test_progress_sends_task_progress(self):
        ctx = TaskContext("task-2", {}, self.store, self.send_fn)
        await ctx.progress("Working", progress_pct=50)
        assert self.sent[0][0] == "task.progress"
        assert self.sent[0][1]["progress_pct"] == 50
        assert self.sent[0][1]["message"] == "Working"

    @pytest.mark.asyncio
    async def test_result_sends_and_cleans_up(self):
        ctx = TaskContext("task-3", {}, self.store, self.send_fn)
        self.store.add_running_task("task-3")
        await ctx.result({"output": "ok"})
        assert self.sent[0][0] == "task.result"
        assert self.sent[0][1]["result"] == {"output": "ok"}
        assert ctx.status == TaskStatus.COMPLETED
        assert not self.store.is_task_running("task-3")

    @pytest.mark.asyncio
    async def test_fail_sends_and_cleans_up(self):
        ctx = TaskContext("task-4", {}, self.store, self.send_fn)
        self.store.add_running_task("task-4")
        await ctx.fail("Something went wrong")
        assert self.sent[0][0] == "task.failed"
        assert self.sent[0][1]["error_message"] == "Something went wrong"
        assert ctx.status == TaskStatus.FAILED
        assert not self.store.is_task_running("task-4")

    @pytest.mark.asyncio
    async def test_request_approval_sets_awaiting_approval(self):
        ctx = TaskContext("task-5", {}, self.store, self.send_fn)
        await ctx.request_approval("shell", "rm -rf /", risk_level="high", reason="dangerous")
        assert self.sent[0][0] == "approval.request"
        assert self.sent[0][1]["risk_level"] == "high"
        assert self.sent[0][1]["action"]["kind"] == "shell"
        assert ctx.status == TaskStatus.AWAITING_APPROVAL
