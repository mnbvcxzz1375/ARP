#!/usr/bin/env python3
"""Verify HTTPS and WSS connectivity for an AgentNet deployment.

Usage:
    python verify_https_wss.py --domain andrewhyc.top [--ws-path /v1/ws] [--skip-wss] [--timeout 10]

Exit codes:
    0  All checks PASSED
    1  One or more checks FAILED (or SKIP without --allow-skips)
"""
from __future__ import annotations

import argparse
import os
import ssl
import sys
import urllib.request
import urllib.error
import json
from dataclasses import dataclass, field
from typing import Optional

WS_PATH_DEFAULT = "/v1/ws"


@dataclass
class CheckResult:
    name: str
    status: str  # PASS, FAIL, SKIP, POLICY_SKIP
    detail: str = ""
    raw_status: Optional[int] = None


def _make_result(name: str, status: str, detail: str, raw_status: Optional[int] = None) -> CheckResult:
    return CheckResult(name=name, status=status, detail=detail, raw_status=raw_status)


def check_https(domain: str, timeout: int) -> CheckResult:
    """Verify HTTPS is reachable and returns a valid response."""
    url = f"https://{domain}/healthz"
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            if status == 200:
                return _make_result("HTTPS /healthz", "PASS", f"HTTP {status}", raw_status=status)
            else:
                # 2xx but not 200 — unusual but not necessarily broken
                if 200 <= status < 300:
                    return _make_result("HTTPS /healthz", "PASS", f"HTTP {status}", raw_status=status)
                # 404, 403, 5xx — these are failures, not passes
                return _make_result("HTTPS /healthz", "FAIL", f"HTTP {status} — endpoint returned non-success", raw_status=status)
    except urllib.error.HTTPError as e:
        # 404, 403, etc from the server — these are FAIL, not PASS
        return _make_result("HTTPS /healthz", "FAIL", f"HTTP {e.code} — endpoint returned error", raw_status=e.code)
    except ssl.SSLCertVerificationError as e:
        return _make_result("HTTPS /healthz", "FAIL", f"TLS certificate error: {e}")
    except ssl.SSLError as e:
        return _make_result("HTTPS /healthz", "FAIL", f"TLS error: {e}")
    except urllib.error.URLError as e:
        return _make_result("HTTPS /healthz", "FAIL", f"Connection error: {e.reason}")
    except Exception as e:
        return _make_result("HTTPS /healthz", "FAIL", f"Unexpected error: {e}")


def check_tls_version(domain: str, timeout: int) -> CheckResult:
    """Verify TLS 1.2+ is negotiated."""
    try:
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        req = urllib.request.Request(f"https://{domain}/healthz", method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            # Check the actual TLS version negotiated
            return _make_result("TLS Version", "PASS", "TLS 1.2+ negotiated")
    except ssl.SSLCertVerificationError as e:
        return _make_result("TLS Version", "FAIL", f"Certificate error: {e}")
    except ssl.SSLError as e:
        return _make_result("TLS Version", "FAIL", f"TLS negotiation failed: {e}")
    except Exception as e:
        return _make_result("TLS Version", "FAIL", f"Error: {e}")


def check_healthz_content(domain: str, timeout: int) -> CheckResult:
    """Verify /healthz returns valid JSON with status information."""
    url = f"https://{domain}/healthz"
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status != 200:
                return _make_result("Healthz Content", "FAIL", f"HTTP {resp.status}", raw_status=resp.status)
            body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
                if isinstance(data, dict) and ("status" in data or "healthy" in data):
                    return _make_result("Healthz Content", "PASS", "Valid health JSON response")
                else:
                    return _make_result("Healthz Content", "FAIL", f"JSON response missing status field: {body[:200]}")
            except json.JSONDecodeError:
                return _make_result("Healthz Content", "FAIL", f"Response is not valid JSON: {body[:200]}")
    except urllib.error.HTTPError as e:
        return _make_result("Healthz Content", "FAIL", f"HTTP {e.code}", raw_status=e.code)
    except Exception as e:
        return _make_result("Healthz Content", "FAIL", f"Error: {e}")


def check_wss(domain: str, ws_path: str, timeout: int) -> CheckResult:
    """Verify WSS endpoint is reachable (basic TLS + upgrade check)."""
    try:
        import websocket
        ws_url = f"wss://{domain}{ws_path}"
        # Attempt connection — we expect a 401/403 (no auth) or successful upgrade
        # Either way confirms WSS endpoint is reachable
        try:
            ws = websocket.create_connection(ws_url, timeout=timeout)
            ws.close()
            return _make_result("WSS Endpoint", "PASS", f"WSS {ws_path} reachable and upgraded")
        except websocket.WebSocketBadStatusException as e:
            code = getattr(e, "status_code", 0) or 0
            # 401/403 prove the WSS endpoint exists and requires auth
            if code in (401, 403):
                return _make_result("WSS Endpoint", "PASS", f"WSS {ws_path} reachable (HTTP {code}, auth required)")
            # 404 means the endpoint does not exist
            if code == 404:
                return _make_result("WSS Endpoint", "FAIL", f"WSS {ws_path} not found (HTTP 404)")
            # Other 4xx/5xx are failures
            return _make_result("WSS Endpoint", "FAIL", f"WSS {ws_path} failed: HTTP {code}")
        except (ssl.SSLError, OSError) as e:
            return _make_result("WSS Endpoint", "FAIL", f"WSS {ws_path} error: {e}")
        except websocket.WebSocketException as e:
            return _make_result("WSS Endpoint", "FAIL", f"WSS {ws_path} error: {e}")
    except ImportError:
        return _make_result("WSS Endpoint", "SKIP", "websocket-client not installed; pip install websocket-client")


def check_readyz(domain: str, timeout: int) -> CheckResult:
    """Verify /readyz deep health check returns 200 with dependency info."""
    url = f"https://{domain}/readyz"
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status == 200:
                return _make_result("HTTPS /readyz", "PASS", f"HTTP {resp.status}", raw_status=resp.status)
            else:
                return _make_result("HTTPS /readyz", "FAIL", f"HTTP {resp.status} — readiness check failed", raw_status=resp.status)
    except urllib.error.HTTPError as e:
        return _make_result("HTTPS /readyz", "FAIL", f"HTTP {e.code}", raw_status=e.code)
    except Exception as e:
        return _make_result("HTTPS /readyz", "FAIL", f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Verify HTTPS/WSS for an AgentNet deployment")
    parser.add_argument("--domain", required=True, help="Domain to verify (e.g. andrewhyc.top)")
    parser.add_argument("--ws-path", default=os.environ.get("WS_PATH", WS_PATH_DEFAULT),
                        help=f"WSS path (default: {WS_PATH_DEFAULT}, env: WS_PATH)")
    parser.add_argument("--skip-wss", action="store_true", help="Skip WSS checks")
    parser.add_argument("--allow-skips", action="store_true",
                        help="Treat SKIP results as non-blocking (exit 0 if only skips)")
    parser.add_argument("--timeout", type=int, default=10, help="HTTP timeout in seconds")
    args = parser.parse_args()

    domain = args.domain
    if not domain:
        parser.error("--domain is required")

    results: list[CheckResult] = []

    # HTTPS checks
    results.append(check_https(domain, args.timeout))
    results.append(check_tls_version(domain, args.timeout))
    results.append(check_healthz_content(domain, args.timeout))
    results.append(check_readyz(domain, args.timeout))

    # WSS check
    if args.skip_wss:
        results.append(_make_result("WSS Endpoint", "POLICY_SKIP", "Skipped via --skip-wss"))
    else:
        results.append(check_wss(domain, args.ws_path, args.timeout))

    # Print results
    print(f"\n{'Check':<30} {'Status':<12} Detail")
    print("-" * 72)
    has_fail = False
    has_skip = False
    for r in results:
        print(f"{r.name:<30} {r.status:<12} {r.detail}")
        if r.status == "FAIL":
            has_fail = True
        if r.status == "SKIP":
            has_skip = True

    # Exit code logic
    if has_fail:
        print("\nVERIFICATION FAILED — one or more checks did not pass.")
        sys.exit(1)
    if has_skip and not args.allow_skips:
        print("\nVERIFICATION INCOMPLETE — some checks were skipped. Use --allow-skips to treat skips as non-blocking.")
        sys.exit(1)
    if has_skip and args.allow_skips:
        print("\nVERIFICATION PASSED (with skips) — all executed checks passed, some were skipped with --allow-skips.")
        sys.exit(0)
    print("\nVERIFICATION PASSED — all checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
