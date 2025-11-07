# -*- coding: utf-8 -*-
"""Unit tests for aether_frame.common.utils helpers."""

import asyncio
import json
from datetime import datetime, timezone

import pytest

from aether_frame.common import utils
from aether_frame.common.exceptions import TimeoutError


def test_generate_ids_and_hashes(monkeypatch):
    monkeypatch.setattr(utils.uuid, "uuid4", lambda: uuid_stub("12345678-1234-5678-1234-567812345678"))
    monkeypatch.setattr(utils.time, "time", lambda: 1700000000)

    task_id = utils.generate_task_id()
    agent_id = utils.generate_agent_id("writer", domain="dev")

    assert task_id == "12345678-1234-5678-1234-567812345678"
    assert agent_id.startswith("writer-dev-1700000000-")
    assert len(agent_id.split("-")[-1]) == 8
    assert utils.hash_string("hello") == utils.hash_string("hello")


def uuid_stub(value):
    class _UUID:
        def __init__(self, text):
            self._text = text

        def __str__(self):
            return self._text

        def hex(self):
            return self._text.replace("-", "")

    return _UUID(value)


def test_timestamp_and_json_helpers(monkeypatch):
    timestamp = datetime(2024, 5, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(utils, "datetime", type("dt", (), {"now": lambda tz=None: timestamp}))

    assert utils.current_timestamp() == timestamp

    payload = {"a": 1, "created_at": timestamp}
    serialized = utils.serialize_json(payload)
    assert '"created_at": "2024-05-01' in serialized
    assert utils.deserialize_json('{"a": 1}') == {"a": 1}


@pytest.mark.asyncio
async def test_with_timeout_success_and_failure(monkeypatch):
    async def sleepy(delay):
        await asyncio.sleep(delay)
        return "done"

    result = await utils.with_timeout(sleepy(0.01), timeout=0.5)
    assert result == "done"

    with pytest.raises(TimeoutError):
        await utils.with_timeout(sleepy(0.2), timeout=0.05)


def test_dict_helpers_and_timer(monkeypatch):
    merged = utils.merge_dicts({"a": 1}, None, {"b": 2})
    assert merged == {"a": 1, "b": 2}
    assert utils.safe_get({"x": 1}, "x", 0) == 1
    assert utils.safe_get({}, "missing", "fallback") == "fallback"

    assert utils.truncate_string("short", 10) == "short"
    assert utils.truncate_string("longtext", 4) == "l..."

    fake_time = [100.0]

    def time_stub():
        value = fake_time[0]
        fake_time[0] += 1.0
        return value

    monkeypatch.setattr(utils.time, "time", time_stub)
    timer = utils.Timer()
    with timer:
        _ = utils.safe_get({}, "")
    assert timer.elapsed == pytest.approx(1.0)
