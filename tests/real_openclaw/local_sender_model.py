"""
Local sender - sends diverse coding prompts to remote AI model (qwen3.6-plus).
"""
import httpx
import json
import time
import uuid

API_BASE = "http://localhost:8000"
API_KEY = "ak_Bg95_c11p9ZRkqJe5CR5wRKvjTukOVJ8VYck3SGZ9HI"
SENDER_AGENT_NUMBER = "AN-GLOBAL-BB05A89F32-ZQ"
RECEIVER_AGENT_NUMBER = "AN-GLOBAL-295B51BD51-9Z"

HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def send_task(payload: dict) -> dict:
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
        time.sleep(1)
    resp.raise_for_status()
    return resp.json()


def wait_for_result(task_id: str, timeout: float = 120) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(f"{API_BASE}/v1/tasks/{task_id}", headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            task = resp.json()
            if task["status"] in ("completed", "failed"):
                return task
        time.sleep(1)
    return {"status": "timeout"}


TEST_CASES = [
    {
        "name": "Quick Sort Algorithm",
        "prompt": "Write a Python quicksort function with type annotations and docstring. Only code, no explanation.",
    },
    {
        "name": "Regex for Email",
        "prompt": "Write a Python regex to validate email addresses. Provide the regex pattern and a test function with 3 test cases.",
    },
    {
        "name": "Code Review - SQL Injection",
        "prompt": "Review this code for security vulnerabilities:\n```python\nquery = f\"SELECT * FROM users WHERE username='{username}'\"\n```\nIdentify the issue and provide a fixed version.",
    },
    {
        "name": "Async Explanation",
        "prompt": "Explain how Python async/await works in 3 short sentences. Use a simple example.",
    },
    {
        "name": "SQL Optimization",
        "prompt": "This query is slow: SELECT * FROM orders WHERE user_id IN (SELECT id FROM users WHERE created_at > '2024-01-01') AND status = 'pending' ORDER BY created_at DESC LIMIT 100. How to optimize it?",
    },
    {
        "name": "REST API Design",
        "prompt": "Design RESTful API endpoints for a todo list app. List all endpoints with HTTP methods, paths, and request/response bodies in a concise format.",
    },
    {
        "name": "Python Decorator",
        "prompt": "Write a Python decorator called @retry that retries a function up to 3 times on exception. Include the decorator code and a usage example.",
    },
    {
        "name": "Docker Compose",
        "prompt": "Write a minimal docker-compose.yml for a web app with a Flask service and a PostgreSQL service. Include health checks.",
    },
]


def main():
    results = []
    print(f"[SENDER] API: {API_BASE}")
    print(f"[SENDER] Sender:   {SENDER_AGENT_NUMBER}")
    print(f"[SENDER] Receiver: {RECEIVER_AGENT_NUMBER}")
    print(f"[SENDER] Model: qwen3.6-plus (DashScope Coding Plan)")
    print(f"[SENDER] Total test cases: {len(TEST_CASES)}")
    print("=" * 60)

    start_time = time.time()

    for i, tc in enumerate(TEST_CASES, 1):
        t0 = time.time()
        print(f"\n[TEST {i}/{len(TEST_CASES)}] {tc['name']}")
        print(f"  Prompt: {tc['prompt'][:80]}...")

        task = send_task({
            "content": [{"mime": "application/json", "data": {"prompt": tc["prompt"]}}]
        })
        task_id = task["task_id"]
        print(f"  Task ID: {task_id}")

        result = wait_for_result(task_id)
        elapsed = time.time() - t0
        status = result.get("status", "unknown")
        stdout = ""
        stderr = ""
        if result.get("result"):
            stdout = result["result"].get("stdout", "")
            stderr = result["result"].get("stderr", "")

        print(f"  Status: {status} (took {elapsed:.1f}s)")
        if status == "completed" and stdout:
            preview = stdout[:300].replace("\n", "\n    ")
            print(f"  Output: {preview}")
        if stderr:
            print(f"  Stderr: {stderr[:200]}")

        results.append({
            "case": tc["name"],
            "prompt": tc["prompt"],
            "task_id": task_id,
            "status": status,
            "elapsed_sec": round(elapsed, 1),
            "output": stdout,
            "error": stderr,
        })
        icon = "PASS" if status == "completed" else "FAIL"
        print(f"  [{icon}]")

    total_time = time.time() - start_time
    passed = sum(1 for r in results if r["status"] == "completed")

    print("\n" + "=" * 60)
    print(f"\n[SUMMARY] {passed}/{len(TEST_CASES)} passed in {total_time:.0f}s")
    for r in results:
        icon = "PASS" if r["status"] == "completed" else "FAIL"
        print(f"  [{icon}] {r['case']} ({r['elapsed_sec']}s)")

    with open("test_model_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[SENDER] Results saved to test_model_results.json")
    return results


if __name__ == "__main__":
    main()
