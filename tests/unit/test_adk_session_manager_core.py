# -*- coding: utf-8 -*-
"""Tests for AdkSessionManager session lifecycle helpers."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from aether_frame.contracts import KnowledgeSource, TaskRequest, UserContext
from aether_frame.framework.adk.adk_session_manager import AdkSessionManager, SessionClearedError
from aether_frame.framework.adk.adk_session_models import ChatSessionInfo
from aether_frame.framework.adk.session_recovery import SessionRecoveryRecord


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


@pytest.mark.asyncio
async def test_extract_chat_history_fallback(monkeypatch):
    manager = AdkSessionManager()
    chat_session = ChatSessionInfo(
        user_id="user",
        chat_session_id="chat-5",
        active_agent_id="agent",
        active_adk_session_id="adk-1",
        active_runner_id="runner-1",
    )
    runner_manager = SimpleNamespace(
        runners={
            "runner-1": {
                "session_service": None,
                "sessions": {
                    "adk-1": SimpleNamespace(
                        state={"conversation_history": [{"role": "user", "content": "hi"}]}
                    )
                },
            }
        }
    )
    history = await manager._extract_chat_history(chat_session, runner_manager)
    assert history == [{"role": "user", "content": "hi"}]


class DummyRecoveryStore:
    def __init__(self):
        self.saved = []
        self.records = {}
        self.purged = []

    def save(self, record):
        self.saved.append(record)
        self.records[record.chat_session_id] = record

    def load(self, chat_session_id):
        return self.records.get(chat_session_id)

    def purge(self, chat_session_id):
        self.purged.append(chat_session_id)
        self.records.pop(chat_session_id, None)


@pytest.mark.asyncio
async def test_archive_chat_session_state_persists_history(monkeypatch):
    manager = AdkSessionManager()
    recovery_store = DummyRecoveryStore()
    manager._recovery_store = recovery_store
    chat_session = ChatSessionInfo(
        user_id="user",
        chat_session_id="chat-archive",
        active_agent_id="agent-1",
        active_adk_session_id="adk-archive",
        active_runner_id="runner-1",
    )
    runner_manager = SimpleNamespace(runners={"runner-1": {"agent_config": {"name": "agent-1"}}})

    async def fake_extract(session, runner_mgr):
        return [{"role": "user", "content": "hi"}]

    monkeypatch.setattr(manager, "_extract_chat_history", fake_extract)

    await manager._archive_chat_session_state(chat_session, runner_manager, reason="manual")
    assert recovery_store.saved
    saved_record = recovery_store.saved[0]
    assert saved_record.chat_session_id == "chat-archive"
    assert saved_record.chat_history == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_maybe_apply_recovery_payload_injects_and_purges(monkeypatch):
    manager = AdkSessionManager()
    manager._recovery_store = DummyRecoveryStore()
    record = SessionRecoveryRecord(
        chat_session_id="chat-recover",
        user_id="user",
        agent_id="agent-1",
        agent_config=None,
        chat_history=[{"role": "assistant", "content": "cached"}],
    )
    manager._pending_recoveries["chat-recover"] = record
    injected = {}

    async def fake_inject(runner_id, session_id, history, runner_mgr):
        injected["args"] = (runner_id, session_id, history)

    monkeypatch.setattr(manager, "_inject_chat_history", fake_inject)

    chat_session = ChatSessionInfo(
        user_id="user",
        chat_session_id="chat-recover",
        active_agent_id="agent-1",
        active_runner_id="runner-1",
    )
    await manager._maybe_apply_recovery_payload(chat_session, SimpleNamespace(), session_id="session-new")
    assert injected["args"][2][0]["content"] == "cached"
    assert "chat-recover" in manager._recovery_store.purged
    assert "chat-recover" not in manager._pending_recoveries


@pytest.mark.asyncio
async def test_maybe_apply_recovery_payload_requeues_on_failure(monkeypatch):
    manager = AdkSessionManager()
    recovery_store = DummyRecoveryStore()
    record = SessionRecoveryRecord(
        chat_session_id="chat-fail",
        user_id="user",
        agent_id="agent-1",
        agent_config=None,
        chat_history=[{"role": "user", "content": "oops"}],
    )
    recovery_store.records["chat-fail"] = record
    manager._recovery_store = recovery_store

    async def failing_inject(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(manager, "_inject_chat_history", failing_inject)

    chat_session = ChatSessionInfo(
        user_id="user",
        chat_session_id="chat-fail",
        active_agent_id="agent-1",
        active_runner_id="runner-1",
    )
    await manager._maybe_apply_recovery_payload(chat_session, SimpleNamespace(), session_id="session-err")
    assert manager._pending_recoveries["chat-fail"] is record


class MemoryServiceStub:
    def __init__(self):
        self.calls = []

    def store_memory(self, *args, **kwargs):
        if kwargs:
            raise TypeError("no kwargs allowed")
        self.calls.append(args)


@pytest.mark.asyncio
async def test_sync_knowledge_to_memory_stores_new_entries():
    manager = AdkSessionManager()
    chat_session = ChatSessionInfo(
        user_id="user",
        chat_session_id="chat-knowledge",
        active_agent_id="agent",
        active_runner_id="runner-1",
    )
    chat_session.synced_knowledge_sources = set()
    memory_service = MemoryServiceStub()
    runner_manager = SimpleNamespace(
        runners={
            "runner-1": {
                "memory_service": memory_service,
                "app_name": "demo-app",
                "session_user_ids": {"session-knowledge": "stored-user"},
            }
        },
        settings=SimpleNamespace(default_app_name="demo-app", default_user_id="fallback-user"),
    )
    knowledge = KnowledgeSource(
        name="doc-one",
        source_type="file",
        location="s3://bucket/doc",
        description="Doc description",
    )
    task_request = TaskRequest(
        task_id="task-knowledge",
        task_type="chat",
        description="desc",
        user_context=UserContext(user_id="user-from-request"),
        available_knowledge=[knowledge],
    )

    await manager._sync_knowledge_to_memory(
        chat_session,
        task_request,
        runner_manager,
        session_id="session-knowledge",
        user_id=None,
    )
    assert memory_service.calls
    app_name, resolved_user, entry = memory_service.calls[0]
    assert app_name == "demo-app"
    assert resolved_user == "stored-user"
    assert entry.title == "doc-one"
    assert "doc-one" in chat_session.synced_knowledge_sources

    # Re-running should not store duplicates
    await manager._sync_knowledge_to_memory(
        chat_session,
        task_request,
        runner_manager,
        session_id="session-knowledge",
        user_id=None,
    )
    assert len(memory_service.calls) == 1


@pytest.mark.asyncio
async def test_evaluate_runner_agent_idle_cleans_runner_and_agent():
    manager = AdkSessionManager()
    now = datetime.utcnow()

    class IdleRunnerManager:
        def __init__(self):
            self.runners = {
                "runner-1": {"last_activity": now - timedelta(seconds=400), "sessions": {}, "created_at": now - timedelta(seconds=400)}
            }
            self.agent_runner_mapping = {"agent-1": "runner-1"}
            self.cleaned = []

        async def cleanup_runner(self, runner_id):
            self.cleaned.append(runner_id)
            return True

    class IdleAgentManager:
        def __init__(self):
            self._agent_metadata = {"agent-1": {"last_activity": now - timedelta(seconds=400)}}
            self.cleaned = []

        async def cleanup_agent(self, agent_id):
            self.cleaned.append(agent_id)
            return True

    runner_manager = IdleRunnerManager()
    agent_manager = IdleAgentManager()

    manager._runner_idle_timeout_seconds = 100
    manager._agent_idle_timeout_seconds = 200

    await manager._evaluate_runner_agent_idle(
        runner_manager,
        agent_manager,
        runner_id="runner-1",
        agent_id="agent-1",
        now=now,
        trigger="unit-test",
    )
    assert runner_manager.cleaned == ["runner-1"]
    assert agent_manager.cleaned == ["agent-1"]


def test_start_idle_cleanup_configures_timeouts(monkeypatch):
    manager = AdkSessionManager()
    settings = SimpleNamespace(
        session_idle_timeout_seconds=5,
        runner_idle_timeout_seconds=0,
        agent_idle_timeout_seconds=0,
        session_idle_check_interval_seconds=2,
    )
    runner_manager = SimpleNamespace(
        settings=settings,
        agent_runner_mapping={},
    )
    agent_manager = object()

    class LoopStub:
        def __init__(self):
            self.created = []

        def create_task(self, coro, name=None):
            self.created.append(name)

            class TaskStub:
                def __init__(self, inner_coro):
                    self._coro = inner_coro

                def done(self_inner):
                    return False

                def cancel(self_inner):
                    self_inner._coro.close()

            task = TaskStub(coro)
            coro.close()
            return task

    loop_stub = LoopStub()
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop_stub)

    manager.start_idle_cleanup(runner_manager, agent_manager)
    assert manager._session_idle_timeout_seconds == 5
    assert manager._runner_idle_timeout_seconds == 15  # session timeout * 3
    assert manager._agent_idle_timeout_seconds == 15
    assert loop_stub.created == ["adk_idle_cleanup"]


@pytest.mark.asyncio
async def test_stop_idle_cleanup_cancels_task():
    manager = AdkSessionManager()
    loop = asyncio.get_event_loop()
    task = loop.create_task(asyncio.sleep(0.1))
    manager._idle_cleanup_task = task
    manager._idle_runner_manager = object()
    manager._idle_agent_manager = object()

    await manager.stop_idle_cleanup()
    assert task.cancelled()
    assert manager._idle_cleanup_task is None
    assert manager._idle_runner_manager is None
    assert manager._idle_agent_manager is None


@pytest.mark.asyncio
async def test_perform_idle_cleanup_archives_stale_sessions(monkeypatch):
    manager = AdkSessionManager()
    chat_session = ChatSessionInfo(
        user_id="user",
        chat_session_id="chat-stale",
        active_agent_id="agent-1",
        active_adk_session_id="adk-stale",
        active_runner_id="runner-1",
    )
    chat_session.last_activity = datetime.utcnow() - timedelta(seconds=50)
    manager.chat_sessions["chat-stale"] = chat_session
    manager._session_idle_timeout_seconds = 10
    manager._idle_runner_manager = SimpleNamespace(
        runners={"runner-1": {"last_activity": datetime.utcnow(), "sessions": {}}},
        agent_runner_mapping={"agent-1": "runner-1"},
        settings=SimpleNamespace(default_app_name="app", default_user_id="user"),
    )
    manager._idle_agent_manager = SimpleNamespace()
    manager._recovery_store = SimpleNamespace(
        load=lambda chat_id: SimpleNamespace(archived_at=datetime.utcnow())
    )

    calls = {"evaluate": []}

    async def fake_archive(**kwargs):
        calls["archive"] = kwargs["reason"]

    async def fake_cleanup_session(chat_session_arg, runner_mgr):
        calls["cleanup_session"] = chat_session_arg.chat_session_id

    def fake_mark(chat_session_id, reason, archived_at=None):
        calls["mark"] = (chat_session_id, reason)

    async def fake_eval(**kwargs):
        calls["evaluate"].append(kwargs.get("runner_id"))

    monkeypatch.setattr(manager, "_archive_chat_session_state", fake_archive)
    monkeypatch.setattr(manager, "_cleanup_session_only", fake_cleanup_session)
    monkeypatch.setattr(manager, "_mark_session_cleared", fake_mark)
    monkeypatch.setattr(manager, "_evaluate_runner_agent_idle", fake_eval)

    await manager._perform_idle_cleanup()
    assert calls["archive"] == "session_idle_timeout"
    assert calls["cleanup_session"] == "chat-stale"
    assert calls["mark"][0] == "chat-stale"
    assert "runner-1" in calls["evaluate"]
    assert "chat-stale" not in manager.chat_sessions
