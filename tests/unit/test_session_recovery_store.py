# -*- coding: utf-8 -*-
"""Unit tests for SessionRecoveryRecord and InMemorySessionRecoveryStore."""

from datetime import datetime

import pytest

from aether_frame.contracts.configs import AgentConfig
from aether_frame.framework.adk.session_recovery import (
    InMemoryArchiveSessionService,
    InMemorySessionRecoveryStore,
    SessionRecoveryRecord,
)


@pytest.fixture
def sample_record() -> SessionRecoveryRecord:
    return SessionRecoveryRecord(
        chat_session_id="chat-123",
        user_id="user-456",
        agent_id="agent-789",
        agent_config=AgentConfig(
            agent_type="test",
            system_prompt="you are a test agent",
            model_config={"model": "test-model"},
        ),
        chat_history=[{"role": "user", "content": "hi"}],
    )


def test_save_and_load_returns_same_record(sample_record: SessionRecoveryRecord) -> None:
    store = InMemorySessionRecoveryStore()

    store.save(sample_record)

    loaded = store.load(sample_record.chat_session_id)
    assert loaded is not None
    assert loaded.chat_session_id == sample_record.chat_session_id
    assert loaded.agent_id == sample_record.agent_id
    assert loaded.chat_history == sample_record.chat_history


def test_purge_removes_record(sample_record: SessionRecoveryRecord) -> None:
    store = InMemorySessionRecoveryStore()

    store.save(sample_record)
    store.purge(sample_record.chat_session_id)

    assert store.load(sample_record.chat_session_id) is None


def test_to_dict_contains_serialized_agent_config(sample_record: SessionRecoveryRecord) -> None:
    as_dict = sample_record.to_dict()

    assert as_dict["chat_session_id"] == sample_record.chat_session_id
    assert as_dict["chat_history_length"] == 1
    assert as_dict["agent_config"]["model_config"] == {"model": "test-model"}

    # Ensure archived_at has been populated with ISO string
    archived_at = datetime.fromisoformat(as_dict["archived_at"])
    assert isinstance(archived_at, datetime)


@pytest.mark.asyncio
async def test_in_memory_archive_session_service_roundtrip(sample_record: SessionRecoveryRecord) -> None:
    store = InMemorySessionRecoveryStore()
    service = InMemoryArchiveSessionService(recovery_store=store)

    await service.archive_session(sample_record)
    loaded = await service.load_archived_session(sample_record.chat_session_id)
    assert loaded == sample_record
    assert service.get_recovery_store() is store

    await service.purge_archived_session(sample_record.chat_session_id)
    assert await service.load_archived_session(sample_record.chat_session_id) is None

    await service.shutdown()
    assert service.shutdown_called is True
