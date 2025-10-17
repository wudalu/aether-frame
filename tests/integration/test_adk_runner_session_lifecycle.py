import pytest
from unittest.mock import AsyncMock

from src.aether_frame.contracts.configs import AgentConfig
from src.aether_frame.contracts.requests import TaskRequest
from src.aether_frame.contracts.contexts import UserContext
from src.aether_frame.framework.adk.runner_manager import RunnerManager
from src.aether_frame.framework.adk.adk_session_manager import AdkSessionManager
from src.aether_frame.framework.adk.adk_session_models import ChatSessionInfo
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter


@pytest.mark.asyncio
async def test_session_user_mapping_with_inmemory_service():
    pytest.importorskip("google.adk.sessions")
    from google.adk.sessions import InMemorySessionService

    session_manager = AdkSessionManager()
    runner_manager = RunnerManager(session_manager=session_manager)

    runner_id = "runner-integration"
    session_service = InMemorySessionService()
    runner_manager.runners[runner_id] = {
        "runner": None,
        "session_service": session_service,
        "agent_config": AgentConfig(agent_type="assistant", system_prompt="prompt"),
        "config_hash": "hash-integration",
        "sessions": {},
        "session_user_ids": {},
        "created_at": "test",
        "app_name": runner_manager.settings.default_app_name,
    }
    runner_manager.agent_runner_mapping = {"agent-integration": runner_id}

    task_request = TaskRequest(
        task_id="task-integration",
        task_type="integration",
        description="integration session creation",
        agent_id="agent-integration",
        session_id="business-session",
        user_context=UserContext(user_id="integration-user"),
    )

    session_id = await runner_manager._create_session_in_runner(
        runner_id, task_request=task_request
    )

    runner_context = runner_manager.runners[runner_id]
    assert session_id in runner_context["session_user_ids"]
    assert runner_context["session_user_ids"][session_id] == "integration-user"
    assert "user_id" not in runner_context

    chat_session = ChatSessionInfo(
        user_id="integration-user",
        chat_session_id=task_request.session_id,
        active_agent_id="agent-integration",
        active_adk_session_id=session_id,
        active_runner_id=runner_id,
    )

    history = await session_manager._extract_chat_history(chat_session, runner_manager)
    assert history == []

    removed = await runner_manager.remove_session_from_runner(runner_id, session_id)
    assert removed
    assert session_id not in runner_manager.runners[runner_id]["session_user_ids"]


@pytest.mark.asyncio
async def test_cleanup_runner_resets_agent_mapping():
    pytest.importorskip("google.adk.sessions")
    from google.adk.sessions import InMemorySessionService

    session_manager = AdkSessionManager()
    runner_manager = RunnerManager(session_manager=session_manager)

    runner_id = "runner-cleanup"
    session_service = InMemorySessionService()
    runner_manager.runners[runner_id] = {
        "runner": None,
        "session_service": session_service,
        "agent_config": AgentConfig(agent_type="assistant", system_prompt="prompt"),
        "config_hash": "hash-cleanup",
        "sessions": {},
        "session_user_ids": {},
        "created_at": "test",
        "app_name": runner_manager.settings.default_app_name,
    }
    runner_manager.agent_runner_mapping = {"agent-cleanup": runner_id}
    runner_manager.config_to_runner["hash-cleanup"] = runner_id

    task_request = TaskRequest(
        task_id="task-cleanup",
        task_type="integration",
        description="cleanup runner integration",
        agent_id="agent-cleanup",
        session_id="business-session-cleanup",
        user_context=UserContext(user_id="cleanup-user"),
    )

    session_id = await runner_manager._create_session_in_runner(
        runner_id, task_request=task_request
    )
    assert session_id in runner_manager.session_to_runner

    cleaned = await runner_manager.cleanup_runner(runner_id)
    assert cleaned is True
    assert runner_id not in runner_manager.runners
    assert "agent-cleanup" not in runner_manager.agent_runner_mapping
    assert session_id not in runner_manager.session_to_runner


@pytest.mark.asyncio
async def test_runner_cleanup_triggers_agent_cleanup(monkeypatch):
    adapter = AdkFrameworkAdapter()

    agent_id = "agent-lifecycle"
    runner_id = "runner-lifecycle"
    session_id = "session-lifecycle"

    agent_config = AgentConfig(agent_type="assistant", system_prompt="lifecycle")
    config_hash = adapter.runner_manager.compute_config_hash(agent_config)

    # Populate adapter state
    adapter._agent_runners[agent_id] = runner_id
    adapter._agent_sessions[agent_id] = [session_id]
    adapter._config_agents.setdefault(config_hash, []).append(agent_id)
    adapter.agent_manager._agent_configs[agent_id] = agent_config

    # Populate runner manager state
    runner_context = {
        "runner": AsyncMock(),
        "session_service": AsyncMock(),
        "agent_config": agent_config,
        "config_hash": config_hash,
        "sessions": {session_id: object()},
        "session_user_ids": {session_id: "lifecycle-user"},
        "created_at": "test",
        "app_name": adapter.runner_manager.settings.default_app_name,
    }
    runner_context["runner"].shutdown = AsyncMock()
    runner_context["session_service"].shutdown = AsyncMock()

    adapter.runner_manager.runners[runner_id] = runner_context
    adapter.runner_manager.session_to_runner[session_id] = runner_id
    adapter.runner_manager.config_to_runner[config_hash] = runner_id
    adapter.runner_manager.agent_runner_mapping[agent_id] = runner_id

    cleanup_agent_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(adapter.agent_manager, "cleanup_agent", cleanup_agent_mock)

    cleaned = await adapter.runner_manager.cleanup_runner(runner_id)
    assert cleaned is True

    cleanup_agent_mock.assert_awaited_once_with(agent_id)
    assert agent_id not in adapter._agent_runners
    assert agent_id not in adapter._agent_sessions
    assert runner_id not in adapter.runner_manager.runners
    assert agent_id not in adapter.runner_manager.agent_runner_mapping
    assert session_id not in adapter.runner_manager.session_to_runner
    if config_hash in adapter._config_agents:
        assert agent_id not in adapter._config_agents[config_hash]
