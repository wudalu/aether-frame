# -*- coding: utf-8 -*-
"""Tests for AdkSessionManager session lifecycle helpers."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from aether_frame.framework.adk.adk_session_manager import AdkSessionManager, SessionClearedError
from aether_frame.framework.adk.adk_session_models import ChatSessionInfo


class RunnerManagerStub:
    def __init__(self):
        self.runners = {
            "runner-1": {
                "sessions": {"adk-1": SimpleNamespace()},
                "session_service": None,
                "session_user_ids": {"adk-1": "user"},
            }
        }
        self.cleaned = []

    async def remove_session_from_runner(self, runner_id, session_id):
        self.runners[runner_id]["sessions"].pop(session_id, None)

    async def cleanup_runner(self, runner_id):
        self.cleaned.append(runner_id)

    async def get_runner_session_count(self, runner_id):
        return len(self.runners.get(runner_id, {}).get("sessions", {}))


@pytest.mark.asyncio
async def test_get_or_create_chat_session_and_cleanup(monkeypatch):
    manager = AdkSessionManager()
    session = manager.get_or_create_chat_session("chat-1", "user-1")
    assert isinstance(session, ChatSessionInfo)
    assert manager.get_or_create_chat_session("chat-1", "user-1") is session

    manager._mark_session_cleared("chat-1", reason="idle", archived_at=datetime.now())
    with pytest.raises(SessionClearedError):
        manager.get_or_create_chat_session("chat-1", "user-1")


@pytest.mark.asyncio
async def test_cleanup_session_only_and_runner():
    manager = AdkSessionManager()
    chat_session = ChatSessionInfo(
        user_id="user",
        chat_session_id="chat-2",
        active_agent_id="agent",
        active_adk_session_id="adk-1",
        active_runner_id="runner-1",
    )
    runner_manager = RunnerManagerStub()

    await manager._cleanup_session_only(chat_session, runner_manager)
    assert chat_session.active_adk_session_id is None

    other_session = ChatSessionInfo(
        user_id="user",
        chat_session_id="chat-3",
        active_agent_id="agent",
        active_adk_session_id="adk-2",
        active_runner_id="runner-1",
    )
    manager.chat_sessions["chat-3"] = other_session
    manager.chat_sessions["chat-4"] = ChatSessionInfo(
        user_id="user",
        chat_session_id="chat-4",
        active_agent_id="agent",
        active_adk_session_id=None,
        active_runner_id="runner-1",
    )
    await manager._cleanup_session_and_runner(other_session, runner_manager)
    assert runner_manager.cleaned == []
