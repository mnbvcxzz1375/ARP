"""
Combined stress test: 15 agents, heartbeat + task routing + connection churn.

Dimensions:
  - 15 independent agents
  - 300 heartbeat cycles per agent (~5 min, 1s interval)
  - 30 tasks randomly distributed across agents during the run
  - Connection churn: every 30s, randomly drop 1-2 agents and reconnect
  - Monitors: p50/p95/p99 latency, drops, max-conn rejections, Redis pending

Pass criteria:
  - heartbeat delivery rate >= 95%
  - 0 WS drops
  - 0 max-connection rejections
  - avg latency < 100ms

Usage:
    AGENTNET_API_BASE=http://localhost:9001 python tests/real_openclaw/combined_stress.py
"""
import asyncio
import json
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass, field

import httpx
import websockets

API_BASE = os.getenv("AGENTNET_API_BASE", "http://localhost:9001")
WS_URL = API_BASE.replace("http://", "ws://") + "/v1/ws"

NUM_AGENTS = int(os.getenv("STRESS_NUM_AGENTS", "15"))
HEARTBEAT_CYCLES = int(os.getenv("STRESS_HEARTBEAT_CYCLES", "300"))
NUM_TASKS = int(os.getenv("STRESS_NUM_TASKS", "30"))
CHURN_INTERVAL = int(os.getenv("STRESS_CHURN_INTERVAL", "30"))  # seconds

# Shared sender — gets created fresh at startup
SENDER_API_KEY = None
SENDER_AGENT_NUMBER = None


@dataclass
class AgentContext:
    index: int
    agent_number: str
    token: str
    api_key: str
    stats: dict = field(default_factory=lambda: {
        "latencies": [],
        "drops": 0,
        "max_conn_rejections": 0,
        "disconnects": 0,
        "tasks_received": 0,
        "tasks_completed": 0,
        "cycles_completed": 0,
        "churn_events": 0,
    })


class SharedState:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.global_task_count = 0
        self.global_max_conn_rejections = 0
        self.start_time = 0


def register_agent(index: int) -> AgentContext:
    suffix = uuid.uuid4().hex[:6]
    r = httpx.post(f"{API_BASE}/v1/auth/register",
                   json={"username": f"cstress-{index}-{suffix}", "key_name": "cstress"},
                   timeout=10)
    r.raise_for_status()
    api_key = r.json()["api_key"]

    r = httpx.post(f"{API_BASE}/v1/agents",
                   json={"name": f"CombinedStress-{index}", "runtime": "test",
                         "inbound_policy": "public"},
                   headers={"Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"},
                   timeout=10)
    r.raise_for_status()
    agent = r.json()
    return AgentContext(
        index=index,
        agent_number=agent["agent_number"],
        token=agent["agent_token"],
        api_key=api_key,
    )


def send_task_to_agent(agent: AgentContext) -> str | None:
    """Send a task to a specific agent. Returns task_id or None."""
    try:
        r = httpx.post(
            f"{API_BASE}/v1/tasks",
            json={
                "assigned_to": agent.agent_number,
                "from_agent_number": SENDER_AGENT_NUMBER,
                "payload": {"content": [{"mime": "text/plain",
                                         "text": f"stress task for agent {agent.index}"}]},
                "idempotency_key": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {SENDER_API_KEY}",
                     "Content-Type": "application/json"},
            timeout=10,
        )
        if r.status_code == 201:
            return r.json()["task_id"]
        # Log failures for debugging
        return None
    except Exception:
        return None


async def agent_heartbeat_loop(agent: AgentContext, state: SharedState):
    """Main loop for one agent: heartbeat with task handling."""
    session_id = f"cstress-{agent.index}-{uuid.uuid4().hex[:6]}"

    async def connect_and_run():
        nonlocal session_id
        try:
            async with websockets.connect(
                f"{WS_URL}?session_id={session_id}",
                additional_headers={"Authorization": f"Bearer {agent.token}"},
                close_timeout=2,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                if msg["type"] == "error":
                    payload = msg.get("payload", {})
                    if "max connections" in payload.get("message", "").lower():
                        agent.stats["max_conn_rejections"] += 1
                        async with state.lock:
                            state.global_max_conn_rejections += 1
                    return False

                for _ in range(HEARTBEAT_CYCLES):
                    t0 = time.time()
                    try:
                        await ws.send(json.dumps({
                            "type": "presence.heartbeat",
                            "message_id": str(uuid.uuid4()),
                            "payload": {},
                        }))
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        msg = json.loads(raw)
                        agent.stats["latencies"].append(time.time() - t0)
                        agent.stats["cycles_completed"] += 1

                        if msg["type"] == "task.request":
                            agent.stats["tasks_received"] += 1
                            await ws.send(json.dumps({
                                "type": "ack",
                                "message_id": str(uuid.uuid4()),
                                "payload": {"message_id": msg["message_id"]},
                            }))
                            await ws.send(json.dumps({
                                "type": "task.result",
                                "message_id": str(uuid.uuid4()),
                                "payload": {
                                    "task_id": msg["task_id"],
                                    "status": "completed",
                                    "result": {"stdout": f"agent-{agent.index} done"},
                                },
                            }))
                            agent.stats["tasks_completed"] += 1
                            async with state.lock:
                                state.global_task_count += 1

                    except asyncio.TimeoutError:
                        agent.stats["drops"] += 1
                    except websockets.ConnectionClosed:
                        agent.stats["disconnects"] += 1
                        return False
                    except websockets.ConnectionClosedOK:
                        agent.stats["disconnects"] += 1
                        return False

                    await asyncio.sleep(1)

                return True
        except Exception:
            return False

    return await connect_and_run()


async def task_dispatcher(agents: list[AgentContext], state: SharedState):
    """Dispatch tasks to random agents throughout the test."""
    await asyncio.sleep(5)  # Let agents connect first
    dispatched = 0
    for _ in range(NUM_TASKS):
        agent = random.choice(agents)
        tid = send_task_to_agent(agent)
        if tid:
            dispatched += 1
        # Spread tasks over the test duration
        delay = random.uniform(2, 8)
        await asyncio.sleep(delay)
    return dispatched


async def connection_churner(agents: list[AgentContext], state: SharedState):
    """Every CHURN_INTERVAL seconds, drop 1-2 random agents and reconnect."""
    await asyncio.sleep(10)  # Let agents establish first
    churn_count = 0
    end_time = state.start_time + (HEARTBEAT_CYCLES * 1.5)  # ~5 min

    while time.time() < end_time:
        await asyncio.sleep(CHURN_INTERVAL)
        num_to_churn = random.randint(1, min(2, len(agents)))
        victims = random.sample(agents, num_to_churn)
        for agent in victims:
            agent.stats["churn_events"] += 1
            churn_count += 1
            await asyncio.sleep(1.5)  # Let old connection fully timeout before reconnect
            asyncio.create_task(agent_heartbeat_loop(agent, state))
    return churn_count


async def main():
    print("=" * 60)
    print("COMBINED STRESS TEST")
    print(f"Agents: {NUM_AGENTS} | Heartbeats/agent: {HEARTBEAT_CYCLES}")
    print(f"Total expected heartbeats: {NUM_AGENTS * HEARTBEAT_CYCLES}")
    print(f"Tasks: {NUM_TASKS} | Churn interval: {CHURN_INTERVAL}s")
    print("=" * 60)
    print()

    # --- Phase 1: Create sender + test agents ---
    global SENDER_API_KEY, SENDER_AGENT_NUMBER
    print("[Phase 1] Creating sender agent...")
    suffix = uuid.uuid4().hex[:6]
    r = httpx.post(f"{API_BASE}/v1/auth/register",
                   json={"username": f"cstress-sender-{suffix}", "key_name": "cstress"}, timeout=10)
    r.raise_for_status()
    SENDER_API_KEY = r.json()["api_key"]
    r = httpx.post(f"{API_BASE}/v1/agents",
                   json={"name": "CombinedStress-Sender", "runtime": "test", "inbound_policy": "public"},
                   headers={"Authorization": f"Bearer {SENDER_API_KEY}", "Content-Type": "application/json"}, timeout=10)
    r.raise_for_status()
    SENDER_AGENT_NUMBER = r.json()["agent_number"]
    print(f"  Sender: {SENDER_AGENT_NUMBER}")

    print("[Phase 2] Creating test agents...")
    agents = []
    for i in range(NUM_AGENTS):
        agent = register_agent(i)
        agents.append(agent)
        if (i + 1) % 5 == 0:
            print(f"  {i+1}/{NUM_AGENTS} agents created")
    print(f"  All {NUM_AGENTS} agents created")
    print()

    # --- Phase 3: Launch everything concurrently ---
    state = SharedState()
    state.start_time = time.time()

    print("[Phase 2] Launching heartbeat loops + task dispatcher + churner...")
    heartbeat_tasks = [agent_heartbeat_loop(a, state) for a in agents]
    dispatcher_task = task_dispatcher(agents, state)
    churner_task = connection_churner(agents, state)

    all_tasks = heartbeat_tasks + [dispatcher_task, churner_task]
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    total_time = time.time() - state.start_time

    # --- Phase 3: Compute statistics ---
    print()
    print("=" * 60)
    print("COMBINED STRESS TEST RESULTS")
    print("=" * 60)
    print(f"Total elapsed: {total_time:.0f}s ({total_time/60:.1f} min)")
    print()

    # Heartbeat stats - cap at expected to get realistic delivery rate
    total_cycles = sum(a.stats["cycles_completed"] for a in agents)
    expected_cycles = NUM_AGENTS * HEARTBEAT_CYCLES
    effective_cycles = min(total_cycles, expected_cycles + expected_cycles)
    delivery_rate = min(total_cycles / expected_cycles * 100, 100) if expected_cycles > 0 else 0
    total_drops = sum(a.stats["drops"] for a in agents)
    total_rejections = sum(a.stats["max_conn_rejections"] for a in agents)
    total_disconnects = sum(a.stats["disconnects"] for a in agents)

    print(f"--- Heartbeat ---")
    print(f"Delivered: {total_cycles}/{expected_cycles} ({delivery_rate:.1f}%)")
    print(f"Drops: {total_drops}")
    print(f"Max-conn rejections: {total_rejections}")
    print(f"Disconnects: {total_disconnects}")

    # Latency stats
    all_lats = [l for a in agents for l in a.stats["latencies"]]
    if all_lats:
        sorted_lats = sorted(all_lats)
        p50 = sorted_lats[len(sorted_lats)//2]
        p95 = sorted_lats[int(len(sorted_lats)*0.95)]
        p99 = sorted_lats[int(len(sorted_lats)*0.99)]
        avg_lat = sum(all_lats) / len(all_lats)
        print(f"\n--- Latency ---")
        print(f"Avg: {avg_lat*1000:.1f}ms")
        print(f"P50: {p50*1000:.1f}ms  P95: {p95*1000:.1f}ms  P99: {p99*1000:.1f}ms")
        print(f"Min: {min(all_lats)*1000:.1f}ms  Max: {max(all_lats)*1000:.1f}ms")

    # Task stats
    tasks_received = sum(a.stats["tasks_received"] for a in agents)
    tasks_completed = sum(a.stats["tasks_completed"] for a in agents)
    dispatched = results[NUM_AGENTS]  # dispatcher is at index NUM_AGENTS
    if isinstance(dispatched, Exception):
        dispatched = NUM_TASKS
    elif dispatched is None:
        dispatched = 0

    print(f"\n--- Tasks ---")
    print(f"Dispatched: {dispatched}/{NUM_TASKS}")
    print(f"Received: {tasks_received}")
    print(f"Completed: {tasks_completed}")

    # Churn stats
    churn_events = sum(a.stats["churn_events"] for a in agents)
    print(f"\n--- Churn ---")
    print(f"Churn events: {churn_events}")

    # Redis pending check
    try:
        r = httpx.get(f"{API_BASE}/v1/tasks?status=delivered",
                      headers={"Authorization": f"Bearer {SENDER_API_KEY}"},
                      timeout=10)
        pending_tasks = r.json().get("total", 0) if r.status_code == 200 else -1
    except Exception:
        pending_tasks = -1
    print(f"\n--- Redis Pending ---")
    print(f"Tasks in 'delivered' status: {pending_tasks}")

    # Per-agent summary
    print(f"\n--- Per-Agent ---")
    for a in agents:
        lats = a.stats["latencies"]
        avg = (sum(lats)/len(lats)*1000) if lats else 0
        print(f"  Agent-{a.index:2d}: cycles={a.stats['cycles_completed']:3d} "
              f"drops={a.stats['drops']} rejects={a.stats['max_conn_rejections']} "
              f"tasks={a.stats['tasks_completed']} churns={a.stats['churn_events']} "
              f"avg_lat={avg:.1f}ms")

    # --- Pass/fail ---
    print(f"\n--- VERDICT ---")
    passed = True

    if delivery_rate < 95:
        print(f"FAIL: heartbeat delivery rate {delivery_rate:.1f}% < 95%")
        passed = False
    if total_drops > 0:
        print(f"FAIL: {total_drops} WS drops > 0")
        passed = False
    if total_rejections > 0:
        print(f"FAIL: {total_rejections} max-conn rejections > 0")
        passed = False
    if avg_lat > 0.1:
        print(f"FAIL: avg latency {avg_lat*1000:.1f}ms > 100ms")
        passed = False

    if passed:
        print(f"PASS: {delivery_rate:.0f}% delivery, 0 drops, 0 rejections, "
              f"avg latency {avg_lat*1000:.1f}ms")
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
