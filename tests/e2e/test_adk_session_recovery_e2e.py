# -*- coding: utf-8 -*-
"""End-to-end style verification of chat session recovery flows."""

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.aether_frame.contracts import (
    FrameworkType,
    TaskRequest,
    TaskResult,
    TaskStatus,
    UserContext,
)
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from src.aether_frame.framework.adk.adk_session_manager import AdkSessionManager, SessionClearedError
from src.aether_frame.framework.adk.session_recovery import (
    InMemorySessionRecoveryStore,
    SessionRecoveryRecord,
)


@dataclass
class FakeRuntimeContext:
    """Minimal runtime context to satisfy adapter execution flow."""

    session_id: str
    agent_id: str
    runner_id: str
    user_id: str = "user"
    framework_type: FrameworkType = FrameworkType.ADK
    metadata: dict = None
    execution_id: str = "exec-test"
    trace_id: str = "trace-test"

    def __post_init__(self):
        self.metadata = self.metadata or {"pattern": "test", "domain_agent": object()}

    def update_activity(self) -> None:
        pass

    def get_runtime_dict(self):
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "framework_type": self.framework_type,
            "agent_id": self.agent_id,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
        }


class StubRunnerManager:
    """Runner manager stub that tracks sessions without touching real ADK."""

    def __init__(self, session_manager: AdkSessionManager):
        self.session_manager = session_manager
        self.runners = {}
        self.session_to_runner = {}
        self.agent_runner_mapping = {}
        self.settings = SimpleNamespace(
            default_user_id="stub-user",
            default_app_name="stub-app",
            session_id_prefix="stub-session",
            max_sessions_per_agent=10,
        )

    async def _create_session_in_runner(self, runner_id, task_request=None, external_session_id=None):
        session_id = external_session_id or "stub-session-id"
        runner_context = self.runners.setdefault(
            runner_id,
            {
                "sessions": {},
                "session_user_ids": {},
                "agent_config": SimpleNamespace(),
            },
        )
        runner_context["sessions"][session_id] = object()
        runner_context["session_user_ids"][session_id] = (
            task_request.user_context.get_adk_user_id() if task_request and task_request.user_context else "user"
        )
        self.session_to_runner[session_id] = runner_id
        return session_id

    async def get_runner_for_agent(self, agent_id: str) -> str:
        if agent_id not in self.agent_runner_mapping:
            raise RuntimeError(f"No runner registered for agent {agent_id}")
        return self.agent_runner_mapping[agent_id]

    async def remove_session_from_runner(self, runner_id: str, session_id: str) -> bool:
        runner_context = self.runners.get(runner_id)
        if not runner_context:
            return False
        runner_context["sessions"].pop(session_id, None)
        runner_context["session_user_ids"].pop(session_id, None)
        self.session_to_runner.pop(session_id, None)
        return True

    async def get_runner_session_count(self, runner_id: str) -> int:
        runner_context = self.runners.get(runner_id)
        if not runner_context:
            return 0
        return len(runner_context["sessions"])

    async def cleanup_runner(self, runner_id: str) -> bool:
        self.runners.pop(runner_id, None)
        return True


def _bootstrap_adapter(monkeypatch, inject_hook=None):
    """Create an adapter with stubbed dependencies for recovery scenarios."""

    adapter = AdkFrameworkAdapter()

    recovery_store = InMemorySessionRecoveryStore()
    adapter.adk_session_manager = AdkSessionManager(recovery_store=recovery_store)

    stub_runner_manager = StubRunnerManager(adapter.adk_session_manager)
    adapter.runner_manager = stub_runner_manager

    async def fake_runtime_context(task_request: TaskRequest):
        runner_id = stub_runner_manager.agent_runner_mapping.get(task_request.agent_id)
        if not runner_id:
            raise RuntimeError(f"runner not found for agent {task_request.agent_id}")
        return FakeRuntimeContext(
            session_id=task_request.session_id,
            agent_id=task_request.agent_id,
            runner_id=runner_id,
            user_id=task_request.user_context.get_adk_user_id() if task_request.user_context else "user",
        )

    async def fake_execute(task_request: TaskRequest, runtime_context, domain_agent):
        return TaskResult(task_id=task_request.task_id, status=TaskStatus.SUCCESS, messages=[])

    monkeypatch.setattr(adapter, "_create_runtime_context_for_existing_session", fake_runtime_context)
    monkeypatch.setattr(adapter, "_execute_with_domain_agent", fake_execute)

    injections = []

    async def default_inject(runner_id, session_id, history, runner_manager):
        injections.append((runner_id, session_id, history))

    monkeypatch.setattr(
        adapter.adk_session_manager,
        "_inject_chat_history",
        inject_hook or default_inject,
    )

    return adapter, stub_runner_manager, recovery_store, injections


def _register_agent(adapter: AdkFrameworkAdapter, runner_manager: StubRunnerManager, agent_id: str, runner_id: str):
    runner_manager.agent_runner_mapping[agent_id] = runner_id
    runner_manager.runners[runner_id] = {
        "sessions": {},
        "session_user_ids": {},
        "agent_config": SimpleNamespace(),
    }
    adapter.agent_manager._agents[agent_id] = object()
    adapter.agent_manager._agent_configs[agent_id] = SimpleNamespace(agent_type="test")
    adapter.agent_manager._agent_metadata[agent_id] = {"last_activity": None, "created_at": None}


@pytest.mark.asyncio
async def test_session_recovery_same_agent(monkeypatch):
    adapter, runner_manager, recovery_store, injections = _bootstrap_adapter(monkeypatch)

    agent_id = "agent-recover"
    runner_id = "runner-recover"
    _register_agent(adapter, runner_manager, agent_id, runner_id)

    chat_session_id = "chat-recover"
    recovery_record = SessionRecoveryRecord(
        chat_session_id=chat_session_id,
        user_id="user-recover",
        agent_id=agent_id,
        agent_config=None,
        chat_history=[{"role": "user", "content": "hello again"}],
    )
    recovery_store.save(recovery_record)
    adapter.adk_session_manager._cleared_sessions[chat_session_id] = {"cleared_at": recovery_record.archived_at}

    task_request = TaskRequest(
        task_id="recover-task",
        task_type="chat",
        description="resume conversation",
        agent_id=agent_id,
        session_id=chat_session_id,
        messages=[],
        user_context=UserContext(user_id="user-recover"),
    )

    result = await adapter._handle_conversation(task_request, strategy=None)

    assert result.status == TaskStatus.SUCCESS
    assert result.metadata.get("chat_session_id") == chat_session_id
    assert injections
    injected_runner, injected_session, injected_history = injections[0]
    assert injected_runner == runner_id
    assert injected_history == recovery_record.chat_history
    assert recovery_store.load(chat_session_id) is None
    assert chat_session_id not in adapter.adk_session_manager._pending_recoveries


@pytest.mark.asyncio
async def test_session_recovery_agent_switch(monkeypatch):
    adapter, runner_manager, recovery_store, injections = _bootstrap_adapter(monkeypatch)

    old_agent = "agent-old"
    old_runner = "runner-old"
    _register_agent(adapter, runner_manager, old_agent, old_runner)

    new_agent = "agent-new"
    new_runner = "runner-new"
    _register_agent(adapter, runner_manager, new_agent, new_runner)

    chat_session_id = "chat-switch"
    recovery_record = SessionRecoveryRecord(
        chat_session_id=chat_session_id,
        user_id="user-switch",
        agent_id=old_agent,
        agent_config=None,
        chat_history=[{"role": "user", "content": "history before switch"}],
    )
    recovery_store.save(recovery_record)
    adapter.adk_session_manager._cleared_sessions[chat_session_id] = {"cleared_at": recovery_record.archived_at}

    task_request = TaskRequest(
        task_id="switch-task",
        task_type="chat",
        description="switch agent on recovery",
        agent_id=new_agent,
        session_id=chat_session_id,
        messages=[],
        user_context=UserContext(user_id="user-switch"),
    )

    result = await adapter._handle_conversation(task_request, strategy=None)

    assert result.status == TaskStatus.SUCCESS
    assert injections
    injected_runner, injected_session, injected_history = injections[0]
    assert injected_runner == new_runner
    assert injected_history == recovery_record.chat_history
    assert recovery_store.load(chat_session_id) is None
    assert chat_session_id not in adapter.adk_session_manager._pending_recoveries


@pytest.mark.asyncio
async def test_session_recovery_missing_snapshot(monkeypatch):
    adapter, runner_manager, recovery_store, injections = _bootstrap_adapter(monkeypatch)

    agent_id = "agent-missing"
    runner_id = "runner-missing"
    _register_agent(adapter, runner_manager, agent_id, runner_id)

    chat_session_id = "chat-missing"
    adapter.adk_session_manager._cleared_sessions[chat_session_id] = {"cleared_at": datetime.now()}

    task_request = TaskRequest(
        task_id="missing-task",
        task_type="chat",
        description="missing recovery snapshot",
        agent_id=agent_id,
        session_id=chat_session_id,
        messages=[],
        user_context=UserContext(user_id="user-missing"),
    )

    with pytest.raises(SessionClearedError) as excinfo:
        await adapter._handle_conversation(task_request, strategy=None)

    assert excinfo.value.reason == "missing_recovery_record"
    assert recovery_store.load(chat_session_id) is None
    assert injections == []


@pytest.mark.asyncio
async def test_session_recovery_injection_retry(monkeypatch):
    injection_calls = []
    failure_state = {"attempt": 0}

    async def flaky_inject(runner_id, session_id, history, runner_manager):
        failure_state["attempt"] += 1
        injection_calls.append((runner_id, session_id, history, failure_state["attempt"]))
        if failure_state["attempt"] == 1:
            raise RuntimeError("temporary inject failure")

    adapter, runner_manager, recovery_store, _ = _bootstrap_adapter(monkeypatch, inject_hook=flaky_inject)

    agent_id = "agent-retry"
    runner_id = "runner-retry"
    _register_agent(adapter, runner_manager, agent_id, runner_id)

    chat_session_id = "chat-retry"
    recovery_record = SessionRecoveryRecord(
        chat_session_id=chat_session_id,
        user_id="user-retry",
        agent_id=agent_id,
        agent_config=None,
        chat_history=[{"role": "user", "content": "will retry"}],
    )
    recovery_store.save(recovery_record)
    adapter.adk_session_manager._cleared_sessions[chat_session_id] = {"cleared_at": recovery_record.archived_at}

    task_request = TaskRequest(
        task_id="retry-task",
        task_type="chat",
        description="first attempt fails injection",
        agent_id=agent_id,
        session_id=chat_session_id,
        messages=[],
        user_context=UserContext(user_id="user-retry"),
    )

    # First attempt: injection fails, record should remain for retry
    result_first = await adapter._handle_conversation(task_request, strategy=None)
    assert result_first.status == TaskStatus.SUCCESS
    assert failure_state["attempt"] == 1
    assert recovery_store.load(chat_session_id) is not None
    assert chat_session_id in adapter.adk_session_manager._pending_recoveries

    # Drop the existing session to force recreation on next attempt
    chat_info = adapter.adk_session_manager.chat_sessions[chat_session_id]
    await adapter.adk_session_manager._cleanup_session_only(chat_info, adapter.runner_manager)
    assert chat_session_id in adapter.adk_session_manager._pending_recoveries
    task_request.session_id = chat_session_id

    # Second attempt: injection succeeds and record is purged
    result_second = await adapter._handle_conversation(task_request, strategy=None)
    assert result_second.status == TaskStatus.SUCCESS
    assert failure_state["attempt"] == 2
    assert recovery_store.load(chat_session_id) is None
    assert chat_session_id not in adapter.adk_session_manager._pending_recoveries
    assert len(injection_calls) == 2
