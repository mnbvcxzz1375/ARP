"""Safety checks: path traversal detection, deny-path enforcement, env sanitization, command review."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

SENSITIVE_ENV_KEYS: set[str] = {
    "API_KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD",
    "AWS_ACCESS_KEY", "AWS_SECRET_KEY", "AWS_SESSION_TOKEN",
    "AZURE_CLIENT_SECRET", "GCP_SA_KEY",
    "DOCKER_AUTH", "KUBECONFIG",
    "SSH_KEY", "PRIVATE_KEY",
    "AGENTNET_API_KEY", "AGENTNET_AGENT_TOKEN",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "GITHUB_TOKEN", "GITLAB_TOKEN",
    "DATABASE_URL", "REDIS_URL", "RABBITMQ_URL",
}

SENSITIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r".*_KEY$", re.IGNORECASE),
    re.compile(r".*_SECRET$", re.IGNORECASE),
    re.compile(r".*_TOKEN$", re.IGNORECASE),
    re.compile(r".*_PASSWORD$", re.IGNORECASE),
    re.compile(r".*_PASSWD$", re.IGNORECASE),
]

DANGEROUS_COMMAND_PATTERNS: list[re.Pattern] = [
    re.compile(r"rm\s+-rf\s+/[^\s]*", re.IGNORECASE),
    re.compile(r"sudo\s+", re.IGNORECASE),
    re.compile(r"chmod\s+777", re.IGNORECASE),
    re.compile(r">\s*/dev/", re.IGNORECASE),
    re.compile(r"mkfs\.", re.IGNORECASE),
    re.compile(r"dd\s+if=", re.IGNORECASE),
    re.compile(r":\{\|:&", re.IGNORECASE),  # fork bomb
]


class SafetyError(Exception):
    """Raised when a safety check fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


# ------------------------------------------------------------------
# path safety
# ------------------------------------------------------------------


def resolve_safe(path: str, allow_paths: list[str], deny_paths: list[str]) -> Path:
    """Resolve *path* and verify it is within allowed directories.

    Raises SafetyError if:
      - path does not resolve within any allow_path
      - resolved path is within any deny_path
      - path contains traversal attempts
    """
    raw = Path(path)
    resolved = raw.resolve()

    # Check deny paths first (takes priority)
    for deny in deny_paths:
        deny_resolved = Path(deny).resolve()
        try:
            resolved.relative_to(deny_resolved)
            raise SafetyError(f"Path '{path}' is denied (matches deny-path '{deny}')")
        except ValueError:
            pass

    # Check allow paths
    allowed = False
    for allow in allow_paths:
        allow_resolved = Path(allow).resolve()
        try:
            resolved.relative_to(allow_resolved)
            allowed = True
            break
        except ValueError:
            pass

    if not allowed:
        raise SafetyError(
            f"Path '{path}' resolves to '{resolved}' which is not within any allowed path"
        )

    return resolved


def check_path_traversal(path: str) -> bool:
    """Return True if *path* contains traversal patterns like ../ or ..\\"""
    traversal_patterns = [r"\.\./", r"\.\.\\", r"\.\\./", r"\.\\.\\"]
    for pattern in traversal_patterns:
        if re.search(pattern, path):
            return True
    return False


# ------------------------------------------------------------------
# env isolation
# ------------------------------------------------------------------


def sanitize_env(
    env: dict[str, str] | None = None,
    pass_env: list[str] | None = None,
) -> dict[str, str]:
    """Build a minimal subprocess environment.

    Only passes:
      - Whitelisted env vars specified in *pass_env*
      - OS-critical vars: PATH, HOME, USER, TEMP, SYSTEMROOT

    Strips all sensitive keys (API keys, tokens, passwords).

    If *env* is given, applies additional key=value overrides.
    """
    pass_env = pass_env or []
    safe: dict[str, str] = {}

    # OS-critical vars
    for key in ("PATH", "HOME", "USER", "USERNAME", "TEMP", "TMP",
                "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "SHELL",
                "LANG", "LC_ALL"):
        val = os.environ.get(key)
        if val:
            safe[key] = val

    # Whitelisted
    for key in pass_env:
        if is_sensitive_env_key(key):
            continue
        val = os.environ.get(key)
        if val:
            safe[key] = val

    # Explicit overrides (filter sensitive keys)
    if env:
        for k, v in env.items():
            if is_sensitive_env_key(k):
                continue
            safe[k] = v

    return safe


def is_sensitive_env_key(key: str) -> bool:
    """Check if an environment variable key is sensitive."""
    if key.upper() in SENSITIVE_ENV_KEYS:
        return True
    for pattern in SENSITIVE_PATTERNS:
        if pattern.match(key):
            return True
    return False


# ------------------------------------------------------------------
# command review
# ------------------------------------------------------------------


def review_command(command: list[str]) -> list[str]:
    """Check *command* for dangerous patterns.

    Returns a list of reasons why the command is dangerous.
    Empty list means the command passes review.
    """
    reasons: list[str] = []
    cmd_str = " ".join(command)

    for pattern in DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(cmd_str):
            reasons.append(f"Command matches dangerous pattern: {pattern.pattern}")

    return reasons


# ------------------------------------------------------------------
# output truncation
# ------------------------------------------------------------------


def truncate_output(data: bytes | str, max_bytes: int) -> tuple[bytes | str, bool]:
    """Truncate *data* to *max_bytes*. Returns (truncated, was_truncated)."""
    if isinstance(data, str):
        encoded = data.encode("utf-8", errors="replace")
        if len(encoded) <= max_bytes:
            return data, False
        truncated = encoded[:max_bytes].decode("utf-8", errors="replace")
        return truncated, True
    else:
        if len(data) <= max_bytes:
            return data, False
        return data[:max_bytes], True
