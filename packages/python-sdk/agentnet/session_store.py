"""Local session store: persists last_message_id and running_tasks to a JSON file."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SessionStore:
    """Persistent local session state stored as a plain JSON file.

    Tracks:
      - session_id        -> stable session identifier for resume
      - last_message_id   -> most recently acked/payload message id
      - running_tasks     -> dict of task_id -> task metadata kwargs
      - peer_keys         -> dict of peer_id -> KEM public key fingerprint
      - session_key_handles -> dict of peer_id -> handle of this side's
                               local private key material

    Key state (E2EE, M1): only fingerprints and opaque handles are
    persisted — never private key material itself. A handle is an
    application-defined reference (env var name, file path, KMS key id)
    to where this side's private key lives.

    Thread-safe enough for single-agent usage; not meant for concurrent writes.
    """

    def __init__(self, file_path: str | Path) -> None:
        self._path = Path(file_path)
        self._data: dict[str, Any] = {
            "session_id": None,
            "last_message_id": None,
            "running_tasks": {},
            "peer_keys": {},
            "session_key_handles": {},
        }

    # ------------------------------------------------------------------
    # persistence helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._path.exists():
            raw = self._path.read_text(encoding="utf-8")
            if raw.strip():
                loaded = json.loads(raw)
                self._data["session_id"] = loaded.get("session_id")
                self._data["last_message_id"] = loaded.get("last_message_id")
                self._data["running_tasks"] = loaded.get("running_tasks", {})
                self._data["peer_keys"] = loaded.get("peer_keys", {})
                self._data["session_key_handles"] = loaded.get(
                    "session_key_handles", {}
                )

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def open(self) -> None:
        """Load state from disk. Safe to call multiple times."""
        self._load()

    def close(self) -> None:
        self._save()

    # ------------------------------------------------------------------
    # session_id
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str | None:
        return self._data.get("session_id")

    def set_session_id(self, session_id: str) -> None:
        self._data["session_id"] = session_id
        self._save()

    # ------------------------------------------------------------------
    # last_message_id
    # ------------------------------------------------------------------

    @property
    def last_message_id(self) -> str | None:
        return self._data.get("last_message_id")

    def set_last_message_id(self, message_id: str) -> None:
        self._data["last_message_id"] = message_id
        self._save()

    # ------------------------------------------------------------------
    # running tasks
    # ------------------------------------------------------------------

    @property
    def running_tasks(self) -> dict[str, dict[str, Any]]:
        return self._data.setdefault("running_tasks", {})

    def add_running_task(self, task_id: str, **kwargs: Any) -> None:
        entry = {"started_at": datetime.now(UTC).isoformat(), **kwargs}
        self.running_tasks[task_id] = entry
        self._save()

    def remove_running_task(self, task_id: str) -> None:
        self.running_tasks.pop(task_id, None)
        self._save()

    def is_task_running(self, task_id: str) -> bool:
        return task_id in self.running_tasks

    # ------------------------------------------------------------------
    # E2EE key state
    # ------------------------------------------------------------------

    def set_peer_key_fingerprint(
        self, peer_id: str, fingerprint: str
    ) -> None:
        """Record the fingerprint of a peer's published KEM public key."""
        self._data.setdefault("peer_keys", {})[peer_id] = fingerprint
        self._save()

    def peer_key_fingerprint(self, peer_id: str) -> str | None:
        """Fingerprint of the peer's KEM public key, if recorded."""
        return self._data.get("peer_keys", {}).get(peer_id)

    def set_session_key_handle(self, peer_id: str, handle: str) -> None:
        """Record an opaque handle to this side's local private key
        material for sessions with *peer_id*.

        The handle is never key material itself — it is a reference
        (env var name, file path, KMS key id, ...) owned by the caller.
        """
        self._data.setdefault("session_key_handles", {})[peer_id] = handle
        self._save()

    def session_key_handle(self, peer_id: str) -> str | None:
        """The recorded local private key handle for *peer_id*, if any."""
        return self._data.get("session_key_handles", {}).get(peer_id)
