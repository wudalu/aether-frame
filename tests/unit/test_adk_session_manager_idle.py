from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from aether_frame.framework.adk.adk_session_manager import (
    AdkSessionManager,
    SessionClearedError,
)
from aether_frame.framework.adk.adk_session_models import ChatSessionInfo


class StubRunnerManager:
    def __init__(self):
        self.runners = {}
        self.session_to_runner = {}
        self.agent_runner_mapping = {}
        self.cleaned = []
        self.removed_sessions = []
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


@pytest.mark.asyncio
async def test_session_cleanup_marks_and_blocks_reuse():
    manager = AdkSessionManager()
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
        "sessions": {},
        "last_activity": datetime.now(),
        "created_at": datetime.now(),
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

    with pytest.raises(SessionClearedError):
        manager.get_or_create_chat_session(chat_session_id, user_id)

    await manager.recover_chat_session(chat_session_id, runner_manager)
    assert chat_session_id not in manager._cleared_sessions

    info = manager.get_or_create_chat_session(chat_session_id, user_id)
    assert isinstance(info, ChatSessionInfo)


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
