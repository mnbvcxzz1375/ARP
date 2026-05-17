"""
Local sender - sends tasks to the remote OpenClaw receiver agent via the API.
Run on local machine.
"""
import httpx
import json
import sys
import time
import uuid

API_BASE = "http://localhost:8000"
API_KEY = "ak_Bg95_c11p9ZRkqJe5CR5wRKvjTukOVJ8VYck3SGZ9HI"
SENDER_AGENT_NUMBER = "AN-GLOBAL-BB05A89F32-ZQ"
RECEIVER_AGENT_NUMBER = "AN-GLOBAL-295B51BD51-9Z"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def send_task(payload: dict) -> dict:
    """Send a task to the receiver agent. Retries on transient errors."""
    import time as _time
    body = {
        "assigned_to": RECEIVER_AGENT_NUMBER,
        "from_agent_number": SENDER_AGENT_NUMBER,
        "payload": payload,
        "idempotency_key": str(uuid.uuid4()),
    }
    for attempt in range(3):
        resp = httpx.post(f"{API_BASE}/v1/tasks", json=body, headers=HEADERS, timeout=10)
        if resp.status_code < 500:
            resp.raise_for_status()
            return resp.json()
        print(f"[SENDER] Server error {resp.status_code} on attempt {attempt+1}, retrying...")
        _time.sleep(1)
    resp.raise_for_status()
    return resp.json()


def wait_for_result(task_id: str, timeout: float = 30) -> dict:
    """Poll for task completion."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(f"{API_BASE}/v1/tasks/{task_id}", headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            task = resp.json()
            if task["status"] in ("completed", "failed"):
                return task
        time.sleep(0.5)
    return {"status": "timeout"}


def main():
    print(f"[SENDER] API: {API_BASE}")
    print(f"[SENDER] Sender:   {SENDER_AGENT_NUMBER}")
    print(f"[SENDER] Receiver: {RECEIVER_AGENT_NUMBER}")
    print()

    # Test 1: Simple echo command via Python
    print("[SENDER] === Test 1: Python echo command ===")
    task = send_task({
        "content": [
            {
                "mime": "application/json",
                "data": {
                    "args": ["-c", "print('Hello from remote OpenClaw agent!')"],
                },
            }
        ],
    })
    task_id = task["task_id"]
    print(f"[SENDER] Task created: {task_id}")
    print(f"[SENDER] Status: {task['status']}")

    result = wait_for_result(task_id)
    print(f"[SENDER] Final status: {result['status']}")
    if result.get("result"):
        print(f"[SENDER] Result: {json.dumps(result['result'], indent=2)}")
    print()

    # Test 2: System info command
    print("[SENDER] === Test 2: System info command ===")
    task2 = send_task({
        "content": [
            {
                "mime": "application/json",
                "data": {
                    "args": ["-c", "import platform; print(f'OS: {platform.system()} {platform.release()}'); print(f'Python: {platform.python_version()}'); print(f'Hostname: {platform.node()}')"],
                },
            }
        ],
    })
    task2_id = task2["task_id"]
    print(f"[SENDER] Task created: {task2_id}")

    result2 = wait_for_result(task2_id)
    print(f"[SENDER] Final status: {result2['status']}")
    if result2.get("result"):
        print(f"[SENDER] Result: {json.dumps(result2['result'], indent=2)}")
    print()

    # Test 3: text/plain format
    print("[SENDER] === Test 3: Text plain format ===")
    task3 = send_task({
        "content": [
            {
                "mime": "text/plain",
                "text": "-c print('text/plain format works!')",
            }
        ],
    })
    task3_id = task3["task_id"]
    print(f"[SENDER] Task created: {task3_id}")

    result3 = wait_for_result(task3_id)
    print(f"[SENDER] Final status: {result3['status']}")
    if result3.get("result"):
        print(f"[SENDER] Result: {json.dumps(result3['result'], indent=2)}")
    print()

    # Check task messages
    print("[SENDER] === Checking task messages ===")
    resp = httpx.get(
        f"{API_BASE}/v1/tasks/{task_id}/messages",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 200:
        msgs = resp.json()
        print(f"[SENDER] Messages for task {task_id}: {len(msgs.get('messages', []))} messages")
        for m in msgs.get("messages", []):
            print(f"  - type={m['type']} status={m['delivery_status']}")

    print()
    print("[SENDER] === ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    main()
