# -*- coding: utf-8 -*-
"""Focused tests for ADK adapter error messaging, metadata, and recovery logic."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.aether_frame.contracts import (
    AgentConfig,
    FrameworkType,
    TaskRequest,
    TaskStatus,
    TaskComplexity,
    TaskResult,
    UniversalMessage,
    UserContext,
)
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from src.aether_frame.framework.adk.adk_session_manager import SessionClearedError
from src.aether_frame.framework.adk.adk_session_models import CoordinationResult
from src.aether_frame.framework.adk.session_recovery import SessionRecoveryRecord
from src.aether_frame.execution.task_router import ExecutionStrategy


@pytest.fixture
def execution_strategy() -> ExecutionStrategy:
    """Provide a simple ADK execution strategy for tests."""
    return ExecutionStrategy(
        framework_type=FrameworkType.ADK,
        task_complexity=TaskComplexity.SIMPLE,
        execution_config={},
        runtime_options={},
        execution_mode="sync",
    )


def _build_agent_config() -> AgentConfig:
    """Create a minimal agent configuration."""
    return AgentConfig(
        agent_type="assistant",
        system_prompt="You are a helpful assistant.",
        model_config={"model": "gemini-1.5-flash"},
    )


def _build_message() -> UniversalMessage:
    """Create a simple user message."""
    return UniversalMessage(role="user", content="hello")


class FakeRuntimeContext:
    """Minimal runtime context stub for conversation tests."""

    def __init__(self, session_id: str, agent_id: str, runner_id: str):
        self.session_id = session_id
        self.agent_id = agent_id
        self.runner_id = runner_id
        self.user_id = "user-recover"
        self.framework_type = FrameworkType.ADK
        self.metadata = {"pattern": "test", "domain_agent": object()}
        self.execution_id = "exec-1"
        self.trace_id = None
        self.runner_context = {}

    def update_activity(self) -> None:
        """No-op for tests."""

    def get_runtime_dict(self):  # noqa: D401
        """Return minimal runtime dict for compatibility."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "framework_type": self.framework_type,
            "agent_id": self.agent_id,
        }


@pytest.mark.asyncio
async def test_agent_creation_rejects_messages(execution_strategy: ExecutionStrategy) -> None:
    """Ensure create-agent requests with messages return guidance error."""
    adapter = AdkFrameworkAdapter()
    task_request = TaskRequest(
        task_id="create_with_messages",
        task_type="chat",
        description="Create agent",
        agent_config=_build_agent_config(),
        messages=[_build_message()],
    )

    result = await adapter.execute_task(task_request, execution_strategy)

    assert result.status == TaskStatus.ERROR
    assert "Create the agent first" in result.error_message
    assert result.metadata.get("request_mode") == "agent_creation_with_messages"
    assert result.metadata.get("error_stage") == "adk_adapter.validate_request"


@pytest.mark.asyncio
async def test_execution_error_metadata(execution_strategy: ExecutionStrategy) -> None:
    """Verify custom ExecutionError surfaces structured metadata."""
    adapter = AdkFrameworkAdapter()
    task_request = TaskRequest(
        task_id="conversation_error",
        task_type="chat",
        description="Continue conversation",
        agent_id="agent_123",
        session_id="session_abc",
    )

    execution_error = adapter.ExecutionError("Runner missing", task_request)

    with patch.object(
        adapter,
        "_handle_conversation",
        side_effect=execution_error,
    ):
        result = await adapter.execute_task(task_request, execution_strategy)

    assert result.status == TaskStatus.ERROR
    assert "Runner missing" in result.error_message
    assert result.metadata.get("request_mode") == "conversation_existing_session"
    assert result.metadata.get("error_stage") == "adk_adapter.execute_task"
    assert result.metadata.get("session_id") == "session_abc"


@pytest.mark.asyncio
async def test_generic_exception_metadata(execution_strategy: ExecutionStrategy) -> None:
    """Ensure unexpected exceptions include request mode and identifiers."""
    adapter = AdkFrameworkAdapter()
    task_request = TaskRequest(
        task_id="conversation_generic_error",
        task_type="chat",
        description="Continue conversation",
        agent_id="agent_456",
        session_id="session_xyz",
    )

    with patch.object(
        adapter,
        "_handle_conversation",
        side_effect=RuntimeError("Unexpected failure"),
    ):
        result = await adapter.execute_task(task_request, execution_strategy)

    assert result.status == TaskStatus.ERROR
    assert "Unexpected failure" in result.error_message
    assert "conversation_existing_session" in result.error_message
    assert result.metadata.get("request_mode") == "conversation_existing_session"
    assert result.metadata.get("error_type") == "RuntimeError"
    assert result.metadata.get("session_id") == "session_xyz"
    assert result.metadata.get("agent_id") == "agent_456"


@pytest.mark.asyncio
async def test_conversation_recovers_cleared_session(execution_strategy: ExecutionStrategy) -> None:
    """Adapter should trigger session recovery once and then proceed."""

    adapter = AdkFrameworkAdapter()
    chat_session_id = "chat-business"
    task_request = TaskRequest(
        task_id="conversation_recover",
        task_type="chat",
        description="Recover conversation",
        agent_id="agent_recover",
        session_id=chat_session_id,
        user_context=UserContext(user_id="user-recover"),
    )

    cleared_error = SessionClearedError(chat_session_id, datetime.now())
    coordination_side_effect = [
        cleared_error,
        CoordinationResult(adk_session_id="adk-session-xyz", switch_occurred=False),
    ]
    adapter.adk_session_manager.coordinate_chat_session = AsyncMock(side_effect=coordination_side_effect)

    recovery_record = SessionRecoveryRecord(
        chat_session_id=chat_session_id,
        user_id="user-recover",
        agent_id="agent_recover",
        agent_config=None,
        chat_history=[{"role": "user", "content": "hi"}],
    )
    adapter.adk_session_manager.recover_chat_session = AsyncMock(return_value=recovery_record)

    fake_runtime_context = FakeRuntimeContext(
        session_id="adk-session-xyz",
        agent_id="agent_recover",
        runner_id="runner-123",
    )
    adapter._create_runtime_context_for_existing_session = AsyncMock(return_value=fake_runtime_context)

    adapter._execute_with_domain_agent = AsyncMock(
        return_value=TaskResult(
            task_id=task_request.task_id,
            status=TaskStatus.SUCCESS,
            messages=[]
        )
    )

    result = await adapter._handle_conversation(task_request, execution_strategy)

    assert result.status == TaskStatus.SUCCESS
    assert result.metadata.get("chat_session_id") == chat_session_id
    assert adapter.adk_session_manager.recover_chat_session.await_count == 1
    assert adapter.adk_session_manager.coordinate_chat_session.await_count == 2
    adapter._execute_with_domain_agent.assert_awaited_once()
