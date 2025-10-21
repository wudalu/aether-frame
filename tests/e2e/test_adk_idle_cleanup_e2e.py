# -*- coding: utf-8 -*-
"""End-to-end idle cleanup test using real ADK services."""

from datetime import datetime, timedelta

import pytest

from src.aether_frame.config.settings import Settings
from src.aether_frame.contracts.configs import AgentConfig
from src.aether_frame.contracts.contexts import UserContext, UniversalMessage
from src.aether_frame.contracts.enums import FrameworkType, TaskComplexity, TaskStatus
from src.aether_frame.contracts.requests import TaskRequest
from src.aether_frame.execution.task_router import ExecutionStrategy
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from src.aether_frame.framework.adk.adk_session_manager import SessionClearedError


@pytest.mark.asyncio
async def test_adk_idle_cleanup_end_to_end():
    pytest.importorskip("google.adk.sessions")
    pytest.importorskip("google.adk.runners")
    pytest.importorskip("google.adk.agents")

    settings = Settings(
        session_idle_timeout_seconds=1,
        runner_idle_timeout_seconds=2,
        agent_idle_timeout_seconds=2,
        session_idle_check_interval_seconds=1,
        default_user_id="idle_e2e_user",
        default_app_name="idle-e2e-app",
    )

    adapter = AdkFrameworkAdapter()
    await adapter.initialize(settings=settings)

    strategy = ExecutionStrategy(
        framework_type=FrameworkType.ADK,
        task_complexity=TaskComplexity.SIMPLE,
        execution_config={},
        runtime_options={},
    )

    agent_config = AgentConfig(
        agent_type="assistant",
        system_prompt="You are an idle cleanup validator.",
        model_config={"model": "gemini-1.5-flash"},
    )

    chat_session_id = "idle_cleanup_e2e"
    user_context = UserContext(user_id="idle_e2e_user")

    try:
        create_request = TaskRequest(
            task_id="idle_create",
            task_type="chat",
            description="create agent for idle cleanup",
            agent_config=agent_config,
            session_id=chat_session_id,
            user_context=user_context,
        )

        creation_result = await adapter.execute_task(create_request, strategy)
        assert creation_result.status == TaskStatus.SUCCESS
        agent_id = creation_result.agent_id
        assert agent_id

        conversation_request = TaskRequest(
            task_id="idle_convo",
            task_type="chat",
            description="drive conversation for idle cleanup",
            agent_id=agent_id,
            session_id=chat_session_id,
            messages=[UniversalMessage(role="user", content="ping")],
            user_context=user_context,
        )

        convo_result = await adapter.execute_task(conversation_request, strategy)
        assert convo_result.status in {TaskStatus.SUCCESS, TaskStatus.ERROR}

        chat_info = adapter.adk_session_manager.chat_sessions[chat_session_id]
        runner_id = chat_info.active_runner_id
        adk_session_id = chat_info.active_adk_session_id
        assert runner_id
        assert adk_session_id

        # Force idle state and perform cleanup sweep
        idle_time = datetime.now() - timedelta(seconds=5)
        chat_info.last_activity = idle_time
        adapter.runner_manager.runners[runner_id]["last_activity"] = idle_time
        adapter.agent_manager._agent_metadata[agent_id]["last_activity"] = idle_time

        await adapter.adk_session_manager._perform_idle_cleanup()

        assert chat_session_id not in adapter.adk_session_manager.chat_sessions
        assert chat_session_id in adapter.adk_session_manager._cleared_sessions
        with pytest.raises(SessionClearedError):
            adapter.adk_session_manager.get_or_create_chat_session(chat_session_id, user_context.user_id)

        if runner_id in adapter.runner_manager.runners:
            adapter.runner_manager.runners[runner_id]["last_activity"] = idle_time
            await adapter.adk_session_manager._perform_idle_cleanup()

        assert runner_id not in adapter.runner_manager.runners
        assert agent_id not in adapter.agent_manager._agents

    finally:
        await adapter.adk_session_manager.stop_idle_cleanup()
        await adapter.shutdown()
