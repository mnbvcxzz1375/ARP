"""Tests for IdempotencyCache."""

import time

import pytest

from agentnet.idempotency import IdempotencyCache


class TestIdempotencyCache:
    def test_add_and_has(self):
        cache = IdempotencyCache()
        assert not cache.has("msg_1")
        cache.add("msg_1")
        assert cache.has("msg_1")
        # Not present
        assert not cache.has("msg_2")

    def test_add_duplicate_noop(self):
        cache = IdempotencyCache()
        cache.add("msg_1")
        cache.add("msg_1")  # should not raise
        assert cache.size == 1

    def test_ttl_expiry(self):
        cache = IdempotencyCache(ttl_seconds=0.1)
        cache.add("msg_1")
        assert cache.has("msg_1")
        time.sleep(0.15)
        assert not cache.has("msg_1")
        assert cache.size == 0

    def test_lru_eviction(self):
        cache = IdempotencyCache(max_size=3)
        cache.add("a")
        cache.add("b")
        cache.add("c")
        cache.add("d")
        assert not cache.has("a")  # evicted (oldest)
        assert cache.has("b")
        assert cache.has("c")
        assert cache.has("d")
        assert cache.size == 3

    def test_has_moves_to_end(self):
        cache = IdempotencyCache(max_size=3)
        cache.add("a")
        cache.add("b")
        cache.add("c")
        # access 'a' to mark it recently used
        assert cache.has("a")
        cache.add("d")
        # 'b' should be evicted now (least recently used)
        assert not cache.has("b")
        assert cache.has("a")

    def test_remove(self):
        cache = IdempotencyCache()
        cache.add("x")
        cache.remove("x")
        assert not cache.has("x")

    def test_seed(self):
        cache = IdempotencyCache()
        cache.seed(["m1", "m2", "m3"])
        assert cache.has("m1")
        assert cache.has("m2")
        assert cache.has("m3")
        assert cache.size == 3

    def test_clear(self):
        cache = IdempotencyCache()
        cache.add("m1")
        cache.clear()
        assert cache.size == 0
