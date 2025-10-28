"""Tests for ADK Framework Adapter live execution bridge."""

from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.aether_frame.contracts import (
    ExecutionContext,
    FrameworkType,
    RuntimeContext,
    TaskChunkType,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskStreamChunk,
    UserContext,
)
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from src.aether_frame.agents.base.domain_agent import DomainAgent


class _StubDomainAgent(DomainAgent):
    """Minimal domain agent used to validate live delegation."""

    def __init__(self):
        super().__init__("agent-123", {}, {})
        self.execute_live_called = False

    async def initialize(self):
        return None

    async def execute(self, agent_request):
        return TaskResult(
            task_id=agent_request.task_request.task_id,
            status=TaskStatus.SUCCESS,
        )

    async def get_state(self) -> Dict[str, Any]:
        return {}

    async def cleanup(self):
        return None

    async def execute_live(self, task_request):
        self.execute_live_called = True

        async def _stream():
            yield TaskStreamChunk(
                task_id=task_request.task_id,
                chunk_type=TaskChunkType.RESPONSE,
                sequence_id=0,
                content="ok",
                metadata={},
            )

        return _stream(), MagicMock()


@pytest.fixture
def execution_context():
    return ExecutionContext(
        execution_id="exec-live-1",
        framework_type=FrameworkType.ADK,
        execution_mode="live",
        timeout=120,
    )


@pytest.fixture
def task_request():
    return TaskRequest(
        task_id="task-live-1",
        task_type="chat",
        description="Live test",
        user_context=UserContext(user_id="user-1"),
        messages=[],
        session_id="chat-session-1",
        agent_id="agent-123",
    )


@pytest.mark.asyncio
async def test_execute_task_live_not_initialized(task_request, execution_context):
    adapter = AdkFrameworkAdapter()
    with pytest.raises(RuntimeError, match="not initialized"):
        await adapter.execute_task_live(task_request, execution_context)


@pytest.mark.asyncio
async def test_execute_task_live_requires_agent_and_session(execution_context):
    adapter = AdkFrameworkAdapter()
    adapter._initialized = True

    invalid_request = TaskRequest(
        task_id="task-no-agent",
        task_type="chat",
        description="Missing agent",
    )

    event_stream, communicator = await adapter.execute_task_live(
        invalid_request, execution_context
    )

    chunks = []
    async for chunk in event_stream:
        chunks.append(chunk)

    assert len(chunks) == 1
    assert chunks[0].chunk_type == TaskChunkType.ERROR
    assert "requires both agent_id and session_id" in chunks[0].content
    assert hasattr(communicator, "send_user_response")


@pytest.mark.asyncio
async def test_execute_task_live_bridge_flow(task_request, execution_context):
    adapter = AdkFrameworkAdapter()
    adapter._initialized = True

    adapter.adk_session_manager.coordinate_chat_session = AsyncMock(
        return_value=SimpleNamespace(adk_session_id="adk-session-123", switch_occurred=False)
    )

    runtime_context = RuntimeContext(
        session_id="adk-session-123",
        user_id="user-1",
        framework_type=FrameworkType.ADK,
        agent_id=task_request.agent_id,
        runner_id="runner-1",
    )
    runtime_context.metadata["domain_agent"] = _StubDomainAgent()

    adapter._create_runtime_context_for_existing_session = AsyncMock(
        return_value=runtime_context
    )
    adapter.runner_manager.mark_runner_activity = MagicMock()
    adapter._execute_live_with_domain_agent = AsyncMock(
        return_value=("stream", "communicator")
    )

    stream, communicator = await adapter.execute_task_live(
        task_request, execution_context
    )

    adapter.adk_session_manager.coordinate_chat_session.assert_awaited_once()
    adapter._create_runtime_context_for_existing_session.assert_awaited_once()
    adapter._execute_live_with_domain_agent.assert_awaited_once_with(
        task_request, runtime_context
    )
    adapter.runner_manager.mark_runner_activity.assert_called_once_with("runner-1")

    # Ensure request session id restored to business value
    assert task_request.session_id == "chat-session-1"
    assert stream == "stream"
    assert communicator == "communicator"


@pytest.mark.asyncio
async def test_execute_live_with_domain_agent_updates_runtime(task_request):
    adapter = AdkFrameworkAdapter()
    stub_agent = _StubDomainAgent()

    runtime_context = RuntimeContext(
        session_id="adk-session-456",
        user_id="user-1",
        framework_type=FrameworkType.ADK,
        agent_id=stub_agent.agent_id,
        runner_id="runner-live",
    )
    runtime_context.metadata["domain_agent"] = stub_agent
    runtime_context.metadata["adk_session_id"] = "adk-session-456"

    stream, communicator = await adapter._execute_live_with_domain_agent(
        task_request, runtime_context
    )

    assert stub_agent.execute_live_called is True
    assert stub_agent.runtime_context["session_id"] == "adk-session-456"

    collected = []
    async for chunk in stream:
        collected.append(chunk)

    assert collected and collected[0].content == "ok"
    assert hasattr(communicator, "send_user_response")
