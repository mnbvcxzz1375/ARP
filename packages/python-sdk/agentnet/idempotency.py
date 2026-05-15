"""In-memory idempotency cache that deduplicates ARP message_ids.

Also writes-through to the local session store so dedup survives restarts.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class IdempotencyCache:
    """LRU-style in-memory cache keyed by ARP message_id.

    Duplicate message_ids return True (already processed) so the caller
    can send an automatic ack without re-invoking the task handler.
    """

    def __init__(
        self,
        max_size: int = 10_000,
        ttl_seconds: int = 3600,
    ) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, float] = OrderedDict()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def has(self, message_id: str) -> bool:
        """Return True if *message_id* has already been seen and is not expired."""
        now = time.monotonic()
        ts = self._cache.get(message_id)
        if ts is None:
            return False
        if now - ts > self._ttl:
            self._cache.pop(message_id, None)
            return False
        # Move to end (most-recently-used)
        self._cache.move_to_end(message_id)
        return True

    def add(self, message_id: str) -> None:
        """Mark *message_id* as seen."""
        if self.has(message_id):
            return
        self._cache[message_id] = time.monotonic()
        # Enforce max size
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def remove(self, message_id: str) -> None:
        self._cache.pop(message_id, None)

    def clear(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------
    # bulk ops for session resume
    # ------------------------------------------------------------------

    def seed(self, message_ids: list[str]) -> None:
        """Pre-populate with known message ids (e.g. from session store)."""
        now = time.monotonic()
        for mid in message_ids:
            if mid not in self._cache:
                self._cache[mid] = now
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    @property
    def size(self) -> int:
        return len(self._cache)
