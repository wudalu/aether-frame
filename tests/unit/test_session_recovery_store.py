# -*- coding: utf-8 -*-
"""Unit tests for session recovery models and stores."""

import asyncio

import pytest

from aether_frame.contracts import AgentConfig, FrameworkType
from aether_frame.framework.adk.session_recovery import (
    InMemoryArchiveSessionService,
    InMemorySessionRecoveryStore,
    SessionRecoveryRecord,
)


def make_agent_config():
    return AgentConfig(
        agent_type="support",
        system_prompt="help users",
        framework_type=FrameworkType.ADK,
        model_config={"model": "gemini"},
        available_tools=["tool-a"],
    )


def test_session_recovery_record_to_dict_includes_metadata():
    record = SessionRecoveryRecord(
        chat_session_id="chat-1",
        user_id="user-1",
        agent_id="agent-1",
        agent_config=make_agent_config(),
        chat_history=[{"role": "user", "content": "hello"}],
    )

    payload = record.to_dict()
    assert payload["chat_session_id"] == "chat-1"
    assert payload["chat_history_length"] == 1
    assert payload["agent_config"]["agent_type"] == "support"


def test_in_memory_store_save_load_purge():
    store = InMemorySessionRecoveryStore()
    record = SessionRecoveryRecord(
        chat_session_id="chat-1",
        user_id="user-1",
        agent_id="agent-1",
        agent_config=None,
        chat_history=[],
    )

    store.save(record)
    assert store.load("chat-1") == record
    store.purge("chat-1")
    assert store.load("chat-1") is None


@pytest.mark.asyncio
async def test_archive_session_service_roundtrip():
    service = InMemoryArchiveSessionService()
    await service.create_session("app", "user", "session-1")
    assert "session-1" in service.sessions

    record = SessionRecoveryRecord(
        chat_session_id="chat-1",
        user_id="user",
        agent_id="agent",
        agent_config=None,
        chat_history=[],
    )

    await service.archive_session(record)
    loaded = await service.load_archived_session("chat-1")
    assert loaded == record

    await service.purge_archived_session("chat-1")
    assert await service.load_archived_session("chat-1") is None

    await service.delete_session("app", "user", "session-1")
    assert "session-1" not in service.sessions

    await service.shutdown()
    assert service.shutdown_called is True
