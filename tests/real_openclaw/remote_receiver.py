"""
Remote OpenClaw adapter agent - connects to API via WebSocket,
receives tasks, executes them, and sends results back.
Run on remote machine (100.127.164.72).
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid

# Bypass system proxy for Tailscale IPs
os.environ["NO_PROXY"] = "100.118.246.96,100.127.164.72"
os.environ["no_proxy"] = os.environ["NO_PROXY"]

import websockets

_missing = [v for v in ("AGENTNET_API_KEY", "AGENTNET_AGENT_TOKEN") if not os.environ.get(v)]
if _missing:
    print(f"ERROR: required environment variables not set: {', '.join(_missing)}", file=sys.stderr)
    sys.exit(1)

API_WS_URL = "ws://100.118.246.96:8000/v1/ws"
AGENT_TOKEN = os.environ["AGENTNET_AGENT_TOKEN"]
API_KEY = os.environ["AGENTNET_API_KEY"]
# Use python as substitute command since openclaw is not installed
COMMAND = sys.executable
WORKING_DIR = "C:\\Users\\Andrewhyc\\agentnet_workdir"


def make_msg(msg_type, payload=None):
    return json.dumps({
        "type": msg_type,
        "message_id": str(uuid.uuid4()),
        "payload": payload or {},
    })


def execute_task(args: list[str]) -> dict:
    """Execute a command and return the result."""
    import os
    os.makedirs(WORKING_DIR, exist_ok=True)

    full_cmd = [COMMAND] + args
    print(f"  [EXEC] {' '.join(full_cmd)}")
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=WORKING_DIR,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Command timed out"}
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e)}


async def send_heartbeat(ws):
    """Send heartbeat every 10 seconds."""
    while True:
        await asyncio.sleep(10)
        try:
            await ws.send(make_msg("presence.heartbeat"))
            print("  [HB] heartbeat sent")
        except Exception:
            break


async def main():
    print(f"[RECEIVER] Connecting to {API_WS_URL}")
    print(f"[RECEIVER] Using command: {COMMAND}")

    uri = f"{API_WS_URL}?session_id=receiver-session-1"
    headers = {"Authorization": f"Bearer {AGENT_TOKEN}"}

    async with websockets.connect(
        uri,
        additional_headers=headers,
        close_timeout=5,
    ) as ws:
        # Receive session resume result
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        msg = json.loads(raw)
        print(f"[RECEIVER] Connected: {msg['type']}")
        if msg["type"] == "error":
            print(f"[RECEIVER] Auth error: {msg['payload']}")
            return
        conn_id = msg["payload"].get("connection_id", "unknown")
        print(f"[RECEIVER] Connection ID: {conn_id}")

        # Start heartbeat task
        hb_task = asyncio.create_task(send_heartbeat(ws))

        print("[RECEIVER] Waiting for tasks...")
        try:
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)
                except asyncio.TimeoutError:
                    print("[RECEIVER] No task received in 60s, still listening...")
                    continue

                msg = json.loads(raw)
                msg_type = msg.get("type")
                print(f"[RECEIVER] Received: {msg_type}")

                if msg_type == "task.request":
                    task_id = msg["task_id"]
                    message_id = msg["message_id"]
                    payload = msg["payload"]
                    print(f"[RECEIVER] Task {task_id}: {payload}")

                    # Parse args from payload
                    args = []
                    content = payload.get("content", [])
                    for part in content:
                        if part.get("mime") == "application/json":
                            data = part.get("data", {})
                            if "args" in data:
                                args = data["args"]
                        elif part.get("mime") == "text/plain":
                            import shlex
                            text = part.get("text", "")
                            if text:
                                try:
                                    args = shlex.split(text)
                                except ValueError:
                                    args = text.split()

                    if not args:
                        # Default: echo the payload
                        args = ["-c", f"print('Echo from remote: {json.dumps(payload)}')"]

                    # Send ACK for the request message
                    await ws.send(make_msg("ack", {"message_id": message_id}))
                    print(f"[RECEIVER] ACK sent for message {message_id}")

                    # Send task.accepted (DELIVERED -> ACCEPTED)
                    await ws.send(make_msg("task.accepted", {"task_id": task_id}))
                    print(f"[RECEIVER] Accepted task {task_id}")

                    # Execute
                    result = execute_task(args)
                    print(f"[RECEIVER] Result: exit_code={result['exit_code']}")
                    if result["stdout"]:
                        print(f"[RECEIVER] stdout: {result['stdout'][:200]}")

                    # Send task.result back (completes the task)
                    result_payload = {
                        "task_id": task_id,
                        "status": "completed" if result["exit_code"] == 0 else "failed",
                        "result": result,
                    }
                    await ws.send(make_msg("task.result", result_payload))
                    print(f"[RECEIVER] Result sent for task {task_id}")
                    print("[RECEIVER] === TASK COMPLETE ===")

                elif msg_type == "ack":
                    print(f"[RECEIVER] ACK received: {msg.get('payload')}")

        except websockets.ConnectionClosed as e:
            print(f"[RECEIVER] Connection closed: {e}")
        finally:
            hb_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
