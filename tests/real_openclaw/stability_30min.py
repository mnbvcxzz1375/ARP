#!/usr/bin/env python3
"""30-minute WebSocket heartbeat stability test."""
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
CYCLES = int(os.getenv("LONG_STABILITY_CYCLES", "900"))  # ~30 min


async def main():
    # Create fresh agent
    suffix = uuid.uuid4().hex[:6]
    r = httpx.post(f"{API_BASE}/v1/auth/register",
                   json={"username": f"stab30m-{suffix}", "key_name": "stab30"}, timeout=10)
    r.raise_for_status()
    api_key = r.json()["api_key"]

    r = httpx.post(f"{API_BASE}/v1/agents",
                   json={"name": "Stab30m Agent", "runtime": "test", "inbound_policy": "public"},
                   headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                   timeout=10)
    r.raise_for_status()
    agent = r.json()
    token = agent["agent_token"]
    print(f"Agent: {agent['agent_number']}", flush=True)

    session_id = f"stab30m-{uuid.uuid4().hex[:6]}"
    async with websockets.connect(
        f"{WS_URL}?session_id={session_id}",
        additional_headers={"Authorization": f"Bearer {token}"},
        close_timeout=2,
    ) as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        msg = json.loads(raw)
        print(f"Connected: {msg['type']}", flush=True)

        drops = 0
        errors = 0
        disconnects = 0
        latencies = []
        t0 = time.time()

        for c in range(CYCLES):
            t1 = time.time()
            try:
                await ws.send(json.dumps({
                    "type": "presence.heartbeat",
                    "message_id": str(uuid.uuid4()),
                    "payload": {},
                }))
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                latencies.append(time.time() - t1)
            except asyncio.TimeoutError:
                drops += 1
            except websockets.ConnectionClosed:
                disconnects += 1
                break

            if (c + 1) % 180 == 0:
                elapsed = time.time() - t0
                avg = sum(latencies[-60:]) / len(latencies[-60:])
                print(f"  [{c+1}/{CYCLES}] elapsed={elapsed/60:.0f}min "
                      f"avg_lat={avg:.3f}s drops={drops} errs={errors}",
                      flush=True)

            await asyncio.sleep(2)

        total = time.time() - t0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0

        print(f"\n=== 30-MINUTE STABILITY RESULTS ===", flush=True)
        print(f"Cycles: {c+1}/{CYCLES}", flush=True)
        print(f"Drops: {drops}  Errors: {errors}  Disconnects: {disconnects}", flush=True)
        print(f"Total time: {total:.0f}s ({total/60:.1f} min)", flush=True)
        print(f"Avg latency: {avg_lat:.3f}s", flush=True)
        if latencies:
            sorted_lats = sorted(latencies)
            print(f"Min/Max latency: {min(latencies):.3f}s / {max(latencies):.3f}s", flush=True)
            print(f"P50: {sorted_lats[len(sorted_lats)//2]:.3f}s  "
                  f"P99: {sorted_lats[int(len(sorted_lats)*0.99)]:.3f}s", flush=True)

        assert drops == 0 and errors == 0 and disconnects == 0, \
            f"drops={drops} errors={errors} disconnects={disconnects}"
        print("RESULT: PASS", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
