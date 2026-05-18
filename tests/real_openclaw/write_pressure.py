"""Pure write pressure test: POST /v1/tasks at scale."""
import concurrent.futures
import os
import statistics
import sys
import threading
import time
import uuid

import httpx

API_BASE = os.getenv("AGENTNET_API_BASE", "http://localhost:9001")
NUM_TASKS = int(os.getenv("WRITE_NUM_TASKS", "1000"))
NUM_WORKERS = int(os.getenv("WRITE_WORKERS", "20"))

# Created at startup
_sender_agent = None
_receiver_agent = None
_headers = None


def bootstrap():
    global _headers, _sender_agent, _receiver_agent
    suffix = uuid.uuid4().hex[:6]
    r = httpx.post(f"{API_BASE}/v1/auth/register",
                   json={"username": f"wp-{suffix}", "key_name": "wp"}, timeout=10)
    r.raise_for_status()
    api_key = r.json()["api_key"]
    _headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    r = httpx.post(f"{API_BASE}/v1/agents",
                   json={"name": "WP-Sender", "runtime": "test", "inbound_policy": "public"},
                   headers=_headers, timeout=10)
    r.raise_for_status()
    _sender_agent = r.json()["agent_number"]

    r = httpx.post(f"{API_BASE}/v1/agents",
                   json={"name": "WP-Receiver", "runtime": "test", "inbound_policy": "public"},
                   headers=_headers, timeout=10)
    r.raise_for_status()
    _receiver_agent = r.json()["agent_number"]
    print(f"Sender: {_sender_agent} | Receiver: {_receiver_agent}")
    return api_key


class Stats:
    def __init__(self):
        self.latencies = []
        self.errors = []
        self.task_ids = []
        self.message_ids = []
        self._lock = threading.Lock()

    def record(self, lat, status, body, tid):
        with self._lock:
            self.latencies.append(lat)
            if status == 201:
                self.task_ids.append(tid)
            else:
                self.errors.append((status, body[:80]))


def create_one(stats, i):
    t0 = time.time()
    try:
        r = httpx.post(
            f"{API_BASE}/v1/tasks",
            json={
                "assigned_to": _receiver_agent,
                "from_agent_number": _sender_agent,
                "payload": {"content": [{"mime": "text/plain", "text": f"wp-{i}"}]},
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=_headers,
            timeout=30,
        )
        lat = time.time() - t0
        tid = r.json().get("task_id") if r.status_code == 201 else None
        stats.record(lat, r.status_code, r.text, tid)
    except Exception as e:
        stats.record(time.time() - t0, 0, str(e), None)


def main():
    print("=" * 60)
    print("WRITE PRESSURE TEST")
    print(f"Tasks: {NUM_TASKS} | Workers: {NUM_WORKERS} | API: {API_BASE}")
    print("=" * 60)

    # Check API
    r = httpx.get(f"{API_BASE}/healthz", timeout=5)
    assert r.json()["status"] == "ok", "API not healthy"
    print("[OK] healthz")

    # Bootstrap
    api_key = bootstrap()

    # Baseline
    r = httpx.get(f"{API_BASE}/v1/tasks", headers=_headers, timeout=10)
    tasks_before = r.json().get("total", 0) if r.status_code == 200 else -1
    print(f"Tasks before: {tasks_before}")

    # Run
    stats = Stats()
    print(f"\nDispatching {NUM_TASKS} tasks ({NUM_WORKERS} workers)...")
    t0 = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
        futures = [pool.submit(create_one, stats, i) for i in range(NUM_TASKS)]
        for i, f in enumerate(concurrent.futures.as_completed(futures)):
            f.result()
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{NUM_TASKS} ({time.time() - t0:.1f}s)")

    total_time = time.time() - t0

    # Latency stats
    lats = stats.latencies
    s = sorted(lats)
    n = len(s)
    avg = sum(s) / n if n else 0
    p50 = s[n // 2] if n else 0
    p95 = s[int(n * 0.95)] if n else 0
    p99 = s[int(n * 0.99)] if n else 0
    err_rate = len(stats.errors) / NUM_TASKS * 100

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Total time: {total_time:.1f}s ({NUM_TASKS/total_time:.0f} req/s)")
    print(f"Success: {len(stats.task_ids)}/{NUM_TASKS}  Errors: {len(stats.errors)} ({err_rate:.1f}%)")
    print(f"Avg: {avg*1000:.1f}ms  P50: {p50*1000:.1f}ms  P95: {p95*1000:.1f}ms  P99: {p99*1000:.1f}ms")
    print(f"Min: {min(s)*1000:.1f}ms  Max: {max(s)*1000:.1f}ms" if s else "")

    if stats.errors:
        print(f"\nError samples:")
        for status, body in stats.errors[:5]:
            print(f"  {status}: {body}")

    # DB consistency
    time.sleep(2)
    r = httpx.get(f"{API_BASE}/v1/tasks", headers=_headers, timeout=10)
    tasks_after = r.json().get("total", 0) if r.status_code == 200 else -1
    delta = tasks_after - tasks_before

    # Check message count via DB query
    msg_count = -1
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "exec", "infra-postgres-1", "psql", "-U", "agentnet", "-d", "agentnet",
             "-tAc", "SELECT COUNT(*) FROM messages WHERE created_at > now() - interval '10 minutes'"],
            capture_output=True, text=True, timeout=10
        )
        msg_count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else -1
    except Exception:
        pass

    print(f"\n--- DB Consistency ---")
    print(f"Tasks before/after: {tasks_before} / {tasks_after} (delta: {delta})")
    print(f"Messages created (last 10min): {msg_count}")
    print(f"Task IDs collected: {len(stats.task_ids)}")
    if delta >= len(stats.task_ids):
        print("PASS: task count matches")
    else:
        print(f"WARN: delta {delta} < {len(stats.task_ids)}")

    # Verdict
    print(f"\n--- VERDICT ---")
    passed = True
    if err_rate > 1: print(f"FAIL: error rate {err_rate:.1f}%"); passed = False
    if p99 > 5.0: print(f"FAIL: P99 {p99*1000:.0f}ms"); passed = False
    if len(stats.task_ids) < NUM_TASKS * 0.99: print(f"FAIL: success rate"); passed = False
    if passed:
        print(f"PASS: {len(stats.task_ids)}/{NUM_TASKS} tasks, err={err_rate:.1f}%, "
              f"P50={p50*1000:.0f}ms P95={p95*1000:.0f}ms P99={p99*1000:.0f}ms")


if __name__ == "__main__":
    main()
