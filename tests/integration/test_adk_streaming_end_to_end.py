"""Integration test covering ADK streaming pipeline end-to-end."""

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from src.aether_frame.contracts import (
    ExecutionContext,
    FrameworkType,
    RuntimeContext,
    TaskChunkType,
    TaskRequest,
    TaskStreamChunk,
    UserContext,
)
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from src.aether_frame.agents.base.domain_agent import DomainAgent
from src.aether_frame.agents.adk.adk_event_converter import AdkEventConverter
from src.aether_frame.execution.execution_engine import ExecutionEngine
from src.aether_frame.framework.framework_registry import FrameworkRegistry
from src.aether_frame.framework.base.live_communicator import LiveCommunicator


class _StubCommunicator(LiveCommunicator):
    """Minimal communicator recording sent responses."""

    def __init__(self):
        self.sent_responses: List[Any] = []

    async def send_user_response(self, response):
        self.sent_responses.append(response)

    async def send_user_message(self, message: str):
        return None

    async def send_cancellation(self, reason: str):
        return None

    def close(self):
        return None


class _StreamingDomainAgent(DomainAgent):
    """Domain agent that uses AdkEventConverter to produce streaming chunks."""

    def __init__(self):
        super().__init__("agent-123", {}, {})
        self.event_converter = AdkEventConverter()

    async def initialize(self):
        return None

    async def execute(self, agent_request):
        return None

    async def get_state(self) -> Dict[str, Any]:
        return {}

    async def cleanup(self):
        return None

    def _event_sequence(self):
        """Craft synthetic ADK events that exercise plan/tool/result workflow."""
        plan_event = SimpleNamespace(
            metadata={"stage": "plan", "plan_text": "Step 1: gather account context"},
            content=None,
        )

        tool_call = SimpleNamespace(name="lookup_customer", args={"customer_id": "42"}, id="call-42")
        tool_part = SimpleNamespace(function_call=tool_call)
        tool_event = SimpleNamespace(
            metadata={"stage": "tool", "requires_approval": True},
            content=SimpleNamespace(parts=[tool_part]),
            author="agent",
        )

        response_payload = SimpleNamespace(result={"balance": 100}, name="lookup_customer", id="call-42")
        result_part = SimpleNamespace(function_response=response_payload, function_call=None)
        result_event = SimpleNamespace(
            metadata={"stage": "tool_result"},
            content=SimpleNamespace(parts=[result_part]),
            author="agent",
        )

        text_part = SimpleNamespace(text="Customer 42 has a balance of 100 credits.")
        text_event = SimpleNamespace(
            metadata={},
            content=SimpleNamespace(parts=[text_part]),
            partial=False,
            author="assistant",
            id="resp-1",
            turn_complete=True,
        )

        return [plan_event, tool_event, result_event, text_event]

    async def execute_live(self, task_request):
        events = self._event_sequence()
        communicator = _StubCommunicator()

        async def stream():
            sequence_id = 0
            for event in events:
                chunk = self.event_converter.convert_adk_event_to_chunk(
                    event, task_request.task_id, sequence_id
                )
                if chunk is not None:
                    yield chunk
                    sequence_id += 1

        return stream(), communicator


@pytest.mark.asyncio
async def test_adk_streaming_end_to_end(monkeypatch):
    adapter = AdkFrameworkAdapter()
    adapter._initialized = True
    adapter._config.update(
        {
            "tool_approval_timeout_seconds": 30,
            "tool_approval_timeout_policy": "auto_cancel",
        }
    )

    # Stub session coordination to avoid dependency on real ADK runtime.
    async def fake_coordinate(*args, **kwargs):
        return SimpleNamespace(adk_session_id="adk-session-123", switch_occurred=False)

    adapter.adk_session_manager.coordinate_chat_session = fake_coordinate
    adapter.runner_manager.mark_runner_activity = lambda runner_id: None

    streaming_agent = _StreamingDomainAgent()
    runtime_context = RuntimeContext(
        session_id="adk-session-123",
        user_id="user-1",
        framework_type=FrameworkType.ADK,
        agent_id="agent-123",
        runner_id="runner-1",
        runner_context={},
        framework_session=SimpleNamespace(),
        tool_service=None,
    )
    runtime_context.metadata["domain_agent"] = streaming_agent
    runtime_context.metadata["adk_session_id"] = "adk-session-123"

    async def fake_runtime_context(task_request):
        return runtime_context

    adapter._create_runtime_context_for_existing_session = fake_runtime_context

    registry = FrameworkRegistry()
    registry.register_adapter(FrameworkType.ADK, adapter)
    registry._initialization_status[FrameworkType.ADK] = True

    engine = ExecutionEngine(framework_registry=registry)

    task_request = TaskRequest(
        task_id="task-stream-123",
        task_type="chat",
        description="Verify ADK streaming end-to-end",
        agent_id="agent-123",
        session_id="chat-session-456",
        user_context=UserContext(user_id="user-1"),
        messages=[],
    )
    execution_context = ExecutionContext(
        execution_id="exec-123",
        framework_type=FrameworkType.ADK,
        execution_mode="live",
    )

    live_stream, communicator = await engine.execute_task_live(task_request, execution_context)

    chunks: List[TaskStreamChunk] = []
    async for chunk in live_stream:
        chunks.append(chunk)

    chunk_types = [chunk.chunk_type for chunk in chunks]
    assert chunk_types == [
        TaskChunkType.PLAN_DELTA,
        TaskChunkType.TOOL_PROPOSAL,
        TaskChunkType.TOOL_RESULT,
        TaskChunkType.RESPONSE,
    ]

    proposal_chunk = chunks[1]
    result_chunk = chunks[2]

    assert proposal_chunk.interaction_id is not None
    assert proposal_chunk.metadata["stage"] == "tool"
    assert result_chunk.interaction_id == proposal_chunk.interaction_id
    assert result_chunk.metadata["tool_name"] == "lookup_customer"

    # Communicator should be wrapped by ApprovalAwareCommunicator
    assert hasattr(communicator, "send_user_response")
