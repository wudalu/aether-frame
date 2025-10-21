# -*- coding: utf-8 -*-
"""Focused tests for ADK adapter error messaging and metadata."""

import pytest
from unittest.mock import patch

from src.aether_frame.contracts import (
    AgentConfig,
    FrameworkType,
    TaskRequest,
    TaskStatus,
    TaskComplexity,
    UniversalMessage,
)
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
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
