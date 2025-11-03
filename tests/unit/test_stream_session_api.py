import pytest
from unittest.mock import AsyncMock, MagicMock

from aether_frame.execution.task_factory import TaskRequestFactory
from aether_frame.execution.execution_engine import ExecutionEngine
from aether_frame.framework.framework_registry import FrameworkRegistry
from aether_frame.tools.service import ToolService
from aether_frame.contracts import (
    InteractionResponse,
    TaskChunkType,
    TaskStreamChunk,
    UniversalMessage,
    UserContext,
)
from aether_frame.streaming import StreamSession


class _DummyBroker:
    def __init__(self) -> None:
        self.closed = False
        self._pending = [
            {
                "interaction_id": "call-1",
                "tool_name": "demo.search",
                "created_at": "2025-01-01T00:00:00Z",
                "expires_at": "2025-01-01T00:00:30Z",
                "requires_approval": True,
                "metadata": {"tool_name": "demo.search"},
            }
        ]

    async def list_pending_interactions(self):
        return list(self._pending)

    def close(self) -> None:
        self.closed = True


class _DummyCommunicator:
    def __init__(self) -> None:
        self.responses = []
        self.messages = []
        self.cancellations = []
        self.closed = False
        self.broker = _DummyBroker()

    async def send_user_response(self, response: InteractionResponse) -> None:
        self.responses.append(response)

    async def send_user_message(self, message: str) -> None:
        self.messages.append(message)

    async def send_cancellation(self, reason: str = "user_cancelled") -> None:
        self.cancellations.append(reason)

    def close(self) -> None:
        self.closed = True
        if self.broker:
            self.broker.close()


def _build_live_chunk(task_id: str) -> TaskStreamChunk:
    return TaskStreamChunk(
        task_id=task_id,
        chunk_type=TaskChunkType.TOOL_PROPOSAL,
        sequence_id=0,
        content={
            "tool_name": "progressive_search",
            "tool_full_name": "demo.search",
            "tool_namespace": "demo",
            "arguments": {"query": "latest updates"},
        },
        is_final=False,
        metadata={
            "stage": "tool",
            "requires_approval": True,
            "tool_name": "demo.search",
            "tool_short_name": "progressive_search",
            "tool_full_name": "demo.search",
        },
        interaction_id="call-1",
        chunk_kind="tool.proposal",
    )


@pytest.mark.asyncio
async def test_execute_task_live_session_wrapper() -> None:
    tool_service = ToolService()
    factory = TaskRequestFactory(tool_service)

    task_request = await factory.create_live_chat_task(
        task_id="live_demo_001",
        description="Demo live session",
        user_context=UserContext(user_id="user-123"),
        messages=[UniversalMessage(role="user", content="Give me an update")],
        agent_type="demo_agent",
        system_prompt="You are a helpful assistant.",
        model_config={"model": "deepseek-chat"},
        tool_names=None,
    )

    assert task_request.agent_config.system_prompt == "You are a helpful assistant."
    assert task_request.execution_context is not None
    assert task_request.execution_context.metadata["stream_mode"] is True

    async def stream_generator():
        yield _build_live_chunk(task_request.task_id)

    communicator = _DummyCommunicator()

    engine = ExecutionEngine(MagicMock(spec=FrameworkRegistry))
    engine.execute_task_live = AsyncMock(return_value=(stream_generator(), communicator))

    session = await engine.execute_task_live_session(
        task_request, task_request.execution_context
    )
    assert isinstance(session, StreamSession)
    assert session.task_id == task_request.task_id

    collected = []
    async for chunk in session:
        collected.append(chunk)

    assert len(collected) == 1
    assert collected[0].chunk_type == TaskChunkType.TOOL_PROPOSAL
    assert collected[0].interaction_id == "call-1"

    await session.approve_tool("call-1", approved=True, user_message="Looks good")
    assert communicator.responses
    response = communicator.responses[-1]
    assert response.approved is True
    assert response.interaction_id == "call-1"

    pending = await session.list_pending_interactions()
    assert pending and pending[0].interaction_id == "call-1"

    await session.close()
    assert communicator.closed is True
    assert communicator.broker.closed is True
