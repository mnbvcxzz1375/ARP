#!/usr/bin/env python3
"""
Test data cleanup script for AgentNet E2E testing.
Purges test users, agents, tasks created by the e2e_test_runner.py.

Usage:
    python scripts/cleanup_test_data.py          # dry-run (list what would be deleted)
    python scripts/cleanup_test_data.py --run    # actually delete
    python scripts/cleanup_test_data.py --users-only  # only clean test users
"""
import argparse
import os
import sys

import httpx

API_BASE = os.getenv("AGENTNET_API_BASE", "http://localhost:8000")

# Test users have usernames matching these prefixes
TEST_PREFIXES = [
    "crash-test-", "offline-test-", "approval-test-", "approval-list-",
    "rotate-test-", "sec-user-", "long-output-", "unicode-test-",
    "codeblock-", "rapid-", "concurrent-", "hb-test-",
    "dedup-", "model-fail-", "nonzero-", "crash-timeout-",
    "long-stab-", "resume-test-", "e2e-", "ws-e2e-",
    "edge-debug-", "edge-test-", "rapid-check-", "rapid-test-",
    "rate-test-",
]


def main():
    parser = argparse.ArgumentParser(description="Clean up AgentNet test data")
    parser.add_argument("--run", action="store_true", help="Actually delete (default: dry-run)")
    parser.add_argument("--users-only", action="store_true", help="Only clean users")
    args = parser.parse_args()

    session = httpx.Client(base_url=API_BASE, timeout=30)

    # Step 1: Register a fresh admin user to do the cleanup
    print("[CLEANUP] Step 1: Bootstrapping admin user")
    import uuid
    reg = session.post("/v1/auth/register", json={
        "username": f"cleanup-admin-{uuid.uuid4().hex[:6]}",
        "key_name": "cleanup",
    })
    if reg.status_code != 200:
        print(f"[CLEANUP] Failed to register admin: {reg.status_code}")
        sys.exit(1)
    admin = reg.json()
    admin_key = admin["api_key"]
    admin_headers = {"Authorization": f"Bearer {admin_key}"}
    print(f"[CLEANUP] Admin user: {admin['username']}")

    # Step 2: Scan for test agents
    print("[CLEANUP] Step 2: Scanning for test agents")
    test_agents = []
    page = 1
    while True:
        resp = session.get(f"/v1/agents?page={page}&page_size=100", headers=admin_headers)
        if resp.status_code != 200:
            print(f"[CLEANUP] Agent list failed: {resp.status_code}")
            break
        data = resp.json()
        agents = data.get("agents", [])
        for agent in agents:
            name = agent.get("name", "")
            if any(name.startswith(p) or "test" in name.lower() or "Test" in name
                   or "Agent" in name for p in TEST_PREFIXES):
                test_agents.append(agent)
        if len(agents) < 100:
            break
        page += 1

    print(f"[CLEANUP] Found {len(test_agents)} test agents")

    # Step 3: Delete each test agent (cascades to tokens, tasks, messages)
    if args.run:
        print("[CLEANUP] Step 3: Deleting test agents")
        deleted = 0
        for agent in test_agents:
            agent_id = agent["agent_id"]
            resp = session.delete(f"/v1/agents/{agent_id}", headers=admin_headers)
            if resp.status_code == 204:
                deleted += 1
            else:
                print(f"  [WARN] Failed to delete {agent_id}: {resp.status_code}")
        print(f"[CLEANUP] Deleted {deleted}/{len(test_agents)} test agents")
    else:
        print("[CLEANUP] Step 3 (dry-run): would delete these agents:")
        for agent in test_agents[:10]:
            print(f"  - {agent['name']} ({agent['agent_id'][:12]}...)")
        if len(test_agents) > 10:
            print(f"  ... and {len(test_agents) - 10} more")

    # Step 4: Clean API keys for the main test user
    if not args.users_only:
        print("[CLEANUP] Step 4: Checking API key count")
        # Use the main API key to list its own keys
        main_headers = {
            "Authorization": "Bearer ak_Bg95_c11p9ZRkqJe5CR5wRKvjTukOVJ8VYck3SGZ9HI",
        }
        resp = session.get("/v1/auth/api-keys", headers=main_headers)
        if resp.status_code == 200:
            keys = resp.json()
            total = keys.get("total", 0)
            print(f"[CLEANUP] Main user has {total} API keys")
            if total > 5:
                print("[CLEANUP] Consider manually pruning old keys via /v1/auth/api-keys/{id}/revoke")

    # Tear down: delete the cleanup admin
    if args.run:
        print("[CLEANUP] Step 5: Removing cleanup admin agent")
        resp = session.get("/v1/agents", headers=admin_headers)
        if resp.status_code == 200:
            agents = resp.json().get("agents", [])
            for a in agents:
                session.delete(f"/v1/agents/{a['agent_id']}", headers=admin_headers)

    print("[CLEANUP] Done.")
    if not args.run:
        print("[CLEANUP] Re-run with --run to actually delete.")


if __name__ == "__main__":
    main()
