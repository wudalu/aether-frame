from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from aether_frame.contracts import AgentConfig, KnowledgeSource, TaskRequest, UserContext
from aether_frame.framework.adk.adk_session_manager import (
    AdkSessionManager,
    SessionClearedError,
)
from aether_frame.framework.adk.adk_session_models import ChatSessionInfo
from aether_frame.framework.adk.session_recovery import (
    InMemorySessionRecoveryStore,
    SessionRecoveryRecord,
)


class StubRunnerManager:
    def __init__(self):
        self.runners = {}
        self.session_to_runner = {}
        self.agent_runner_mapping = {}
        self.cleaned = []
        self.removed_sessions = []
        self.created_sessions = []
        self.settings = SimpleNamespace(
            runner_idle_timeout_seconds=43200,
            agent_idle_timeout_seconds=43200,
        )

    async def cleanup_runner(self, runner_id: str) -> bool:
        self.cleaned.append(runner_id)
        self.runners.pop(runner_id, None)
        for agent_id, mapped_runner in list(self.agent_runner_mapping.items()):
            if mapped_runner == runner_id:
                del self.agent_runner_mapping[agent_id]
        return True

    async def remove_session_from_runner(self, runner_id: str, session_id: str) -> bool:
        self.removed_sessions.append((runner_id, session_id))
        runner_context = self.runners.get(runner_id)
        if runner_context:
            runner_context.get("sessions", {}).pop(session_id, None)
        return True

    async def get_runner_session_count(self, runner_id: str) -> int:
        runner_context = self.runners.get(runner_id, {})
        sessions = runner_context.get("sessions", {})
        return len(sessions)

    async def _create_session_in_runner(self, runner_id: str, task_request=None, external_session_id: str = None) -> str:
        session_id = external_session_id or f"session-{len(self.created_sessions)}"
        runner_context = self.runners.setdefault(
            runner_id,
            {
                "sessions": {},
                "session_user_ids": {},
                "agent_config": AgentConfig(agent_type="test", system_prompt="prompt"),
            },
        )
        runner_context["sessions"][session_id] = object()
        user_id = "user"
        if task_request and getattr(task_request, "user_context", None):
            user_id = task_request.user_context.get_adk_user_id()
        runner_context.setdefault("session_user_ids", {})[session_id] = user_id
        self.session_to_runner[session_id] = runner_id
        self.created_sessions.append((runner_id, session_id))
        return session_id

    async def get_runner_for_agent(self, agent_id: str) -> str:
        if agent_id not in self.agent_runner_mapping:
            raise RuntimeError(f"No runner for agent {agent_id}")
        return self.agent_runner_mapping[agent_id]


class StubAgentManager:
    def __init__(self):
        self._agent_metadata = {}
        self._agents = {}
        self.cleaned = []

    async def cleanup_agent(self, agent_id: str) -> bool:
        self.cleaned.append(agent_id)
        self._agent_metadata.pop(agent_id, None)
        self._agents.pop(agent_id, None)
        return True


class StubMemoryService:
    def __init__(self):
        self.store_calls = []

    async def store_memory(self, *args, **kwargs):
        self.store_calls.append({"args": args, "kwargs": kwargs})

    async def search_memory(self, *args, **kwargs):
        return SimpleNamespace(results=[])


@pytest.mark.asyncio
async def test_session_cleanup_marks_and_blocks_reuse():
    recovery_store = InMemorySessionRecoveryStore()
    manager = AdkSessionManager(recovery_store=recovery_store)
    runner_manager = StubRunnerManager()
    agent_manager = StubAgentManager()

    chat_session_id = "chat-1"
    user_id = "user-1"
    runner_id = "runner-1"
    agent_id = "agent-1"

    manager.chat_sessions[chat_session_id] = ChatSessionInfo(
        user_id=user_id,
        chat_session_id=chat_session_id,
        active_agent_id=agent_id,
        active_adk_session_id="adk-1",
        active_runner_id=runner_id,
    )

    runner_manager.runners[runner_id] = {
        "sessions": {"adk-1": object()},
        "last_activity": datetime.now(),
        "created_at": datetime.now(),
        "agent_config": AgentConfig(agent_type="test", system_prompt="prompt"),
    }
    runner_manager.agent_runner_mapping[agent_id] = runner_id

    agent_manager._agent_metadata[agent_id] = {
        "created_at": datetime.now(),
        "last_activity": datetime.now(),
    }
    agent_manager._agents[agent_id] = object()

    await manager.cleanup_chat_session(
        chat_session_id,
        runner_manager,
        agent_manager=agent_manager,
    )

    assert chat_session_id in manager._cleared_sessions
    archived_entry = recovery_store.load(chat_session_id)
    assert archived_entry is not None
    assert archived_entry.chat_session_id == chat_session_id
    assert manager._cleared_sessions[chat_session_id]["archived_at"] == archived_entry.archived_at

    with pytest.raises(SessionClearedError):
        manager.get_or_create_chat_session(chat_session_id, user_id)

    recovery_record = await manager.recover_chat_session(chat_session_id, runner_manager)
    assert chat_session_id not in manager._cleared_sessions
    assert recovery_record.agent_id == agent_id
    assert recovery_store.load(chat_session_id) is recovery_record
    assert manager._pending_recoveries[chat_session_id] is recovery_record
    chat_info = manager.chat_sessions[chat_session_id]
    assert chat_info.active_agent_id == agent_id
    assert chat_info.active_adk_session_id is None

    info = manager.get_or_create_chat_session(chat_session_id, user_id)
    assert isinstance(info, ChatSessionInfo)
    assert info is chat_info


@pytest.mark.asyncio
async def test_evaluate_runner_agent_idle_cleans_resources():
    manager = AdkSessionManager()
    runner_manager = StubRunnerManager()
    agent_manager = StubAgentManager()

    runner_id = "runner-1"
    agent_id = "agent-1"
    old_time = datetime.now() - timedelta(hours=13)

    manager._runner_idle_timeout_seconds = 60
    manager._agent_idle_timeout_seconds = 60

    runner_manager.runners[runner_id] = {
        "sessions": {},
        "last_activity": old_time,
        "created_at": old_time,
    }
    runner_manager.agent_runner_mapping[agent_id] = runner_id

    agent_manager._agent_metadata[agent_id] = {
        "created_at": old_time,
        "last_activity": old_time,
    }
    agent_manager._agents[agent_id] = object()

    await manager._evaluate_runner_agent_idle(
        runner_manager,
        agent_manager,
        runner_id,
        agent_id,
        now=datetime.now(),
        trigger="unit_test",
    )

    assert runner_id in runner_manager.cleaned
    assert agent_id in agent_manager.cleaned


@pytest.mark.asyncio
async def test_idle_cleanup_archives_session():
    recovery_store = InMemorySessionRecoveryStore()
    manager = AdkSessionManager(recovery_store=recovery_store)
    runner_manager = StubRunnerManager()

    chat_session_id = "chat-idle"
    runner_id = "runner-idle"
    agent_id = "agent-idle"

    chat_session = ChatSessionInfo(
        user_id="user-idle",
        chat_session_id=chat_session_id,
        active_agent_id=agent_id,
        active_adk_session_id="adk-idle",
        active_runner_id=runner_id,
    )
    chat_session.last_activity = datetime.now() - timedelta(hours=2)
    manager.chat_sessions[chat_session_id] = chat_session

    runner_manager.runners[runner_id] = {
        "sessions": {"adk-idle": object()},
        "last_activity": datetime.now(),
        "created_at": datetime.now(),
        "agent_config": AgentConfig(agent_type="test", system_prompt="prompt"),
    }

    manager._idle_runner_manager = runner_manager
    manager._session_idle_timeout_seconds = 10

    await manager._perform_idle_cleanup()

    archived = recovery_store.load(chat_session_id)
    assert archived is not None
    assert archived.agent_id == agent_id
    assert chat_session_id in manager._cleared_sessions


@pytest.mark.asyncio
async def test_create_session_after_recovery_injects_history(monkeypatch):
    recovery_store = InMemorySessionRecoveryStore()
    manager = AdkSessionManager(recovery_store=recovery_store)
    runner_manager = StubRunnerManager()

    chat_session_id = "chat-recover"
    agent_id = "agent-recover"
    runner_id = "runner-recover"
    user_id = "user-recover"

    runner_manager.agent_runner_mapping[agent_id] = runner_id
    runner_manager.runners[runner_id] = {
        "sessions": {},
        "last_activity": datetime.now(),
        "created_at": datetime.now(),
        "session_user_ids": {},
        "agent_config": AgentConfig(agent_type="test", system_prompt="prompt"),
    }

    record = SessionRecoveryRecord(
        chat_session_id=chat_session_id,
        user_id=user_id,
        agent_id=agent_id,
        agent_config=AgentConfig(agent_type="test", system_prompt="prompt"),
        chat_history=[{"role": "user", "content": "hello"}],
    )
    recovery_store.save(record)
    manager._cleared_sessions[chat_session_id] = {"cleared_at": datetime.now()}

    recovered = await manager.recover_chat_session(chat_session_id, runner_manager)
    assert recovered.chat_history

    injections = []

    async def fake_inject(runner_id_in, session_id_in, chat_history_in, runner_manager_in):
        injections.append((runner_id_in, session_id_in, chat_history_in))

    monkeypatch.setattr(manager, "_inject_chat_history", fake_inject)

    chat_session = manager.chat_sessions[chat_session_id]
    task_request = TaskRequest(
        task_id="task",
        task_type="chat",
        description="recover conversation",
        session_id=chat_session_id,
        agent_id=agent_id,
        user_context=UserContext(user_id=user_id),
    )

    result = await manager._create_session_for_agent(
        chat_session,
        agent_id,
        user_id,
        task_request,
        runner_manager,
    )

    assert result.adk_session_id == chat_session.active_adk_session_id
    assert injections
    injected_runner_id, injected_session_id, injected_history = injections[0]
    assert injected_runner_id == runner_id
    assert injected_history == record.chat_history
    assert recovery_store.load(chat_session_id) is None
    assert chat_session_id not in manager._pending_recoveries


@pytest.mark.asyncio
async def test_switch_agent_consumes_pending_recovery(monkeypatch):
    recovery_store = InMemorySessionRecoveryStore()
    manager = AdkSessionManager(recovery_store=recovery_store)
    runner_manager = StubRunnerManager()

    chat_session_id = "chat-switch"
    old_agent = "agent-old"
    new_agent = "agent-new"
    runner_new = "runner-new"
    user_id = "user-switch"

    chat_session = ChatSessionInfo(
        user_id=user_id,
        chat_session_id=chat_session_id,
        active_agent_id=old_agent,
        active_adk_session_id=None,
        active_runner_id=None,
    )
    manager.chat_sessions[chat_session_id] = chat_session

    record = SessionRecoveryRecord(
        chat_session_id=chat_session_id,
        user_id=user_id,
        agent_id=old_agent,
        agent_config=AgentConfig(agent_type="test", system_prompt="prompt"),
        chat_history=[{"role": "user", "content": "hello"}],
    )
    recovery_store.save(record)
    manager._pending_recoveries[chat_session_id] = record

    runner_manager.agent_runner_mapping[new_agent] = runner_new
    runner_manager.runners[runner_new] = {
        "sessions": {},
        "last_activity": datetime.now(),
        "created_at": datetime.now(),
        "agent_config": AgentConfig(agent_type="test", system_prompt="prompt"),
        "session_user_ids": {},
    }

    injections = []

    async def fake_inject(runner_id_in, session_id_in, history_in, runner_manager_in):
        injections.append((runner_id_in, session_id_in, history_in))

    monkeypatch.setattr(manager, "_inject_chat_history", fake_inject)

    task_request = TaskRequest(
        task_id="task-switch",
        task_type="chat",
        description="Agent switch after recovery",
        agent_id=new_agent,
        session_id=chat_session_id,
        user_context=UserContext(user_id=user_id),
    )

    result = await manager._switch_agent_session(
        chat_session,
        new_agent,
        user_id,
        task_request,
        runner_manager,
    )

    assert result.switch_occurred is True
    assert injections
    injected_runner_id, injected_session_id, injected_history = injections[0]
    assert injected_runner_id == runner_new
    assert injected_history == record.chat_history
    assert recovery_store.load(chat_session_id) is None
    assert chat_session_id not in manager._pending_recoveries


@pytest.mark.asyncio
async def test_evaluate_runner_idle_skips_active_runner():
    manager = AdkSessionManager()
    runner_manager = StubRunnerManager()
    agent_manager = StubAgentManager()

    runner_id = "runner-active"
    agent_id = "agent-active"
    old_time = datetime.now() - timedelta(hours=13)

    manager._runner_idle_timeout_seconds = 60
    manager._agent_idle_timeout_seconds = 60

    runner_manager.runners[runner_id] = {
        "sessions": {"adk-1": object()},
        "last_activity": old_time,
        "created_at": old_time,
    }
    runner_manager.agent_runner_mapping[agent_id] = runner_id

    agent_manager._agent_metadata[agent_id] = {
        "created_at": old_time,
        "last_activity": old_time,
    }
    agent_manager._agents[agent_id] = object()

    await manager._evaluate_runner_agent_idle(
        runner_manager,
        agent_manager,
        runner_id,
        agent_id,
        now=datetime.now(),
        trigger="unit_test",
    )

    assert runner_manager.cleaned == []
    assert agent_manager.cleaned == []


@pytest.mark.asyncio
async def test_cleanup_chat_session_preserves_shared_runner():
    manager = AdkSessionManager()
    runner_manager = StubRunnerManager()

    runner_id = "runner-shared"
    chat_session_a = "chat-A"
    chat_session_b = "chat-B"

    manager.chat_sessions[chat_session_a] = ChatSessionInfo(
        user_id="user-a",
        chat_session_id=chat_session_a,
        active_agent_id="agent-a",
        active_adk_session_id="adk-a",
        active_runner_id=runner_id,
    )
    manager.chat_sessions[chat_session_b] = ChatSessionInfo(
        user_id="user-b",
        chat_session_id=chat_session_b,
        active_agent_id="agent-b",
        active_adk_session_id="adk-b",
        active_runner_id=runner_id,
    )

    runner_manager.runners[runner_id] = {
        "sessions": {"adk-a": object(), "adk-b": object()},
        "last_activity": datetime.now(),
        "created_at": datetime.now(),
    }

    await manager.cleanup_chat_session(
        chat_session_a,
        runner_manager,
    )

    assert runner_manager.removed_sessions == [(runner_id, "adk-a")]
    assert runner_manager.cleaned == []
    assert chat_session_a in manager._cleared_sessions
    assert chat_session_b in manager.chat_sessions
    assert manager.chat_sessions[chat_session_b].active_runner_id == runner_id
    assert "adk-b" in runner_manager.runners[runner_id]["sessions"]


@pytest.mark.asyncio
async def test_cleanup_chat_session_destroys_runner_when_last_session_removed():
    manager = AdkSessionManager()
    runner_manager = StubRunnerManager()

    runner_id = "runner-final"
    chat_session_id = "chat-final"

    manager.chat_sessions[chat_session_id] = ChatSessionInfo(
        user_id="user-final",
        chat_session_id=chat_session_id,
        active_agent_id="agent-final",
        active_adk_session_id="adk-final",
        active_runner_id=runner_id,
    )

    runner_manager.runners[runner_id] = {
        "sessions": {"adk-final": object()},
        "last_activity": datetime.now(),
        "created_at": datetime.now(),
    }

    await manager.cleanup_chat_session(
        chat_session_id,
        runner_manager,
    )

    assert runner_manager.removed_sessions == [(runner_id, "adk-final")]
    assert runner_manager.cleaned == [runner_id]


class KnowledgeRunnerManagerStub:
    def __init__(self):
        self.agent_runner_mapping = {"agent-knowledge": "runner-knowledge"}
        self.session_to_runner = {}
        self.memory_service = StubMemoryService()
        self.settings = SimpleNamespace(
            default_app_name="test-app",
            default_user_id="user-knowledge",
        )
        self.runners = {
            "runner-knowledge": {
                "sessions": {},
                "session_user_ids": {},
                "memory_service": self.memory_service,
                "app_name": "test-app",
                "user_id": "user-knowledge",
            }
        }

    async def get_runner_for_agent(self, agent_id: str) -> str:
        return self.agent_runner_mapping[agent_id]

    async def _create_session_in_runner(self, runner_id: str, task_request=None, external_session_id: str = None) -> str:
        session_id = external_session_id or "stub-session"
        runner_context = self.runners.setdefault(
            runner_id,
            {
                "sessions": {},
                "session_user_ids": {},
                "memory_service": self.memory_service,
                "app_name": "test-app",
                "user_id": "user-knowledge",
            },
        )
        runner_context["sessions"][session_id] = object()
        if task_request and task_request.user_context:
            runner_context["session_user_ids"][session_id] = task_request.user_context.get_adk_user_id()
        self.session_to_runner[session_id] = runner_id
        return session_id

    async def get_runner_by_session(self, session_id: str):
        runner_id = self.session_to_runner.get(session_id)
        if not runner_id:
            return None
        return self.runners.get(runner_id)


@pytest.mark.asyncio
async def test_coordinate_chat_session_persists_and_hydrates_knowledge():
    manager = AdkSessionManager()
    runner_manager = KnowledgeRunnerManagerStub()

    knowledge_sources = [
        KnowledgeSource(
            name="docs",
            source_type="vector_store",
            location="memory://docs",
            description="Primary documentation store",
        )
    ]

    initial_request = TaskRequest(
        task_id="task-1",
        task_type="chat",
        description="Initial turn",
        agent_id="agent-knowledge",
        session_id="chat-session",
        user_context=UserContext(user_id="user-knowledge"),
        available_knowledge=knowledge_sources,
    )

    result = await manager.coordinate_chat_session(
        chat_session_id=initial_request.session_id,
        target_agent_id=initial_request.agent_id,
        user_id=initial_request.user_context.get_adk_user_id(),
        task_request=initial_request,
        runner_manager=runner_manager,
    )

    chat_session = manager.chat_sessions[initial_request.session_id]
    assert chat_session.available_knowledge == knowledge_sources
    assert result.adk_session_id in runner_manager.session_to_runner
    assert "docs" in chat_session.synced_knowledge_sources
    assert len(runner_manager.memory_service.store_calls) == 1
    first_call = runner_manager.memory_service.store_calls[0]
    stored_entry = first_call["kwargs"].get("entry") if first_call["kwargs"] else first_call["args"][2]
    assert getattr(stored_entry, "title", None) == "docs"

    followup_request = TaskRequest(
        task_id="task-2",
        task_type="chat",
        description="Follow-up turn",
        agent_id="agent-knowledge",
        session_id="chat-session",
        user_context=UserContext(user_id="user-knowledge"),
        available_knowledge=[],
    )

    await manager.coordinate_chat_session(
        chat_session_id=followup_request.session_id,
        target_agent_id=followup_request.agent_id,
        user_id=followup_request.user_context.get_adk_user_id(),
        task_request=followup_request,
        runner_manager=runner_manager,
    )

    assert followup_request.available_knowledge == knowledge_sources
    assert followup_request.available_knowledge is not chat_session.available_knowledge
    assert len(runner_manager.memory_service.store_calls) == 1
