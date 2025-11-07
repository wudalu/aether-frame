# -*- coding: utf-8 -*-
"""Unit tests for AdkApprovalBroker coordination logic."""

import asyncio

import pytest

from aether_frame.contracts import (
    InteractionResponse,
    InteractionType,
    TaskChunkType,
    TaskStreamChunk,
)
from aether_frame.framework.adk.approval_broker import (
    AdkApprovalBroker,
    ApprovalAwareCommunicator,
)


class CommunicatorStub:
    def __init__(self):
        self.responses = []
        self.cancellations = []
        self.messages = []
        self.closed = False

    async def send_user_response(self, response: InteractionResponse) -> None:
        self.responses.append(response)

    async def send_cancellation(self, reason: str = "user_cancelled") -> None:
        self.cancellations.append(reason)

    async def send_user_message(self, message: str) -> None:
        self.messages.append(message)

    def close(self) -> None:
        self.closed = True


def make_tool_chunk(sequence_id: int = 1, tool_name: str = "builtin.echo") -> TaskStreamChunk:
    return TaskStreamChunk(
        task_id="task-1",
        chunk_type=TaskChunkType.TOOL_PROPOSAL,
        sequence_id=sequence_id,
        content={"tool_name": tool_name, "arguments": {"value": 1}},
        metadata={"tool_name": tool_name, "requires_approval": True},
    )


@pytest.mark.asyncio
async def test_register_and_resolve_tool_proposal():
    communicator = CommunicatorStub()
    broker = AdkApprovalBroker(communicator, timeout_seconds=5)

    chunk = make_tool_chunk()
    await broker.on_chunk(chunk)

    wait_task = asyncio.create_task(broker.wait_for_tool_approval("builtin.echo", {"value": 1}))

    response = InteractionResponse(
        interaction_id=chunk.interaction_id,
        interaction_type=InteractionType.TOOL_APPROVAL,
        approved=True,
    )
    await broker.resolve(chunk.interaction_id, response)

    result = await wait_task
    assert result["approved"] is True
    assert communicator.responses == []


@pytest.mark.asyncio
async def test_timeout_fallback_triggers_auto_cancel():
    communicator = CommunicatorStub()
    broker = AdkApprovalBroker(
        communicator,
        timeout_seconds=0.01,
        fallback_policy="auto_cancel",
    )

    chunk = make_tool_chunk()
    await broker.on_chunk(chunk)
    await broker.finalize()

    assert communicator.responses
    timeout_response = communicator.responses[0]
    assert timeout_response.approved is False
    assert timeout_response.metadata["auto_timeout"] is True


@pytest.mark.asyncio
async def test_list_pending_interactions_returns_metadata():
    communicator = CommunicatorStub()
    broker = AdkApprovalBroker(communicator, timeout_seconds=10)

    chunk = make_tool_chunk(sequence_id=2, tool_name="custom.search")
    await broker.on_chunk(chunk)

    items = await broker.list_pending_interactions()
    assert len(items) == 1
    assert items[0]["tool_name"] == "custom.search"
    assert "expires_at" in items[0]


@pytest.mark.asyncio
async def test_approval_aware_communicator_resolves_on_response():
    delegate = CommunicatorStub()
    broker = AdkApprovalBroker(delegate, timeout_seconds=5)
    communicator = ApprovalAwareCommunicator(delegate, broker)

    chunk = make_tool_chunk()
    await broker.on_chunk(chunk)

    response = InteractionResponse(
        interaction_id=chunk.interaction_id,
        interaction_type=InteractionType.TOOL_APPROVAL,
        approved=True,
    )
    await communicator.send_user_response(response)
    result = await broker.wait_for_tool_approval("builtin.echo", {"value": 1})

    assert delegate.responses == [response]
    assert result["approved"] is True

    communicator.close()
    assert delegate.closed is True
