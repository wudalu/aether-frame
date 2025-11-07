# -*- coding: utf-8 -*-
"""Unit tests for StreamSession helper methods."""

import pytest

from aether_frame.contracts import InteractionResponse, InteractionType
from aether_frame.streaming.stream_session import StreamSession, create_stream_session


class AsyncIteratorStub:
    def __init__(self):
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

    async def aclose(self):
        self.closed = True


class BrokerStub:
    def __init__(self, items=None):
        self.items = items or []
        self.closed = False

    async def list_pending_interactions(self):
        return list(self.items)

    def close(self):
        self.closed = True


class CommunicatorStub:
    def __init__(self, broker=None):
        self.messages = []
        self.responses = []
        self.cancellations = []
        self.closed = False
        self.broker = broker

    async def send_user_message(self, message):
        self.messages.append(message)

    async def send_user_response(self, response: InteractionResponse):
        self.responses.append(response)

    async def send_cancellation(self, reason: str = "user_cancelled"):
        self.cancellations.append(reason)

    def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_send_user_message_and_response_passthrough():
    streamer = AsyncIteratorStub()
    communicator = CommunicatorStub()
    session = StreamSession(task_id="task-1", event_stream=streamer, communicator=communicator)

    await session.send_user_message("hello")
    response = InteractionResponse(
        interaction_id="int-1",
        interaction_type=InteractionType.USER_INPUT,
        approved=True,
    )
    await session.send_interaction_response(response)

    assert communicator.messages == ["hello"]
    assert communicator.responses == [response]


@pytest.mark.asyncio
async def test_approve_tool_builds_interaction_response():
    streamer = AsyncIteratorStub()
    communicator = CommunicatorStub()
    session = StreamSession(task_id="task-2", event_stream=streamer, communicator=communicator)

    await session.approve_tool(
        "tool-1",
        approved=False,
        user_message="needs review",
        response_data={"status": "denied"},
        metadata={"origin": "test"},
    )

    assert len(communicator.responses) == 1
    response = communicator.responses[0]
    assert response.interaction_id == "tool-1"
    assert response.interaction_type == InteractionType.TOOL_APPROVAL
    assert response.approved is False
    assert response.user_message == "needs review"
    assert response.response_data == {"status": "denied"}
    assert response.metadata == {"origin": "test"}


@pytest.mark.asyncio
async def test_cancel_and_close_cleanup_resources():
    broker = BrokerStub()
    streamer = AsyncIteratorStub()
    communicator = CommunicatorStub(broker=broker)
    session = StreamSession(task_id="task-3", event_stream=streamer, communicator=communicator)

    await session.cancel("timeout")
    await session.close()
    await session.close()  # second call should be no-op

    assert communicator.cancellations == ["timeout"]
    assert communicator.closed is True
    assert broker.closed is True
    assert streamer.closed is True


@pytest.mark.asyncio
async def test_list_pending_interactions_with_broker():
    pending = [
        {
            "interaction_id": "i-1",
            "tool_name": "search",
            "created_at": "2025-01-01T00:00:00Z",
            "expires_at": None,
            "requires_approval": True,
            "metadata": {"severity": "high"},
        }
    ]
    communicator = CommunicatorStub(broker=BrokerStub(items=pending))
    session = StreamSession(task_id="task-4", event_stream=AsyncIteratorStub(), communicator=communicator)

    interactions = await session.list_pending_interactions()

    assert len(interactions) == 1
    assert interactions[0].interaction_id == "i-1"
    assert interactions[0].tool_name == "search"
    assert interactions[0].metadata == {"severity": "high"}


@pytest.mark.asyncio
async def test_list_pending_interactions_without_broker():
    session = StreamSession(task_id="task-5", event_stream=AsyncIteratorStub(), communicator=CommunicatorStub())
    interactions = await session.list_pending_interactions()
    assert interactions == []


@pytest.mark.asyncio
async def test_create_stream_session_factory():
    streamer = AsyncIteratorStub()
    communicator = CommunicatorStub()
    session = create_stream_session("task-6", (streamer, communicator))
    assert isinstance(session, StreamSession)
    assert session.task_id == "task-6"
