"""
Multi-agent concurrent WebSocket stress test.
Creates 10 independent agents, 10 WS connections simultaneously,
each sending heartbeat every 2s for ~5 minutes (150 cycles).

Monitors: peak connections, drops, max_conn rejections, avg latency per agent.

Usage:
    LONG_STABILITY_CYCLES=150 python tests/real_openclaw/concurrency_stress.py
"""
import asyncio
import json
import os
import sys
import time
import uuid

import httpx
import websockets

API_BASE = os.getenv("AGENTNET_API_BASE", "http://localhost:9001")
WS_URL = API_BASE.replace("http://", "ws://") + "/v1/ws"

CYCLES = int(os.getenv("LONG_STABILITY_CYCLES", "150"))  # ~5 min with 2s interval
CONCURRENT = int(os.getenv("CONCURRENT_AGENTS", "10"))


def register_and_create_agent(idx: int) -> dict:
    """Register a new user, create an agent, return {token, agent_number}."""
    suffix = uuid.uuid4().hex[:6]
    r = httpx.post(f"{API_BASE}/v1/auth/register",
                   json={"username": f"stress-{idx}-{suffix}", "key_name": "stress"},
                   timeout=10)
    r.raise_for_status()
    api_key = r.json()["api_key"]

    r = httpx.post(f"{API_BASE}/v1/agents",
                   json={"name": f"Stress Agent {idx}", "runtime": "test",
                         "inbound_policy": "public"},
                   headers={"Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"},
                   timeout=10)
    r.raise_for_status()
    agent = r.json()
    return {"token": agent["agent_token"], "agent_number": agent["agent_number"],
            "index": idx, "api_key": api_key}


async def run_agent_heartbeat(agent: dict, results: list):
    """Run heartbeat loop for one agent. Collects stats into results list."""
    session_id = f"stress-{agent['index']}-{uuid.uuid4().hex[:6]}"
    stats = {"index": agent["index"], "drops": 0, "errors": 0,
             "latencies": [], "connected": False, "disconnects": 0}

    try:
        async with websockets.connect(
            f"{WS_URL}?session_id={session_id}",
            additional_headers={"Authorization": f"Bearer {agent['token']}"},
            close_timeout=2,
        ) as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)
            if msg["type"] == "error":
                stats["errors"] += 1
                stats["error_msg"] = msg["payload"].get("message", "")[:80]
                results.append(stats)
                return
            stats["connected"] = True

            for cycle in range(CYCLES):
                t0 = time.time()
                try:
                    await ws.send(json.dumps({
                        "type": "presence.heartbeat",
                        "message_id": str(uuid.uuid4()),
                        "payload": {},
                    }))
                    raw = await asyncio.wait_for(ws.recv(), timeout=10)
                    msg = json.loads(raw)
                    stats["latencies"].append(time.time() - t0)

                    if msg["type"] == "error":
                        payload = msg.get("payload", {})
                        if "max connections" in payload.get("message", "").lower():
                            stats["errors"] += 1
                        else:
                            stats["drops"] += 1
                except asyncio.TimeoutError:
                    stats["drops"] += 1
                except websockets.ConnectionClosed:
                    stats["disconnects"] += 1
                    break

                # Print progress marker every 50 cycles for agent 0 only
                if agent["index"] == 0 and (cycle + 1) % 50 == 0:
                    elapsed = (cycle + 1) * 2
                    print(f"  [Agent-0] {cycle+1}/{CYCLES} cycles (~{elapsed}s)")

                await asyncio.sleep(2)

    except Exception as e:
        stats["errors"] += 1
        stats["error_msg"] = str(e)[:80]

    results.append(stats)


async def main():
    print(f"API: {API_BASE}")
    print(f"Cycles per agent: {CYCLES} (~{CYCLES * 2 // 60} min)")
    print(f"Concurrent agents: {CONCURRENT}")
    print(f"Total expected heartbeats: {CONCURRENT * CYCLES}")
    print()

    # Step 1: Create all agents
    print("=== Creating agents ===")
    agents = []
    for i in range(CONCURRENT):
        agent = register_and_create_agent(i)
        agents.append(agent)
        print(f"  Agent {i}: {agent['agent_number']}")
    print(f"  Created {len(agents)} agents")

    # Step 2: Run all agents concurrently
    print(f"\n=== Starting {CONCURRENT} concurrent WS connections ===")
    results: list[dict] = []
    t0 = time.time()

    tasks = [run_agent_heartbeat(a, results) for a in agents]
    await asyncio.gather(*tasks, return_exceptions=True)

    total_time = time.time() - t0

    # Step 3: Compute statistics
    print(f"\n{'='*60}")
    print(f"=== CONCURRENCY STRESS TEST RESULTS ===")
    print(f"{'='*60}")
    print(f"Total time: {total_time:.0f}s ({total_time/60:.1f} min)")
    print()

    connected = sum(1 for r in results if r.get("connected"))
    total_drops = sum(r["drops"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    total_disconnects = sum(r["disconnects"] for r in results)
    total_cycles = sum(len(r["latencies"]) for r in results)

    print(f"Agents connected: {connected}/{CONCURRENT}")
    print(f"Total heartbeat cycles completed: {total_cycles}/{CONCURRENT * CYCLES}")
    print(f"Total drops: {total_drops}")
    print(f"Total errors (max_conn etc): {total_errors}")
    print(f"Total disconnects: {total_disconnects}")
    print()

    all_latencies = [l for r in results for l in r.get("latencies", [])]
    if all_latencies:
        print(f"Avg latency: {sum(all_latencies)/len(all_latencies):.3f}s")
        print(f"Min latency: {min(all_latencies):.3f}s")
        print(f"Max latency: {max(all_latencies):.3f}s")
        print(f"P50 latency: {sorted(all_latencies)[len(all_latencies)//2]:.3f}s")
        print(f"P99 latency: {sorted(all_latencies)[int(len(all_latencies)*0.99)]:.3f}s")

    print()
    print("Per-agent details:")
    for r in sorted(results, key=lambda x: x.get("index", 0)):
        lats = r.get("latencies", [])
        avg_lat = sum(lats) / len(lats) if lats else 0
        status = "CONNECTED" if r.get("connected") else f"ERROR: {r.get('error_msg', 'unknown')[:40]}"
        print(f"  Agent-{r['index']}: {status} | "
              f"cycles={len(lats)} | drops={r['drops']} | errs={r['errors']} | "
              f"avg_lat={avg_lat:.3f}s")

    # Assertions
    assert connected == CONCURRENT, f"Only {connected}/{CONCURRENT} connected"
    assert total_errors == 0, f"Errors occurred: {total_errors}"
    assert total_disconnects == 0, f"Disconnects: {total_disconnects}"
    print(f"\nRESULT: PASS ({connected}/{CONCURRENT} agents, {total_cycles} heartbeats, 0 errors)")

if __name__ == "__main__":
    asyncio.run(main())
