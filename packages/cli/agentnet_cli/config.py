"""Local config manager: reads/writes ~/.agentnet/config.json."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any


class ConfigManager:
    """Manages the agentnet CLI configuration file.

    Config file location: ~/.agentnet/config.json
    File permissions: 0o600 (owner-only r/w) on Unix.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path or Path.home() / ".agentnet" / "config.json")

    @property
    def path(self) -> Path:
        return self._path

    def _ensure_dir(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Set dir permissions too (0o700 owner-only)
        try:
            os.chmod(self._path.parent, stat.S_IRWXU)
        except OSError:
            pass  # Ignore on Windows / permission-restricted environments

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            return json.loads(self._path.read_text(encoding="utf-8"))
        return {}

    def _save(self, data: dict[str, Any]) -> None:
        self._ensure_dir()
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # Restrict to owner-only (0o600)
        try:
            os.chmod(self._path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass  # Ignore on Windows

    # ------------------------------------------------------------------
    # high-level keys
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self._load().get(key, default)

    def set(self, key: str, value: Any) -> None:
        data = self._load()
        data[key] = value
        self._save(data)

    def all(self) -> dict[str, Any]:
        return self._load()

    # ------------------------------------------------------------------
    # convenience
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        return self.get("base_url", "http://localhost:8000")

    @base_url.setter
    def base_url(self, value: str) -> None:
        self.set("base_url", value)

    @property
    def api_key(self) -> str:
        return self.get("api_key", "")

    @api_key.setter
    def api_key(self, value: str) -> None:
        self.set("api_key", value)

    @property
    def agent_token(self) -> str:
        return self.get("agent_token", "")

    @agent_token.setter
    def agent_token(self, value: str) -> None:
        self.set("agent_token", value)

    def set_credentials(self, base_url: str, api_key: str) -> None:
        data = self._load()
        data["base_url"] = base_url
        data["api_key"] = api_key
        self._save(data)
