"""Tests for ADK event converter streaming chunks."""

from unittest.mock import MagicMock

import pytest

from src.aether_frame.agents.adk.adk_event_converter import AdkEventConverter
from src.aether_frame.contracts import TaskChunkType


@pytest.fixture
def converter():
    return AdkEventConverter()


def _make_adk_event():
    event = MagicMock()
    event.metadata = {}
    event.content = MagicMock()
    event.content.parts = [MagicMock()]
    return event


def test_plan_delta_conversion(converter):
    plan_event = MagicMock()
    plan_event.metadata = {"stage": "plan", "plan_text": "Step 1: gather info"}
    plan_event.custom_metadata = None
    plan_event.content = None

    chunks = converter.convert_adk_event_to_chunk(plan_event, "task-1", 0)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == TaskChunkType.PLAN_DELTA
    assert chunk.content == {"text": "Step 1: gather info"}
    assert chunk.chunk_kind == "plan.delta"
    assert chunk.metadata["stage"] == "plan"


def test_plan_delta_with_custom_metadata(converter):
    plan_event = MagicMock()
    plan_event.metadata = None
    plan_event.custom_metadata = {"stage": "plan", "plan_text": "Step 1: gather info", "source": "deepseek.reasoning"}
    plan_event.content = None

    chunks = converter.convert_adk_event_to_chunk(plan_event, "task-1", 0)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == TaskChunkType.PLAN_DELTA
    assert chunk.metadata["stage"] == "plan"
    assert chunk.metadata["source"] == "deepseek.reasoning"


def test_metadata_merging_metadata_and_custom(converter):
    plan_event = MagicMock()
    plan_event.metadata = {"stage": "plan", "plan_text": "Step 1: gather info"}
    plan_event.custom_metadata = {"source": "deepseek.reasoning"}
    plan_event.content = None

    chunks = converter.convert_adk_event_to_chunk(plan_event, "task-1", 0)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.metadata["stage"] == "plan"
    assert chunk.metadata["source"] == "deepseek.reasoning"


def test_tool_proposal_conversion(converter):
    event = _make_adk_event()
    function_call = MagicMock()
    function_call.name = "lookup_customer"
    function_call.args = {"customer_id": "42"}
    function_call.id = "call-42"
    event.content.parts[0].function_call = function_call
    event.metadata = {"requires_approval": True}

    chunks = converter.convert_adk_event_to_chunk(event, "task-1", 1)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == TaskChunkType.TOOL_PROPOSAL
    assert chunk.content["tool_name"] == "lookup_customer"
    assert chunk.content["arguments"] == {"customer_id": "42"}
    assert chunk.interaction_id == "call-42"
    assert chunk.metadata["stage"] == "tool"
    assert chunk.chunk_kind == "tool.proposal"


def test_tool_result_conversion(converter):
    # Register proposal first to seed pending interactions
    proposal_event = _make_adk_event()
    proposal_call = MagicMock()
    proposal_call.name = "lookup_customer"
    proposal_call.args = {"customer_id": "42"}
    proposal_call.id = "call-42"
    proposal_event.content.parts[0].function_call = proposal_call
    proposal_event.metadata = {"requires_approval": True}
    converter.convert_adk_event_to_chunk(proposal_event, "task-1", 1)

    result_event = MagicMock()
    result_event.metadata = {"stage": "tool_result"}
    result_event.content = MagicMock()
    result_part = MagicMock()
    result_part.function_call = None
    response_payload = MagicMock()
    response_payload.result = {"balance": 100}
    response_payload.name = "lookup_customer"
    response_payload.id = "call-42"
    result_part.function_response = response_payload
    result_event.content.parts = [result_part]

    chunks = converter.convert_adk_event_to_chunk(result_event, "task-1", 2)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == TaskChunkType.TOOL_RESULT
    assert chunk.content == {"balance": 100}
    assert chunk.interaction_id == "call-42"
    assert chunk.metadata["tool_name"] == "lookup_customer"
    assert chunk.chunk_kind == "tool.result"


def test_tool_result_without_prior_proposal_generates_synthetic_proposal(converter):
    result_event = MagicMock()
    result_event.metadata = {"tool_name": "lookup_customer", "tool_namespace": "builtin"}
    result_event.content = MagicMock()
    result_part = MagicMock()
    result_part.function_call = None
    response_payload = MagicMock()
    response_payload.result = {"balance": 250}
    response_payload.name = "lookup_customer"
    response_payload.id = None
    result_part.function_response = response_payload
    result_event.content.parts = [result_part]

    chunks = converter.convert_adk_event_to_chunk(result_event, "task-1", 0)

    assert len(chunks) == 2
    proposal_chunk, result_chunk = chunks

    assert proposal_chunk.chunk_type == TaskChunkType.TOOL_PROPOSAL
    assert proposal_chunk.chunk_kind == "tool.proposal"
    assert proposal_chunk.content["tool_name"] == "lookup_customer"

    assert result_chunk.chunk_type == TaskChunkType.TOOL_RESULT
    assert result_chunk.content == {"balance": 250}
    assert result_chunk.chunk_kind == "tool.result"
    assert result_chunk.interaction_id == proposal_chunk.interaction_id
