"""Example: Send a task to an agent and poll for the result.

Usage:
  set AGENTNET_API_KEY=an_key_...
  set AGENTNET_BASE_URL=http://localhost:8000
  python examples/send_task.py <agent_number>
"""

import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentnet import Client, AgentNetError


def main():
    if len(sys.argv) < 2:
        print("Usage: python send_task.py <agent_number>")
        sys.exit(1)

    agent_number = sys.argv[1]

    client = Client.from_env()

    print(f"Creating task for agent {agent_number}...")
    try:
        task = client.create_task(
            assigned_to=agent_number,
            payload={"message": "Hello from send_task.py!", "ts": time.time()},
        )
        task_id = task["task_id"]
        print(f"Task created: {task_id} (status={task['status']})")

        # Poll for result
        print("Waiting for result...")
        for i in range(60):
            time.sleep(1)
            updated = client.get_task(task_id)
            status = updated.get("status")
            print(f"  [{i+1}s] status={status}", flush=True)

            if status == "completed":
                print(f"\nResult: {updated.get('result')}")
                break
            elif status in ("failed", "cancelled", "rejected", "expired"):
                print(f"\nTask ended: {status} — {updated.get('error_message', 'no message')}")
                break
        else:
            print("\nTimed out waiting for result.")

        # Show progress history
        progress = client.get_task_progress(task_id)
        print(f"\nProgress entries: {progress.get('total', 0)}")
        for entry in progress.get("entries", [])[:5]:
            print(f"  seq={entry['seq']}: {entry.get('message', '')} ({entry.get('progress_pct', '?')}%)")

    except AgentNetError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
