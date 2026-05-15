"""Tests for SessionStore."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from agentnet.session_store import SessionStore


class TestSessionStore:
    def test_new_store_creates_file_on_save(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            store = SessionStore(path)
            store.set_last_message_id("msg_001")
            assert Path(path).exists()
            data = json.loads(Path(path).read_text())
            assert data["last_message_id"] == "msg_001"
        finally:
            os.unlink(path)

    def test_load_restores_state(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store1 = SessionStore(tmp)
            store1.set_last_message_id("msg_load")
            store1.add_running_task("task-1", extra="data")

            store2 = SessionStore(tmp)
            store2.open()
            assert store2.last_message_id == "msg_load"
            assert store2.is_task_running("task-1")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_add_and_remove_running_task(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store = SessionStore(tmp)
            assert not store.is_task_running("t1")

            store.add_running_task("t1")
            assert store.is_task_running("t1")

            store.remove_running_task("t1")
            assert not store.is_task_running("t1")
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_set_last_message_id_overwrites(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store = SessionStore(tmp)
            store.set_last_message_id("first")
            store.set_last_message_id("second")
            assert store.last_message_id == "second"
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
