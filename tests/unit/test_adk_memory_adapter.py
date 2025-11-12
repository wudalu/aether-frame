# -*- coding: utf-8 -*-
"""Unit tests for AdkMemoryAdapter in-memory behaviors."""

import pytest

from aether_frame.infrastructure.adk.adk_memory_adapter import AdkMemoryAdapter


@pytest.mark.asyncio
async def test_save_and_load_session_tracks_timestamps(monkeypatch):
    adapter = AdkMemoryAdapter()

    await adapter.save_session("session-1", {"session_state": {"step": 1}})
    session = await adapter.load_session("session-1")

    assert session["session_state"] == {"step": 1}
    assert session["created_at"] is not None
    assert session["updated_at"] is not None

    await adapter.save_session("session-1", {"session_state": {"step": 2}})
    session = await adapter.load_session("session-1")
    assert session["session_state"]["step"] == 2


@pytest.mark.asyncio
async def test_append_and_get_conversation_history():
    adapter = AdkMemoryAdapter()
    await adapter.append_messages(
        "session-2",
        [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}],
    )

    history = await adapter.get_conversation_history("session-2")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["content"] == "hi"
    assert "timestamp" in history[0]

    limited = await adapter.get_conversation_history("session-2", limit=1)
    assert len(limited) == 1


@pytest.mark.asyncio
async def test_clear_session_and_user_preferences_defaults():
    adapter = AdkMemoryAdapter()
    await adapter.save_session("session-3", {"session_state": {"foo": "bar"}})
    await adapter.append_messages("session-3", [{"role": "user", "content": "ping"}])
    await adapter.clear_session("session-3")

    session = await adapter.load_session("session-3")
    assert session["session_state"] == {}

    prefs = await adapter.get_user_preferences("user-1")
    assert prefs["language"] == "en"

    await adapter.cleanup()
    assert adapter._sessions == {}
