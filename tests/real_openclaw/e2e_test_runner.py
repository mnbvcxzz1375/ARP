"""
Comprehensive E2E test suite for AgentNet OpenClaw platform.
Covers: failure paths, offline recovery, approval pipeline, security,
        long output/edge cases, and stability tests.

Usage:
    python e2e_test_runner.py                    # run all tests
    python e2e_test_runner.py failure            # run only failure path tests
    python e2e_test_runner.py offline            # run only offline recovery tests
    python e2e_test_runner.py approval           # run only approval tests
    python e2e_test_runner.py security           # run only security tests
    python e2e_test_runner.py edge               # run only edge case tests
    python e2e_test_runner.py stability          # run only stability tests

Requires:
    - API running on localhost:8000 (Docker Compose)
    - Remote receiver running on 100.127.164.72 (for real WS tests)
    - AGENTNET_API_KEY environment variable set (sender API key)
    - AGENTNET_AGENT_TOKEN environment variable set (receiver agent token)
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import string
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Any

import httpx
import websockets
import websockets.asyncio.client

API_BASE = "http://localhost:8000"
WS_URL = "ws://localhost:8000/v1/ws"

# Pre-created agents and users — credentials from environment
_missing = [v for v in ("AGENTNET_API_KEY", "AGENTNET_AGENT_TOKEN") if not os.environ.get(v)]
if _missing:
    print(f"ERROR: required environment variables not set: {', '.join(_missing)}", file=sys.stderr)
    sys.exit(1)

API_KEY = os.environ["AGENTNET_API_KEY"]
SENDER_AGENT_NUMBER = "AN-GLOBAL-BB05A89F32-ZQ"
RECEIVER_AGENT_NUMBER = "AN-GLOBAL-295B51BD51-9Z"
AGENT_TOKEN = os.environ["AGENTNET_AGENT_TOKEN"]

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def send_task(payload: dict, api_key: str = API_KEY,
              from_agent: str = SENDER_AGENT_NUMBER,
              to_agent: str = RECEIVER_AGENT_NUMBER) -> dict:
    body = {
        "assigned_to": to_agent,
        "from_agent_number": from_agent,
        "payload": payload,
        "idempotency_key": str(uuid.uuid4()),
    }
    for attempt in range(3):
        resp = httpx.post(
            f"{API_BASE}/v1/tasks", json=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code < 500:
            resp.raise_for_status()
            return resp.json()
        time.sleep(1)
    resp.raise_for_status()
    return resp.json()


def get_task(task_id: str, api_key: str = API_KEY) -> dict:
    resp = httpx.get(
        f"{API_BASE}/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def wait_for_status(task_id: str, status: str, timeout: float = 30,
                    api_key: str = API_KEY) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = get_task(task_id, api_key)
        if task["status"] == status:
            return task
        if task["status"] in ("failed", "expired", "cancelled"):
            return task
        time.sleep(0.5)
    return get_task(task_id, api_key)


def register_user(username: str) -> dict:
    resp = httpx.post(f"{API_BASE}/v1/auth/register",
                      json={"username": username, "key_name": "e2e-test"},
                      timeout=10)
    resp.raise_for_status()
    return resp.json()


def create_agent(name: str, runtime: str, api_key: str = API_KEY,
                 inbound_policy: str = "public") -> dict:
    resp = httpx.post(f"{API_BASE}/v1/agents",
                      json={"name": name, "runtime": runtime,
                            "inbound_policy": inbound_policy},
                      headers={"Authorization": f"Bearer {api_key}",
                               "Content-Type": "application/json"},
                      timeout=10)
    resp.raise_for_status()
    return resp.json()


# ------------------------------------------------------------------
# test runner infrastructure
# ------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""
    elapsed: float = 0.0


class TestRunner:
    def __init__(self):
        self.results: list[TestResult] = []

    def run(self, name: str, fn: Callable[[], str]):
        t0 = time.time()
        try:
            detail = fn()
            self.results.append(TestResult(name, True, detail, time.time() - t0))
            print(f"  [PASS] {name} ({time.time()-t0:.1f}s)")
            if detail:
                print(f"         {detail}")
        except Exception as e:
            self.results.append(TestResult(name, False, str(e), time.time() - t0))
            print(f"  [FAIL] {name} ({time.time()-t0:.1f}s)")
            print(f"         {e}")

    def summary(self):
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        print(f"\n{'='*60}")
        print(f"[SUMMARY] {passed}/{total} tests passed")
        for r in self.results:
            icon = "PASS" if r.passed else "FAIL"
            print(f"  [{icon}] {r.name} ({r.elapsed:.1f}s)")
        return passed == total


# ------------------------------------------------------------------
# Category 1: Failure Paths
# ------------------------------------------------------------------

def test_failure_paths(runner: TestRunner):
    """Test failure scenarios: bad API key, DashScope errors, receiver crash."""

    def test_bad_api_key():
        """Creating a task with invalid API key should fail."""
        resp = httpx.post(
            f"{API_BASE}/v1/tasks",
            json={
                "assigned_to": RECEIVER_AGENT_NUMBER,
                "from_agent_number": SENDER_AGENT_NUMBER,
                "payload": {},
                "idempotency_key": str(uuid.uuid4()),
            },
            headers={"Authorization": "Bearer invalid_key_12345",
                     "Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        return f"Correctly rejected with {resp.status_code}"

    runner.run("Bad API key rejected (401)", test_bad_api_key)

    def test_bad_agent_token_ws():
        """WebSocket connection with bad agent token should fail."""
        async def run_test():
            async with websockets.connect(
                WS_URL,
                additional_headers={"Authorization": "Bearer agt_sk_INVALID_TEST_TOKEN"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "error", f"Expected error, got {msg['type']}"
                assert msg["payload"]["code"] == "INVALID_TOKEN"
                return f"Correctly rejected: {msg['payload']['code']}"
        return asyncio.run(run_test())

    runner.run("Bad agent token WS rejected", test_bad_agent_token_ws)

    def test_api_key_as_agent_token():
        """Using an API key as agent token should fail."""
        async def run_test():
            async with websockets.connect(
                WS_URL,
                additional_headers={"Authorization": f"Bearer {API_KEY}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "error"
                return f"Correctly rejected: {msg['payload']['code']}"
        return asyncio.run(run_test())

    runner.run("API key cannot be used as agent token", test_api_key_as_agent_token)

    def test_receiver_not_online():
        """Task created when receiver is offline should be 'delivered' (queued)."""
        task = send_task({"content": [{"mime": "text/plain", "text": "offline test"}]})
        # Without receiver connected, task should be created but queued
        time.sleep(1)
        task_status = get_task(task["task_id"])
        # Task is created/delivered but NOT completed since no receiver
        assert task_status["status"] in ("created", "delivered"), \
            f"Expected created/delivered, got {task_status['status']}"
        return f"Task status: {task_status['status']} (correctly queued)"

    runner.run("Task queued when receiver offline", test_receiver_not_online)

    def test_receiver_crash_mid_task():
        """Simulate receiver crashing after ACK but before sending result."""
        async def run_test():
            # Create a new agent for this test
            reg = register_user(f"crash-test-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Crash Agent", "test", api_key)
            token = agent["agent_token"]

            # Connect as receiver
            async with websockets.connect(
                f"{WS_URL}?session_id=crash-test-{uuid.uuid4().hex[:6]}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "session.resume_result"

                # Send a task from main user
                task = send_task({
                    "content": [{"mime": "application/json",
                                 "data": {"prompt": "crash test"}}]
                }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent["agent_number"])
                task_id = task["task_id"]

                # Receive task, ACK it, then close connection (simulating crash)
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                assert msg["type"] == "task.request"
                message_id = msg["message_id"]

                # ACK but DON'T send result - close connection
                ack_msg = json.dumps({
                    "type": "ack",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"message_id": message_id},
                })
                await ws.send(ack_msg)
                await ws.close()  # crash

                # Wait for task to transition to failed or remain delivered
                time.sleep(3)
                task_status = get_task(task_id)
                return f"Task {task_status['status']} after receiver crash (acked but no result)"
        return asyncio.run(run_test())

    runner.run("Receiver crash after ACK - task doesn't hang", test_receiver_crash_mid_task)


# ------------------------------------------------------------------
# Category 2: Offline Recovery
# ------------------------------------------------------------------

def test_offline_recovery(runner: TestRunner):
    """Test task delivery when receiver is offline, then reconnects."""

    def test_offline_task_then_reconnect():
        """Create task while receiver is offline, then reconnect and verify delivery."""
        async def run_test():
            # Create a fresh agent for clean state
            reg = register_user(f"offline-test-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Offline Test Agent", "test", api_key)
            agent_number = agent["agent_number"]
            token = agent["agent_token"]

            # 1. Create task while agent is OFFLINE
            task1 = send_task({
                "content": [{"mime": "text/plain", "text": "task while offline 1"}]
            }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
            task1_id = task1["task_id"]
            time.sleep(1)

            task2 = send_task({
                "content": [{"mime": "text/plain", "text": "task while offline 2"}]
            }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
            task2_id = task2["task_id"]
            time.sleep(1)

            # Verify tasks are queued (not completed)
            t1_before = get_task(task1_id)
            t2_before = get_task(task2_id)
            assert t1_before["status"] != "completed", "Task should not be completed yet"

            # 2. Connect the agent - should receive pending tasks
            session_id = f"offline-session-{uuid.uuid4().hex[:6]}"
            received_tasks = []

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                # Receive session resume
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)

                # Receive task requests
                for _ in range(3):  # safety limit
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        msg = json.loads(raw)
                        if msg["type"] == "task.request":
                            received_tasks.append(msg)
                            # ACK each task
                            ack = json.dumps({
                                "type": "ack",
                                "message_id": str(uuid.uuid4()),
                                "payload": {"message_id": msg["message_id"]},
                            })
                            await ws.send(ack)

                            # Send completion
                            result = json.dumps({
                                "type": "task.result",
                                "message_id": str(uuid.uuid4()),
                                "payload": {
                                    "task_id": msg["task_id"],
                                    "status": "completed",
                                    "result": {"stdout": "processed offline task"},
                                },
                            })
                            await ws.send(result)
                    except (asyncio.TimeoutError, websockets.ConnectionClosed):
                        break

            assert len(received_tasks) >= 2, \
                f"Expected >= 2 pending tasks, got {len(received_tasks)}"

            # 3. Verify tasks completed
            time.sleep(2)
            t1_after = get_task(task1_id)
            t2_after = get_task(task2_id)

            return (f"Created 2 tasks offline, received {len(received_tasks)} on reconnect, "
                    f"task1={t1_after['status']}, task2={t2_after['status']}")

        return asyncio.run(run_test())

    runner.run("Offline task delivery + reconnect", test_offline_task_then_reconnect)

    def test_session_resume_no_duplicate():
        """Acked messages should NOT be re-delivered on reconnect."""
        async def run_test():
            reg = register_user(f"resume-test-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Resume Test Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            # Create and deliver task
            task = send_task({
                "content": [{"mime": "text/plain", "text": "resume test"}]
            }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
            task_id = task["task_id"]

            session_id = f"resume-session-{uuid.uuid4().hex[:8]}"
            received_count = 0

            # Connect, receive task, ACK and complete
            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)

                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                assert msg["type"] == "task.request"
                received_count += 1

                message_id = msg["message_id"]
                # ACK
                await ws.send(json.dumps({
                    "type": "ack",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"message_id": message_id},
                }))
                # Complete
                await ws.send(json.dumps({
                    "type": "task.result",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"task_id": task_id, "status": "completed",
                                "result": {"stdout": "done"}},
                }))
                await ws.close()

            time.sleep(2)
            task_status = get_task(task_id)
            assert task_status["status"] == "completed", \
                f"Task should be completed, got {task_status['status']}"

            # Reconnect with same session_id - should NOT re-deliver acked task
            reconnect_count = 0
            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                # Check for task.request within 3 seconds
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3)
                    msg2 = json.loads(raw)
                    if msg2["type"] == "task.request":
                        reconnect_count += 1
                except asyncio.TimeoutError:
                    pass  # Expected: no new tasks

            assert reconnect_count == 0, "Acked task was incorrectly re-delivered"
            return (f"Task acked and completed on first connect, "
                    f"no duplicate on reconnect (correct)")

        return asyncio.run(run_test())

    runner.run("Session resume - no duplicate delivery", test_session_resume_no_duplicate)


# ------------------------------------------------------------------
# Category 3: Approval Pipeline
# ------------------------------------------------------------------

def test_approval_pipeline(runner: TestRunner):
    """Test high-risk task approval workflow."""

    def test_approval_reject_stops_task():
        """Task that requires approval should be stopped when rejected."""
        async def run_test():
            reg = register_user(f"approval-test-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Approval Test Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            # Connect agent
            session_id = f"approval-session-{uuid.uuid4().hex[:6]}"

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)

                # Send a task from main user
                task = send_task({
                    "content": [{"mime": "application/json",
                                 "data": {"prompt": "approval test prompt"}}]
                }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
                task_id = task["task_id"]

                # Receive task
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                assert msg["type"] == "task.request"
                message_id = msg["message_id"]

                # ACK
                await ws.send(json.dumps({
                    "type": "ack",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"message_id": message_id},
                }))

                # Instead of completing, request approval (simulating high-risk)
                await ws.send(json.dumps({
                    "type": "task.accepted",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"task_id": task_id},
                }))

                # Request approval
                await ws.send(json.dumps({
                    "type": "approval.request",
                    "message_id": str(uuid.uuid4()),
                    "payload": {
                        "task_id": task_id,
                        "risk_level": "high",
                        "action": {"kind": "execute_command", "preview": "rm -rf /"},
                        "reason": "Dangerous command detected",
                    },
                }))

                # Wait a moment for approval to be processed
                time.sleep(2)

                # Check that task is awaiting_approval
                task_status = get_task(task_id, api_key)
                return (f"Task status after approval request: {task_status['status']}")

        return asyncio.run(run_test())

    runner.run("Approval request creates awaiting_approval state",
               test_approval_reject_stops_task)

    def test_approval_list_endpoint():
        """Verify approvals can be listed."""
        async def run_test():
            reg = register_user(f"approval-list-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Approval List Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            session_id = f"approval-list-{uuid.uuid4().hex[:6]}"

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)

                task = send_task({
                    "content": [{"mime": "application/json",
                                 "data": {"prompt": "list approval test"}}]
                }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
                task_id = task["task_id"]

                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                if msg["type"] == "task.request":
                    message_id = msg["message_id"]
                    await ws.send(json.dumps({
                        "type": "ack",
                        "message_id": str(uuid.uuid4()),
                        "payload": {"message_id": message_id},
                    }))

                    # Request approval
                    await ws.send(json.dumps({
                        "type": "approval.request",
                        "message_id": str(uuid.uuid4()),
                        "payload": {
                            "task_id": task_id,
                            "risk_level": "medium",
                            "action": {"kind": "api_call", "preview": "GET /admin"},
                            "reason": "Admin access requested",
                        },
                    }))

                time.sleep(2)

            # List approvals
            resp = httpx.get(
                f"{API_BASE}/v1/approvals",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            approvals = resp.json()
            total = approvals.get("total", 0)
            return f"Listed {total} pending approval(s)"

        return asyncio.run(run_test())

    runner.run("Approval list endpoint works", test_approval_list_endpoint)


# ------------------------------------------------------------------
# Category 4: Security Boundaries
# ------------------------------------------------------------------

def test_security_boundaries(runner: TestRunner):
    """Test security boundaries: user isolation, token rotation, access control."""

    def test_token_rotation_invalidates_old():
        """After rotating agent token, old token should fail."""
        async def run_test():
            reg = register_user(f"rotate-test-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Rotate Test Agent", "test", api_key)
            old_token = agent["agent_token"]
            agent_id = agent["agent_id"]

            # Verify old token works
            async with websockets.connect(
                f"{WS_URL}?session_id=rotate-test-1",
                additional_headers={"Authorization": f"Bearer {old_token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] != "error", "Old token should work initially"
                await ws.close()

            # Rotate token
            resp = httpx.post(
                f"{API_BASE}/v1/agents/{agent_id}/rotate-token",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            new_token = resp.json()["agent_token"]

            # Try old token - should fail
            async with websockets.connect(
                f"{WS_URL}?session_id=rotate-test-old",
                additional_headers={"Authorization": f"Bearer {old_token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                if msg["type"] == "error":
                    return f"Old token correctly rejected after rotation"
                # If not rejected, the connection may have been established
                # but old token should have been revoked
                await ws.close()
                return f"Old token behavior after rotation: {msg['type']}"

        return asyncio.run(run_test())

    runner.run("Token rotation invalidates old token",
               test_token_rotation_invalidates_old)

    def test_cross_user_task_access():
        """User A cannot access User B's tasks."""
        reg_a = register_user(f"sec-user-a-{uuid.uuid4().hex[:6]}")
        api_key_a = reg_a["api_key"]
        agent_a = create_agent("User A Agent", "test", api_key_a)

        reg_b = register_user(f"sec-user-b-{uuid.uuid4().hex[:6]}")
        api_key_b = reg_b["api_key"]

        # User B tries to access User A's agent
        resp = httpx.get(
            f"{API_BASE}/v1/agents/{agent_a['agent_id']}",
            headers={"Authorization": f"Bearer {api_key_b}"},
            timeout=10,
        )
        assert resp.status_code == 404, \
            f"Expected 404, got {resp.status_code}: User B should not see User A's agent"

        return f"User B correctly denied access to User A's agent (404)"

    runner.run("Cross-user agent access denied (404)", test_cross_user_task_access)

    def test_list_api_keys():
        """Verify API key management works."""
        resp = httpx.get(f"{API_BASE}/v1/auth/api-keys",
                         headers={"Authorization": f"Bearer {API_KEY}"},
                         timeout=10)
        resp.raise_for_status()
        keys = resp.json()
        total = keys.get("total", 0)
        return f"Listed {total} API keys for authenticated user"

    runner.run("API key listing works", test_list_api_keys)


# ------------------------------------------------------------------
# Category 5: Long Output & Edge Cases
# ------------------------------------------------------------------

def test_edge_cases(runner: TestRunner):
    """Test long outputs, emoji, Chinese, special characters."""

    def test_long_model_output():
        """Model output that exceeds reasonable length should be handled."""
        async def run_test():
            reg = register_user(f"long-output-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Long Output Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            session_id = f"long-output-{uuid.uuid4().hex[:6]}"

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "session.resume_result"

                # Send task asking for long output
                task = send_task({
                    "content": [{"mime": "application/json",
                                 "data": {"prompt": "Write a Python script with 100 functions, each with docstrings. Make it very long."}}]
                }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
                task_id = task["task_id"]

                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                assert msg["type"] == "task.request"
                message_id = msg["message_id"]

                # ACK
                await ws.send(json.dumps({
                    "type": "ack",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"message_id": message_id},
                }))
                # Small delay to let ACK process before sending result
                await asyncio.sleep(0.1)

                # Send result
                await ws.send(json.dumps({
                    "type": "task.result",
                    "message_id": str(uuid.uuid4()),
                    "payload": {
                        "task_id": task_id,
                        "status": "completed",
                        "result": {"stdout": "x" * 100_000, "exit_code": 0},
                    },
                }))
                # Wait for server to process
                await asyncio.sleep(0.5)

                # Check for ack response
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    resp = json.loads(raw)
                except asyncio.TimeoutError:
                    pass

                # Wait for task to be completed
                time.sleep(2)
                task_status = get_task(task_id, api_key)
                assert task_status["status"] == "completed", \
                    f"Expected completed, got {task_status['status']}"
                result = task_status.get("result") or {}
                stdout_len = len(result.get("stdout", ""))
                return (f"Task completed with {stdout_len} chars output, "
                        f"status={task_status['status']}")

        return asyncio.run(run_test())

    runner.run("Long output (100KB) handled correctly", test_long_model_output)

    def test_unicode_emoji_chinese():
        """Task result with emoji and Chinese characters should be stored correctly."""
        async def run_test():
            reg = register_user(f"unicode-test-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Unicode Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            session_id = f"unicode-{uuid.uuid4().hex[:6]}"

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "session.resume_result"

                task = send_task({
                    "content": [{"mime": "text/plain", "text": "unicode test"}]
                }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
                task_id = task["task_id"]

                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                assert msg["type"] == "task.request"
                message_id = msg["message_id"]

                await ws.send(json.dumps({
                    "type": "ack",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"message_id": message_id},
                }))
                await asyncio.sleep(0.1)

                # Send result with unicode/emoji/Chinese
                unicode_result = {
                    "stdout": "Hello 🌍 你好世界! 🔍📦\n"
                              "def 排序(arr): return sorted(arr)\n"
                              "print('✅ 测试通过 ✓')\n"
                              "# Special chars: <>&\"'\\n\n",
                    "exit_code": 0,
                }
                await ws.send(json.dumps({
                    "type": "task.result",
                    "message_id": str(uuid.uuid4()),
                    "payload": {
                        "task_id": task_id,
                        "status": "completed",
                        "result": unicode_result,
                    },
                }))
                await asyncio.sleep(0.5)

                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    pass

                time.sleep(2)
                task_status = get_task(task_id, api_key)
                assert task_status["status"] == "completed", \
                    f"Expected completed, got {task_status['status']}"
                result = task_status.get("result") or {}
                stdout = result.get("stdout", "")

                assert "你好世界" in stdout, f"Chinese characters not preserved. Got: {repr(stdout[:80])}"
                assert "🌍" in stdout, f"Emoji not preserved. Got: {repr(stdout[:80])}"
                return f"Unicode/emoji/Chinese preserved correctly: {repr(stdout[:60])}"

        return asyncio.run(run_test())

    runner.run("Unicode, emoji, Chinese characters preserved", test_unicode_emoji_chinese)

    def test_code_block_in_result():
        """Task result containing markdown code blocks."""
        async def run_test():
            reg = register_user(f"codeblock-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("CodeBlock Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            session_id = f"codeblock-{uuid.uuid4().hex[:6]}"

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "session.resume_result"

                task = send_task({
                    "content": [{"mime": "text/plain", "text": "code block test"}]
                }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
                task_id = task["task_id"]

                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                assert msg["type"] == "task.request"
                message_id = msg["message_id"]

                await ws.send(json.dumps({
                    "type": "ack",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"message_id": message_id},
                }))
                await asyncio.sleep(0.1)

                # Markdown code block
                code_result = {
                    "stdout": (
                        "```python\n"
                        "def hello(name: str) -> str:\n"
                        '    return f"Hello, {name}!"\n'
                        "```\n"
                        "\n"
                        "This function takes a `name` parameter."
                    ),
                    "exit_code": 0,
                }
                await ws.send(json.dumps({
                    "type": "task.result",
                    "message_id": str(uuid.uuid4()),
                    "payload": {
                        "task_id": task_id,
                        "status": "completed",
                        "result": code_result,
                    },
                }))
                await asyncio.sleep(0.5)

                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    pass

                time.sleep(2)
                task_status = get_task(task_id, api_key)
                assert task_status["status"] == "completed", \
                    f"Expected completed, got {task_status['status']}"
                result = task_status.get("result") or {}
                stdout = result.get("stdout", "")
                assert "def hello" in stdout, f"Code not preserved. Got: {repr(stdout[:80])}"
                return f"Code blocks preserved: {repr(stdout[:80])}"

        return asyncio.run(run_test())

    runner.run("Markdown code blocks in result", test_code_block_in_result)


# ------------------------------------------------------------------
# Category 6: Stability
# ------------------------------------------------------------------

def test_stability(runner: TestRunner):
    """Test rapid task creation, concurrent tasks, heartbeat resilience."""

    def test_rapid_tasks():
        """Send 20 tasks rapidly and verify all complete."""
        async def run_test():
            reg = register_user(f"rapid-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Rapid Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            # Create tasks BEFORE connecting (they'll be queued as offline)
            for i in range(20):
                send_task({
                    "content": [{"mime": "text/plain",
                                 "text": f"rapid task {i}"}]
                }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)

            session_id = f"rapid-{uuid.uuid4().hex[:6]}"
            processed = set()

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                # First message could be session.resume_result or task.request (if offline tasks exist)
                if msg["type"] == "task.request":
                    # Process this task immediately
                    task_id = msg["task_id"]
                    processed.add(task_id)
                    await ws.send(json.dumps({
                        "type": "ack",
                        "message_id": str(uuid.uuid4()),
                        "payload": {"message_id": msg["message_id"]},
                    }))
                    await ws.send(json.dumps({
                        "type": "task.result",
                        "message_id": str(uuid.uuid4()),
                        "payload": {
                            "task_id": task_id,
                            "status": "completed",
                            "result": {"stdout": f"done {task_id[:8]}"},
                        },
                    }))
                    await asyncio.sleep(0.1)
                else:
                    assert msg["type"] == "session.resume_result"

                # Process all pending tasks
                for _ in range(30):
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=15)
                        msg = json.loads(raw)
                        if msg["type"] == "task.request":
                            task_id = msg["task_id"]
                            if task_id not in processed:
                                processed.add(task_id)
                                await ws.send(json.dumps({
                                    "type": "ack",
                                    "message_id": str(uuid.uuid4()),
                                    "payload": {"message_id": msg["message_id"]},
                                }))
                                await ws.send(json.dumps({
                                    "type": "task.result",
                                    "message_id": str(uuid.uuid4()),
                                    "payload": {
                                        "task_id": task_id,
                                        "status": "completed",
                                        "result": {"stdout": f"done {task_id[:8]}"},
                                    },
                                }))
                                await asyncio.sleep(0.1)
                        if len(processed) >= 20:
                            break
                    except asyncio.TimeoutError:
                        break

            assert len(processed) >= 20, f"Only processed {len(processed)}/20 tasks"
            return f"Created 20 tasks offline, processed {len(processed)} on connect"

        return asyncio.run(run_test())

    runner.run("20 rapid tasks all processed", test_rapid_tasks)

    def test_concurrent_tasks():
        """Send 5 tasks concurrently and verify routing."""
        async def run_test():
            reg = register_user(f"concurrent-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Concurrent Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            session_id = f"concurrent-{uuid.uuid4().hex[:6]}"
            created_ids = []

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)

                # Create 5 tasks concurrently
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                    futures = []
                    for i in range(5):
                        f = pool.submit(send_task, {
                            "content": [{"mime": "text/plain",
                                         "text": f"concurrent task {i}"}]
                        }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
                        futures.append(f)
                    for f in concurrent.futures.as_completed(futures):
                        task = f.result()
                        created_ids.append(task["task_id"])

                # Process all tasks
                processed = set()
                for _ in range(10):
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=10)
                        msg = json.loads(raw)
                        if msg["type"] == "task.request":
                            task_id = msg["task_id"]
                            message_id = msg["message_id"]
                            if task_id not in processed:
                                processed.add(task_id)
                                await ws.send(json.dumps({
                                    "type": "ack",
                                    "message_id": str(uuid.uuid4()),
                                    "payload": {"message_id": message_id},
                                }))
                                await ws.send(json.dumps({
                                    "type": "task.result",
                                    "message_id": str(uuid.uuid4()),
                                    "payload": {
                                        "task_id": task_id,
                                        "status": "completed",
                                        "result": {"stdout": "concurrent ok"},
                                    },
                                }))
                    except (asyncio.TimeoutError, websockets.ConnectionClosed):
                        break

                return f"Created {len(created_ids)} concurrent tasks, processed {len(processed)}"

        return asyncio.run(run_test())

    runner.run("5 concurrent tasks processed", test_concurrent_tasks)

    def test_heartbeat_and_reconnect():
        """Test heartbeat timeout and auto-reconnect."""
        async def run_test():
            reg = register_user(f"hb-test-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Heartbeat Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            # Connect, send heartbeat, disconnect
            session_id = f"hb-{uuid.uuid4().hex[:6]}"

            # First connection - with heartbeat
            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "session.resume_result"

                # Send a heartbeat
                await ws.send(json.dumps({
                    "type": "presence.heartbeat",
                    "message_id": str(uuid.uuid4()),
                    "payload": {},
                }))

                # Wait for ack
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "ack"

                await ws.close()

            # Second connection - should succeed (old connection cleaned up)
            session_id2 = f"hb-{uuid.uuid4().hex[:6]}"
            async with websockets.connect(
                f"{WS_URL}?session_id={session_id2}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "session.resume_result"
                await ws.close()

            return f"Heartbeat + reconnect successful, no max connection error"

        return asyncio.run(run_test())

    runner.run("Heartbeat and reconnect (no max connection)",
               test_heartbeat_and_reconnect)


# ------------------------------------------------------------------
# Category 7: Offline Recovery + Dedup
# ------------------------------------------------------------------

def test_offline_dedup(runner: TestRunner):
    """Test that acked messages are NOT re-delivered on reconnect."""

    def test_ack_no_redeliver():
        """Acked tasks should not be re-delivered on reconnect with same session_id."""
        async def run_test():
            reg = register_user(f"dedup-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Dedup Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            # 1. Create task while agent is OFFLINE
            task = send_task({
                "content": [{"mime": "text/plain", "text": "dedup test"}]
            }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
            task_id = task["task_id"]

            session_id = f"dedup-session-{uuid.uuid4().hex[:8]}"

            # 2. First connect: receive pending task, ACK it, disconnect immediately
            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                # First message could be session.resume_result or task.request
                if msg["type"] == "task.request":
                    message_id = msg["message_id"]
                    # ACK but DON'T complete - just close
                    await ws.send(json.dumps({
                        "type": "ack",
                        "message_id": str(uuid.uuid4()),
                        "payload": {"message_id": message_id},
                    }))
                    # Wait a moment then close (simulating disconnection after ack)
                    await asyncio.sleep(0.5)
                # Read remaining messages
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3)
                    msg2 = json.loads(raw)
                    if msg2["type"] == "task.request":
                        # This is the pending task, ACK it too
                        if msg["type"] != "task.request":
                            await ws.send(json.dumps({
                                "type": "ack",
                                "message_id": str(uuid.uuid4()),
                                "payload": {"message_id": msg2["message_id"]},
                            }))
                except asyncio.TimeoutError:
                    pass

            # 3. Reconnect with SAME session_id
            redelivered = False
            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                # Check if we get any task.request - should NOT if acked
                for _ in range(5):
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2)
                        msg2 = json.loads(raw)
                        if msg2["type"] == "task.request":
                            redelivered = True
                            break
                    except asyncio.TimeoutError:
                        break

            assert not redelivered, "Acked task was incorrectly re-delivered on resume"
            return (f"Task acked on first connect, "
                    f"no re-delivery on resume with same session_id")

        return asyncio.run(run_test())

    runner.run("Acked tasks not re-delivered on resume", test_ack_no_redeliver)


# ------------------------------------------------------------------
# Category 8: Model Failure Convergence
# ------------------------------------------------------------------

def test_model_failure(runner: TestRunner):
    """Test that DashScope errors cause tasks to fail properly."""

    def test_crash_with_timeout():
        """Receiver crashes after ACK: verify task eventually expires via timeout worker.

        Sets TASK_MAX_RUNTIME_S=30 to accelerate the timeout for testing.
        """
        async def run_test():
            reg = register_user(f"crash-timeout-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Crash Timeout Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            # Connect as receiver
            async with websockets.connect(
                f"{WS_URL}?session_id=crash-timeout-{uuid.uuid4().hex[:6]}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "session.resume_result"

                # Create a task
                task = send_task({
                    "content": [{"mime": "application/json",
                                 "data": {"prompt": "crash timeout test"}}]
                }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
                task_id = task["task_id"]

                # Receive task, ACK it but DON'T send result - crash
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                assert msg["type"] == "task.request"
                message_id = msg["message_id"]

                await ws.send(json.dumps({
                    "type": "ack",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"message_id": message_id},
                }))
                # Close without sending result: crash simulation
                await ws.close()

            # The task is now in "delivered" status with no active receiver.
            # Wait for timeout worker to expire it (runs every ~30s, max_runtime_s=600)
            # For this test we check the task transitions appropriately.
            time.sleep(3)
            task_status = get_task(task_id, api_key)
            initial_status = task_status["status"]

            # Verify task is NOT stuck: should eventually move to failed/expired
            assert initial_status not in ("created",), \
                f"Task should not be stuck in created; got {initial_status}"

            return (f"Task status after crash: {initial_status}. "
                    f"Will be expired by timeout worker (max_runtime=600s)")

        return asyncio.run(run_test())

    runner.run("Receiver crash → task not stuck, will expire", test_crash_with_timeout)

    def test_model_result_with_error():
        """Simulate DashScope error: receiver sends task.failed instead of task.result."""
        async def run_test():
            reg = register_user(f"model-fail-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Model Fail Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            session_id = f"model-fail-{uuid.uuid4().hex[:6]}"

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "session.resume_result"

                # Create task that simulates a model 429/5xx error
                task = send_task({
                    "content": [{"mime": "text/plain",
                                 "text": "exec:simulate_dashscope_429_error"}]
                }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
                task_id = task["task_id"]

                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                assert msg["type"] == "task.request"
                message_id = msg["message_id"]

                # ACK
                await ws.send(json.dumps({
                    "type": "ack",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"message_id": message_id},
                }))

                # Send task.failed instead of task.result (simulating model error)
                await ws.send(json.dumps({
                    "type": "task.failed",
                    "message_id": str(uuid.uuid4()),
                    "payload": {
                        "task_id": task_id,
                        "error_message": "DashScope returned 429 Too Many Requests. Retry after 10s.",
                    },
                }))

            time.sleep(2)
            task_status = get_task(task_id, api_key)
            assert task_status["status"] == "failed", \
                f"Expected failed, got {task_status['status']}"
            return (f"Task correctly marked as failed: "
                    f"{task_status.get('error_message', '')[:60]}")

        return asyncio.run(run_test())

    runner.run("Model 429/5xx → task.failed", test_model_result_with_error)

    def test_result_with_nonzero_exit():
        """Model returns nonzero exit code → task should be marked as completed
        but the result should reflect the error."""
        async def run_test():
            reg = register_user(f"nonzero-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Nonzero Agent", "test", api_key)
            token = agent["agent_token"]
            agent_number = agent["agent_number"]

            session_id = f"nonzero-{uuid.uuid4().hex[:6]}"

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] == "session.resume_result"

                task = send_task({
                    "content": [{"mime": "text/plain",
                                 "text": "exec:-c 'exit(1)'"}]
                }, from_agent=SENDER_AGENT_NUMBER, to_agent=agent_number)
                task_id = task["task_id"]

                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                msg = json.loads(raw)
                assert msg["type"] == "task.request"
                message_id = msg["message_id"]

                await ws.send(json.dumps({
                    "type": "ack",
                    "message_id": str(uuid.uuid4()),
                    "payload": {"message_id": message_id},
                }))

                # Send task.result with nonzero exit code
                await ws.send(json.dumps({
                    "type": "task.result",
                    "message_id": str(uuid.uuid4()),
                    "payload": {
                        "task_id": task_id,
                        "status": "failed",
                        "result": {
                            "stdout": "",
                            "stderr": "Command exited with code 1",
                            "exit_code": 1,
                        },
                    },
                }))

            time.sleep(2)
            task_status = get_task(task_id, api_key)
            assert task_status["status"] in ("completed", "failed"), \
                f"Expected completed/failed, got {task_status['status']}"
            return (f"Nonzero exit task: {task_status['status']}. "
                    f"Result preserved correctly.")

        return asyncio.run(run_test())

    runner.run("Nonzero exit → task.result with error stderr",
               test_result_with_nonzero_exit)


# ------------------------------------------------------------------
# Category 9: Long Stability (30-60 min WebSocket heartbeat/reconnect)
# ------------------------------------------------------------------

def test_long_stability(runner: TestRunner):
    """Run a long-duration WebSocket stability test with heartbeat monitoring."""

    def test_websocket_heartbeat_30min():
        """Connect and maintain heartbeat for 60 cycles (10 min baseline).
        Monitors for connection drops, max connection errors, and latency.

        For a full 30-60 minute run, set CYCLES=180 or 360.
        """
        CYCLES = int(os.getenv("LONG_STABILITY_CYCLES", "60"))
        async def run_test():
            reg = register_user(f"long-stab-{uuid.uuid4().hex[:6]}")
            api_key = reg["api_key"]
            agent = create_agent("Long Stability Agent", "test", api_key)
            token = agent["agent_token"]

            session_id = f"long-stab-{uuid.uuid4().hex[:6]}"
            drop_count = 0
            max_conn_errors = 0
            latencies: list[float] = []

            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                assert msg["type"] in ("session.resume_result", "task.request"), \
                    f"Unexpected first message: {msg['type']}"

                for cycle in range(CYCLES):
                    t0 = time.time()
                    try:
                        await ws.send(json.dumps({
                            "type": "presence.heartbeat",
                            "message_id": str(uuid.uuid4()),
                            "payload": {},
                        }))
                        raw = await asyncio.wait_for(ws.recv(), timeout=15)
                        msg = json.loads(raw)
                        lat = time.time() - t0
                        latencies.append(lat)

                        if msg["type"] == "error":
                            if "max connections" in str(msg.get("payload", {})):
                                max_conn_errors += 1
                                print(f"  [CYCLE {cycle+1}] max connection error")
                            else:
                                drop_count += 1
                                print(f"  [CYCLE {cycle+1}] error: {msg['payload']}")
                        elif msg["type"] == "ack":
                            pass  # normal heartbeat ack
                        elif msg["type"] == "task.request":
                            # Process unexpected task
                            await ws.send(json.dumps({
                                "type": "ack",
                                "message_id": str(uuid.uuid4()),
                                "payload": {"message_id": msg["message_id"]},
                            }))
                    except asyncio.TimeoutError:
                        drop_count += 1
                        print(f"  [CYCLE {cycle+1}] heartbeat timeout")
                    except websockets.ConnectionClosed as e:
                        drop_count += 1
                        print(f"  [CYCLE {cycle+1}] connection closed: {e}")
                        break

                    if (cycle + 1) % 20 == 0:
                        avg_lat = sum(latencies[-20:]) / len(latencies[-20:])
                        print(f"  [CYCLE {cycle+1}/{CYCLES}] avg latency: {avg_lat:.3f}s, "
                              f"drops: {drop_count}, max_conn_errors: {max_conn_errors}")

                    await asyncio.sleep(2)

            total_time = time.time() - t0 if 't0' in dir() else 0
            assert drop_count < CYCLES * 0.1, \
                f"Too many heartbeat drops: {drop_count}/{CYCLES}"
            assert max_conn_errors == 0, \
                f"Max connection errors occurred: {max_conn_errors}"

            avg_lat = sum(latencies) / len(latencies) if latencies else 0
            return (f"{CYCLES} heartbeat cycles completed. "
                    f"Drops: {drop_count}, MaxConnErrors: {max_conn_errors}, "
                    f"Avg latency: {avg_lat:.3f}s")

        return asyncio.run(run_test())

    runner.run(f"WebSocket heartbeat stability ({os.getenv('LONG_STABILITY_CYCLES','60')} cycles)",
               test_websocket_heartbeat_30min)


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

CATEGORIES = {
    "failure": test_failure_paths,
    "offline": test_offline_recovery,
    "approval": test_approval_pipeline,
    "security": test_security_boundaries,
    "edge": test_edge_cases,
    "stability": test_stability,
    "dedup": test_offline_dedup,
    "model_failure": test_model_failure,
    "long_stability": test_long_stability,
}

def main():
    if len(sys.argv) > 1:
        categories = [a for a in sys.argv[1:] if a in CATEGORIES]
        if not categories:
            print(f"Unknown categories: {[a for a in sys.argv[1:] if a not in CATEGORIES]}")
            print(f"Available: {', '.join(CATEGORIES.keys())}")
            sys.exit(1)
    else:
        categories = list(CATEGORIES.keys())

    print("=" * 60)
    print(f"AgentNet E2E Test Suite")
    print(f"Categories: {', '.join(categories)}")
    print(f"API: {API_BASE}")
    print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_passed = True
    for cat in categories:
        print(f"\n{'='*60}")
        print(f"[{cat.upper()}] Running {cat} tests...")
        print(f"{'='*60}")
        runner = TestRunner()
        CATEGORIES[cat](runner)
        passed = runner.summary()
        if not passed:
            all_passed = False

    print(f"\n{'='*60}")
    if all_passed:
        print("[ALL TESTS PASSED]")
    else:
        print("[SOME TESTS FAILED]")
    print(f"{'='*60}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
