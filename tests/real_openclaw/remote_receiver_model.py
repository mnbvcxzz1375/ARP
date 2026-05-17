"""
OpenClaw adapter receiver with DashScope coding model (qwen3.6-plus).
Connects via WebSocket, receives tasks, calls AI model, returns results.
Uses conda 'openclaw' environment on remote machine.
"""
import asyncio
import json
import os
import subprocess
import sys
import uuid

# Bypass system proxy
os.environ["NO_PROXY"] = "100.118.246.96,100.127.164.72,coding.dashscope.aliyuncs.com"
os.environ["no_proxy"] = os.environ["NO_PROXY"]

import websockets

API_WS_URL = "ws://100.118.246.96:8000/v1/ws"
AGENT_TOKEN = "agt_sk_FIzxDbBFIH2yC-LrWfwg2FKXN23MNHvK8m_TyoNAPoQ"

# Use conda openclaw environment
PYTHON = r"D:\Software\Anaconda3\envs\openclaw\python.exe"
ASK_MODEL_SCRIPT = r"C:\Users\Andrewhyc\ask_model.py"
WORKING_DIR = r"C:\Users\Andrewhyc\agentnet_workdir"


def make_msg(msg_type, payload=None):
    return json.dumps({
        "type": msg_type,
        "message_id": str(uuid.uuid4()),
        "payload": payload or {},
    })


def call_model(prompt: str, system: str = "You are a helpful coding assistant.") -> dict:
    """Call the DashScope coding model (qwen3.6-plus)."""
    display = prompt[:100] + ("..." if len(prompt) > 100 else "")
    print(f"  [MODEL] Prompt: {repr(display)}")
    try:
        env = {**os.environ, "NO_PROXY": "coding.dashscope.aliyuncs.com",
               "PYTHONUTF8": "1"}
        result = subprocess.run(
            [PYTHON, ASK_MODEL_SCRIPT, "--system", system, prompt],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=WORKING_DIR,
            env=env,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Model call timed out (120s)"}
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": f"Model error: {e}"}


def execute_command(args: list[str]) -> dict:
    """Execute a CLI command."""
    full_cmd = [PYTHON] + args
    print(f"  [EXEC] {' '.join(full_cmd[:5])}...")
    try:
        os.makedirs(WORKING_DIR, exist_ok=True)
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
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
    while True:
        await asyncio.sleep(10)
        try:
            await ws.send(make_msg("presence.heartbeat"))
        except Exception:
            break


async def main():
    print(f"[RECEIVER] Connecting to {API_WS_URL}")
    print(f"[RECEIVER] Python: {PYTHON}")
    print(f"[RECEIVER] Model: qwen3.6-plus (DashScope)")

    uri = f"{API_WS_URL}?session_id=openclaw-model-session"
    headers = {"Authorization": f"Bearer {AGENT_TOKEN}"}

    retries = 0
    max_retries = 3
    while retries < max_retries:
        retries += 1
        print(f"[RECEIVER] Connection attempt {retries}/{max_retries}")
        try:
            async with websockets.connect(
                uri, additional_headers=headers, close_timeout=5
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                msg = json.loads(raw)
                print(f"[RECEIVER] Connected: {msg['type']}")
                if msg["type"] == "error":
                    print(f"[RECEIVER] Auth error: {msg['payload']}")
                    break
                conn_id = msg["payload"].get("connection_id", "unknown")
                print(f"[RECEIVER] Connection ID: {conn_id}")
                task_count = 0

                hb_task = asyncio.create_task(send_heartbeat(ws))
                print("[RECEIVER] Waiting for tasks...")

                try:
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=120)
                        except asyncio.TimeoutError:
                            print("[RECEIVER] 120s idle, still listening...")
                            continue

                        msg = json.loads(raw)
                        msg_type = msg.get("type")
                        print(f"\n[RECEIVER] Received: {msg_type}")

                        if msg_type == "task.request":
                            task_count += 1
                            task_id = msg["task_id"]
                            message_id = msg["message_id"]
                            payload = msg["payload"]
                            content = payload.get("content", [])

                            # Parse task content
                            prompt = None
                            args = []
                            mode = "model"  # default: call AI model

                            for part in content:
                                mime = part.get("mime", "")
                                if mime == "application/json":
                                    data = part.get("data", {})
                                    if "prompt" in data:
                                        prompt = data["prompt"]
                                    if "args" in data:
                                        args = data["args"]
                                        mode = "exec"
                                elif mime == "text/plain":
                                    text = part.get("text", "").strip()
                                    if text.startswith("exec:"):
                                        import shlex
                                        args = shlex.split(text[5:].strip())
                                        mode = "exec"
                                    else:
                                        prompt = text

                            # ACK and accept
                            await ws.send(make_msg("ack", {"message_id": message_id}))
                            await ws.send(make_msg("task.accepted", {"task_id": task_id}))
                            print(f"[RECEIVER] Task {task_count}: ACK + Accepted {task_id}")

                            # Execute
                            if mode == "exec" and args:
                                print(f"[RECEIVER] Mode: EXEC")
                                result = execute_command(args)
                            elif prompt:
                                print(f"[RECEIVER] Mode: MODEL")
                                print(f"[RECEIVER] Call: python ask_model.py --system ... {repr(prompt[:80])}")
                                result = call_model(prompt)
                                stdout_preview = repr(result.get('stdout','')[:100])
                                print(f"[RECEIVER] Model stdout ({len(result.get('stdout',''))} chars): {stdout_preview}")
                                print(f"[RECEIVER] Model stderr: {repr(result.get('stderr','')[:100])}")
                            else:
                                result = {"exit_code": 1, "stdout": "",
                                          "stderr": "No prompt or args provided"}

                            status = "completed" if result["exit_code"] == 0 else "failed"
                            print(f"[RECEIVER] Result: {status} (exit={result['exit_code']})")

                            # Send result
                            await ws.send(make_msg("task.result", {
                                "task_id": task_id,
                                "status": status,
                                "result": result,
                            }))
                            print(f"[RECEIVER] === TASK {task_count} COMPLETE ===")

                        elif msg_type == "ack":
                            pass

                except websockets.ConnectionClosed as e:
                    print(f"[RECEIVER] Connection closed: {e}")
                finally:
                    hb_task.cancel()
                    print(f"[RECEIVER] Processed {task_count} tasks in this session")

        except Exception as e:
            print(f"[RECEIVER] Error: {e}")
            await asyncio.sleep(2)

    print(f"[RECEIVER] Max retries reached, shutting down")


if __name__ == "__main__":
    asyncio.run(main())
