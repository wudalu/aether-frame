# -*- coding: utf-8 -*-
"""Unit tests for AdkSessionManager chat history migration fallbacks."""

from types import SimpleNamespace

import pytest

from aether_frame.framework.adk.adk_session_manager import AdkSessionManager
from aether_frame.framework.adk.adk_session_models import ChatSessionInfo


class StubRunnerManager:
    def __init__(self, runners):
        self.runners = runners


def make_chat_session(active_runner_id="runner-1", active_session_id="session-1"):
    return ChatSessionInfo(
        user_id="user-1",
        chat_session_id="chat-1",
        active_runner_id=active_runner_id,
        active_adk_session_id=active_session_id,
        active_agent_id="agent-1",
    )


@pytest.mark.asyncio
async def test_extract_chat_history_fallbacks_to_cached_session_state():
    manager = AdkSessionManager()
    sample_history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    runner_context = {
        "sessions": {"session-1": SimpleNamespace(state={"conversation_history": sample_history})},
        "session_service": None,
    }
    runner_manager = StubRunnerManager({"runner-1": runner_context})

    chat_session = make_chat_session()

    extracted = await manager._extract_chat_history(chat_session, runner_manager)

    assert extracted == sample_history


@pytest.mark.asyncio
async def test_extract_chat_history_detects_message_like_structures():
    manager = AdkSessionManager()
    custom_messages = [
        {"author": "assistant", "content": "response"},
        {"author": "user", "content": "follow up"},
    ]
    runner_context = {
        "sessions": {"session-2": SimpleNamespace(state={"custom_log": custom_messages})},
        "session_service": None,
    }
    runner_manager = StubRunnerManager({"runner-2": runner_context})

    chat_session = make_chat_session(active_runner_id="runner-2", active_session_id="session-2")

    extracted = await manager._extract_chat_history(chat_session, runner_manager)

    assert extracted == [
        {"role": "assistant", "content": "response"},
        {"role": "user", "content": "follow up"},
    ]


@pytest.mark.asyncio
async def test_inject_chat_history_updates_cached_session_state():
    manager = AdkSessionManager()
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "welcome"},
    ]
    target_session = SimpleNamespace(state={})
    runner_context = {
        "sessions": {"session-3": target_session},
        "session_service": None,
    }
    runner_manager = StubRunnerManager({"runner-3": runner_context})

    await manager._inject_chat_history("runner-3", "session-3", history, runner_manager)

    assert target_session.state["conversation_history"] == history
    assert target_session.state["messages"] == history
