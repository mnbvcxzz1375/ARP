#!/usr/bin/env python3
"""Validate Prometheus and Alertmanager configuration for AgentNet.

Usage:
    python validate_observability.py [--allow-skips] [--webhook-url URL] [--self-test-alertmanager]

Checks:
    1. Prometheus config is valid YAML
    2. Alert rules are valid YAML
    3. Alertmanager config is valid YAML
    4. promtool check (via Docker with --entrypoint)
    5. amtool check (via Docker with --entrypoint)
    6. Test notification via --webhook-url (direct POST)
    7. Alertmanager self-test (--self-test-alertmanager):
       - Starts a local HTTP webhook receiver
       - Launches a temporary Alertmanager container pointing at it
       - Sends a synthetic alert and waits for the webhook to fire
       - PASS only if the notification is actually received

Exit codes:
    0  All checks PASSED (skips only count with --allow-skips)
    1  One or more checks FAILED or incompletable
"""
from __future__ import annotations

import hashlib
import http.server
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INFRA_DIR = PROJECT_ROOT / "infra"

PROMETHEUS_CONFIG = INFRA_DIR / "prometheus" / "prometheus.yml"
ALERT_RULES_DIR = INFRA_DIR / "prometheus" / "alerts"
ALERTMANAGER_CONFIG = INFRA_DIR / "alertmanager" / "alertmanager.yml"

# Track all results for final verdict
results: list[tuple[str, str, str]] = []  # (name, status, detail)


def _status(check: str, status: str, detail: str = ""):
    icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "⊘", "WARN": "⚠", "ERROR": "!"}.get(status, "?")
    print(f"  {icon} {check}: {status}")
    if detail:
        for line in detail.strip().splitlines():
            print(f"      {line}")
    results.append((check, status, detail))


def validate_yaml(path: Path, name: str) -> bool:
    """Validate YAML is parseable."""
    if not path.exists():
        _status(name, "FAIL", f"File not found: {path}")
        return False
    try:
        import yaml
        with open(path) as f:
            yaml.safe_load(f)
        _status(name, "PASS")
        return True
    except Exception as e:
        _status(name, "FAIL", str(e))
        return False


def validate_alert_rules() -> bool:
    """Validate all alert rule files are valid YAML."""
    if not ALERT_RULES_DIR.exists():
        _status("Alert rules directory", "FAIL", f"Directory not found: {ALERT_RULES_DIR}")
        return False

    rule_files = list(ALERT_RULES_DIR.glob("*.yml")) + list(ALERT_RULES_DIR.glob("*.yaml"))
    if not rule_files:
        _status("Alert rules", "FAIL", "No rule files found in alerts directory")
        return False

    import yaml
    all_ok = True
    for rf in rule_files:
        try:
            with open(rf) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict) or "groups" not in data:
                _status(f"Alert file: {rf.name}", "FAIL", "Missing 'groups' key")
                all_ok = False
            else:
                rule_count = sum(len(g.get("rules", [])) for g in data["groups"])
                _status(f"Alert file: {rf.name}", "PASS", f"{rule_count} rules")
        except Exception as e:
            _status(f"Alert file: {rf.name}", "FAIL", str(e))
            all_ok = False
    return all_ok


def check_promtool() -> bool:
    """Run promtool check via Docker with --entrypoint."""
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--entrypoint", "promtool",
                "-v", f"{PROMETHEUS_CONFIG}:/etc/prometheus/prometheus.yml:ro",
                "-v", f"{ALERT_RULES_DIR}:/etc/prometheus/alerts:ro",
                "prom/prometheus:v2.55.1",
                "check", "config", "/etc/prometheus/prometheus.yml",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            _status("promtool check config", "PASS", result.stdout.strip() or "OK")
            return True
        else:
            _status("promtool check config", "FAIL", result.stderr.strip() or result.stdout.strip())
            return False
    except FileNotFoundError:
        _status("promtool check config", "FAIL", "Docker not available — cannot run promtool")
        return False
    except subprocess.TimeoutExpired:
        _status("promtool check config", "FAIL", "Docker timeout — cannot run promtool")
        return False
    except Exception as e:
        _status("promtool check config", "ERROR", str(e))
        return False


def check_amtool() -> bool:
    """Run amtool check via Docker with --entrypoint."""
    if not ALERTMANAGER_CONFIG.exists():
        _status("amtool check config", "FAIL", "Alertmanager config not found")
        return False

    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--entrypoint", "amtool",
                "-v", f"{ALERTMANAGER_CONFIG}:/etc/alertmanager/alertmanager.yml:ro",
                "prom/alertmanager:v0.27.0",
                "check-config", "/etc/alertmanager/alertmanager.yml",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            _status("amtool check config", "PASS")
            return True
        else:
            _status("amtool check config", "FAIL", result.stderr.strip() or result.stdout.strip())
            return False
    except FileNotFoundError:
        _status("amtool check config", "FAIL", "Docker not available — cannot run amtool")
        return False
    except subprocess.TimeoutExpired:
        _status("amtool check config", "FAIL", "Docker timeout — cannot run amtool")
        return False
    except Exception as e:
        _status("amtool check config", "ERROR", str(e))
        return False


def test_notification(webhook_url: str) -> bool:
    """Send a test alert to the webhook URL."""
    try:
        import httpx
        payload = {
            "receiver": "test",
            "status": "firing",
            "alerts": [{
                "status": "firing",
                "labels": {"alertname": "TestAlert", "severity": "warning"},
                "annotations": {"summary": "AgentNet observability test notification"},
            }],
        }
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        if 200 <= resp.status_code < 300:
            _status("Test notification (webhook-url)", "PASS", f"Webhook responded {resp.status_code}")
            return True
        else:
            _status("Test notification (webhook-url)", "FAIL", f"Webhook responded {resp.status_code}")
            return False
    except ImportError:
        _status("Test notification (webhook-url)", "FAIL", "httpx not installed — cannot send notification test")
        return False
    except Exception as e:
        _status("Test notification (webhook-url)", "FAIL", str(e))
        return False


# ---------------------------------------------------------------------------
# Alertmanager self-test: spin up a local webhook receiver + temporary
# Alertmanager container, send a synthetic alert, and verify delivery.
# ---------------------------------------------------------------------------

class _WebhookHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that records POST bodies for the self-test."""

    received: list[bytes] = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _WebhookHandler.received.append(body)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silence request logging


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("0.0.0.0", 0))
        return s.getsockname()[1]


def _docker_host_address() -> str:
    """Return the address the Docker container should use to reach the host.

    On Windows Docker Desktop, host.docker.internal resolves to the host.
    On Linux, it may not exist without extra Docker config.
    We verify reachability — if it doesn't work, we FAIL rather than skip.
    """
    return "host.docker.internal"


def _wait_for_url(url: str, timeout_s: float = 20, interval_s: float = 1) -> bool:
    """Poll a URL until it returns 200 or timeout."""
    import httpx
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(url, timeout=3)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(interval_s)
    return False


def self_test_alertmanager() -> bool:
    """End-to-end Alertmanager notification self-test.

    1. Start a local HTTP webhook receiver on a random port.
    2. Write a temporary alertmanager.yml pointing at it.
    3. docker run a temporary Alertmanager container.
    4. POST a synthetic alert via the Alertmanager API.
    5. Wait for the webhook receiver to get the notification.
    6. Clean up everything.
    """
    _WebhookHandler.received = []

    port = _find_free_port()
    host_addr = _docker_host_address()
    webhook_target = f"http://{host_addr}:{port}/alertmanager-webhook"

    # 1. Start local webhook receiver
    server = http.server.HTTPServer(("0.0.0.0", port), _WebhookHandler)
    server.timeout = 1  # so serve_forever can be interrupted
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # 2. Write temporary alertmanager.yml
    tmp_dir = tempfile.mkdtemp(prefix="agentnet_am_test_")
    am_config_path = os.path.join(tmp_dir, "alertmanager.yml")
    am_config_content = (
        "global:\n"
        "  resolve_timeout: 5s\n"
        "route:\n"
        "  receiver: 'selftest'\n"
        "  group_wait: 1s\n"
        "  group_interval: 1s\n"
        "  repeat_interval: 1s\n"
        "receivers:\n"
        f"  - name: 'selftest'\n"
        f"    webhook_configs:\n"
        f"      - url: '{webhook_target}'\n"
        f"        send_resolved: true\n"
    )
    with open(am_config_path, "w") as f:
        f.write(am_config_content)

    container_name = f"agentnet-am-selftest-{os.getpid()}"
    am_port = _find_free_port()

    try:
        # 3. Start Alertmanager container
        # Convert Windows path for Docker volume mount
        am_config_docker = am_config_path.replace("\\", "/")
        # On Windows with Docker Desktop, we may need to adjust the path
        if os.name == "nt":
            # Docker Desktop on Windows can handle Windows paths in -v
            am_config_docker = am_config_path

        run_result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", container_name,
                "-p", f"127.0.0.1:{am_port}:9093",
                "-v", f"{am_config_docker}:/etc/alertmanager/alertmanager.yml:ro",
                "prom/alertmanager:v0.27.0",
                "--config.file=/etc/alertmanager/alertmanager.yml",
                "--storage.path=/alertmanager",
                "--log.level=debug",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if run_result.returncode != 0:
            _status("Alertmanager self-test", "FAIL",
                    f"docker run failed: {run_result.stderr.strip()}")
            return False

        # 4. Wait for Alertmanager to be ready
        am_url = f"http://127.0.0.1:{am_port}"
        if not _wait_for_url(f"{am_url}/api/v2/status", timeout_s=25):
            _status("Alertmanager self-test", "FAIL",
                    "Alertmanager container did not become ready in time")
            return False

        # 5. Send synthetic alert
        import httpx
        alert_payload = [
            {
                "labels": {
                    "alertname": "AgentNetValidationAlert",
                    "severity": "critical",
                    "source": "validate_observability.py",
                },
                "annotations": {
                    "summary": "Synthetic alert from AgentNet observability validation",
                },
                "startsAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ]
        try:
            resp = httpx.post(
                f"{am_url}/api/v2/alerts",
                json=alert_payload,
                timeout=10,
            )
            if resp.status_code not in (200, 201, 202):
                _status("Alertmanager self-test", "FAIL",
                        f"POST /api/v2/alerts returned {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            _status("Alertmanager self-test", "FAIL",
                    f"Failed to POST alert to Alertmanager: {e}")
            return False

        # 6. Wait for webhook to receive the notification
        deadline = time.monotonic() + 20
        received = False
        while time.monotonic() < deadline:
            if _WebhookHandler.received:
                received = True
                break
            time.sleep(0.5)

        if received:
            body = _WebhookHandler.received[0]
            try:
                data = json.loads(body)
                alert_names = [
                    a.get("labels", {}).get("alertname", "")
                    for a in data.get("alerts", [])
                ]
                _status("Alertmanager self-test", "PASS",
                        f"Webhook received notification with alerts: {alert_names}")
            except Exception:
                _status("Alertmanager self-test", "PASS",
                        "Webhook received notification (could not parse body)")
            return True
        else:
            _status("Alertmanager self-test", "FAIL",
                    "Webhook did not receive notification within 20s. "
                    "Alertmanager may not be able to reach host.docker.internal — "
                    "check Docker Desktop networking.")
            return False

    except FileNotFoundError:
        _status("Alertmanager self-test", "FAIL", "Docker not available — cannot run self-test")
        return False
    except subprocess.TimeoutExpired:
        _status("Alertmanager self-test", "FAIL", "Docker command timed out")
        return False
    except Exception as e:
        _status("Alertmanager self-test", "ERROR", str(e))
        return False
    finally:
        # 7. Cleanup
        server.shutdown()
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True, timeout=10,
        )
        try:
            os.remove(am_config_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


def main():
    allow_skips = "--allow-skips" in sys.argv
    webhook_url = ""
    if "--webhook-url" in sys.argv:
        idx = sys.argv.index("--webhook-url")
        if idx + 1 < len(sys.argv):
            webhook_url = sys.argv[idx + 1]
    self_test = "--self-test-alertmanager" in sys.argv

    print(f"\n{'='*60}")
    print("AgentNet Observability Validation")
    print(f"{'='*60}\n")

    # 1. Validate YAML configs
    print("Configuration files:")
    validate_yaml(PROMETHEUS_CONFIG, "Prometheus config")
    validate_yaml(ALERTMANAGER_CONFIG, "Alertmanager config")
    validate_alert_rules()

    # 2. promtool / amtool checks
    print("\nTool-based validation:")
    check_promtool()
    check_amtool()

    # 3. Notification tests
    print("\nNotification test:")
    if webhook_url:
        test_notification(webhook_url)
    else:
        _status("Test notification (webhook-url)", "FAIL",
                "No --webhook-url provided. Direct webhook delivery is UNVERIFIED.")

    if self_test:
        print("\nAlertmanager self-test:")
        self_test_alertmanager()
    else:
        _status("Alertmanager self-test", "FAIL",
                "No --self-test-alertmanager flag. Alertmanager notification delivery is UNVERIFIED.\n"
                "To test end-to-end notification delivery:\n"
                "  python scripts/validation/validate_observability.py --self-test-alertmanager\n"
                "Without this, alert delivery cannot be confirmed.")

    # Summary
    print(f"\n{'='*60}")

    pass_count = sum(1 for _, s, _ in results if s == "PASS")
    fail_count = sum(1 for _, s, _ in results if s == "FAIL")
    skip_count = sum(1 for _, s, _ in results if s == "SKIP")
    error_count = sum(1 for _, s, _ in results if s == "ERROR")

    print(f"  Summary: {pass_count} passed, {fail_count} failed, {skip_count} skipped, {error_count} errors")

    if fail_count > 0:
        print("  VERIFICATION FAILED — one or more checks did not pass.")
        print(f"{'='*60}\n")
        sys.exit(1)

    if skip_count > 0 or error_count > 0:
        if allow_skips:
            print("  VERIFICATION PASSED (with skips) — all executed checks passed, some were skipped with --allow-skips.")
            print(f"{'='*60}\n")
            sys.exit(0)
        else:
            print("  VERIFICATION INCOMPLETE — some checks were skipped or errored. Use --allow-skips to treat these as non-blocking.")
            print(f"{'='*60}\n")
            sys.exit(1)

    print("  All checks PASSED.")
    print(f"{'='*60}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
