# -*- coding: utf-8 -*-
"""Integration-style test covering ADK session/runner/agent idle cleanup."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.aether_frame.agents.manager import AgentManager
from src.aether_frame.config.settings import Settings
from src.aether_frame.contracts.configs import AgentConfig
from src.aether_frame.framework.adk.adk_session_manager import (
    AdkSessionManager,
    SessionClearedError,
)
from src.aether_frame.framework.adk.runner_manager import RunnerManager
from src.aether_frame.framework.adk import runner_manager as runner_manager_module

# Ensure runner_manager exposes datetime for internal usage (module is missing explicit import).
runner_manager_module.datetime = datetime


class StubDomainAgent:
    """Minimal domain agent with cleanup hook."""

    def __init__(self):
        self.cleaned = False

    async def cleanup(self):
        self.cleaned = True


class StubRunner:
    """Runner placeholder that tracks shutdown."""

    def __init__(self):
        self.shutdown_called = False

    async def shutdown(self):
        self.shutdown_called = True


class StubSessionService:
    """In-memory session service mirroring the ADK API surface used in tests."""

    def __init__(self):
        self.sessions = {}
        self.shutdown_called = False

    async def create_session(self, app_name: str, user_id: str, session_id: str):
        session = SimpleNamespace(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        self.sessions[session_id] = session
        return session

    async def delete_session(self, app_name: str, user_id: str, session_id: str):
        self.sessions.pop(session_id, None)

    async def shutdown(self):
        self.shutdown_called = True


class StubRunnerManager(RunnerManager):
    """Runner manager that avoids real ADK dependencies while preserving lifecycle logic."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.created_runners = []

    async def _create_new_runner(self, agent_config, config_hash: str, adk_agent=None) -> str:
        runner_id = f"{self.settings.runner_id_prefix}_{uuid4().hex[:12]}"
        session_service = StubSessionService()
        runner = StubRunner()
        now = datetime.now()

        self.runners[runner_id] = {
            "runner": runner,
            "session_service": session_service,
            "agent_config": agent_config,
            "config_hash": config_hash,
            "sessions": {},
            "session_user_ids": {},
            "created_at": now,
            "last_activity": now,
            "app_name": self.settings.default_app_name,
        }

        self.created_runners.append(runner_id)
        return runner_id

    async def _build_adk_agent(self, agent_config):
        # Not needed because tests pass adk_agent explicitly, but keep interface consistent.
        return StubDomainAgent()


@pytest.mark.asyncio
async def test_idle_cleanup_cascades_to_runner_and_agent():
    settings = Settings()
    session_manager = AdkSessionManager()
    agent_manager = AgentManager()

    cleaned_by_callback = []

    async def agent_cleanup_callback(agent_id: str) -> None:
        cleaned_by_callback.append(agent_id)
        await agent_manager.cleanup_agent(agent_id)

    runner_manager = StubRunnerManager(
        settings=settings,
        session_manager=session_manager,
        agent_runner_mapping={},
        agent_cleanup_callback=agent_cleanup_callback,
    )

    # Register agent with manager
    agent_id = "agent-integration"
    agent_config = AgentConfig(agent_type="assistant", system_prompt="be helpful")
    domain_agent = StubDomainAgent()
    agent_manager._agents[agent_id] = domain_agent
    agent_manager._agent_configs[agent_id] = agent_config
    agent_manager._agent_metadata[agent_id] = {
        "created_at": datetime.now(),
        "last_activity": datetime.now(),
        "agent_type": agent_config.agent_type,
        "framework_type": agent_config.framework_type,
    }

    # Create runner and session for the agent
    runner_id, session_id = await runner_manager.get_or_create_runner(
        agent_config=agent_config,
        task_request=None,
        adk_agent=domain_agent,
        engine_session_id="adk-session-integration",
        allow_reuse=False,
    )
    runner_manager.agent_runner_mapping[agent_id] = runner_id

    # Populate session tracking
    chat_session_id = "business-session-integration"
    chat_session = session_manager.get_or_create_chat_session(
        chat_session_id, user_id="integration-user"
    )
    chat_session.active_agent_id = agent_id
    chat_session.active_adk_session_id = session_id
    chat_session.active_runner_id = runner_id

    # Force idle thresholds to trigger cleanup
    idle_past = datetime.now() - timedelta(minutes=10)
    session_manager._session_idle_timeout_seconds = 60
    session_manager._runner_idle_timeout_seconds = 60
    session_manager._agent_idle_timeout_seconds = 60
    session_manager._idle_runner_manager = runner_manager
    session_manager._idle_agent_manager = agent_manager

    chat_session.last_activity = idle_past
    runner_manager.runners[runner_id]["last_activity"] = idle_past
    agent_manager._agent_metadata[agent_id]["last_activity"] = idle_past

    # Execute idle cleanup sweep
    await session_manager._perform_idle_cleanup()

    # Session should be removed and marked as cleared
    assert chat_session_id not in session_manager.chat_sessions
    assert chat_session_id in session_manager._cleared_sessions
    assert session_manager._cleared_sessions[chat_session_id]["reason"] == "session_idle_timeout"

    # Runner still exists but now idle with zero sessions; force timestamp back and sweep again
    assert runner_id in runner_manager.runners
    runner_manager.runners[runner_id]["last_activity"] = idle_past
    await session_manager._perform_idle_cleanup()

    # Runner resources cleaned up via runner manager on subsequent pass
    assert runner_id not in runner_manager.runners
    assert session_id not in runner_manager.session_to_runner
    assert agent_id not in runner_manager.agent_runner_mapping

    # Agent cleanup called both via callback and manager
    assert agent_id in cleaned_by_callback
    assert agent_id not in agent_manager._agents
    assert agent_id not in agent_manager._agent_metadata
    assert domain_agent.cleaned is True

    # Reuse detection should block until recovery
    with pytest.raises(SessionClearedError):
        session_manager.get_or_create_chat_session(chat_session_id, user_id="integration-user")

    await session_manager.recover_chat_session(chat_session_id, runner_manager)
    recovered_session = session_manager.get_or_create_chat_session(
        chat_session_id, user_id="integration-user"
    )
    assert recovered_session.chat_session_id == chat_session_id
