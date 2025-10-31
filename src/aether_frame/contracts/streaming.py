# -*- coding: utf-8 -*-
"""Streaming data structures for Aether Frame Live Execution."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Optional, Union

from .enums import InteractionType, TaskChunkType

if TYPE_CHECKING:
    pass

DEFAULT_CHUNK_VERSION = "2025-03-01"

# Chunk semantic kinds (chunk_kind values)
# These string identifiers loosely follow industry patterns used by OpenAI Responses API,
# Cohere tool streaming, and LangGraph (plan/tool/result separation) so downstream clients
# can rely on familiar naming when rendering live events.
CHUNK_KIND_PLAN_DELTA = "plan.delta"  # Incremental plan step emitted while the agent is reasoning.
CHUNK_KIND_PLAN_SUMMARY = "plan.summary"  # Consolidated plan/next action summary after planning stabilises.
CHUNK_KIND_TOOL_PROPOSAL = "tool.proposal"  # Tool invocation proposal that may require human approval.
CHUNK_KIND_TOOL_RESULT = "tool.result"  # Final tool execution result returned to the conversation transcript.
CHUNK_KIND_TOOL_PROGRESS = "tool.delta"  # Optional intermediate progress log while a tool is running.
CHUNK_KIND_TOOL_COMPLETE = "tool.complete"  # Tool wrapper completion marker (success or graceful finish).
CHUNK_KIND_TOOL_ERROR = "tool.error"  # Tool execution failure details.


@dataclass
class TaskStreamChunk:
    """Streaming execution block for real-time task processing."""

    task_id: str
    chunk_type: TaskChunkType
    sequence_id: int
    content: Union[str, Dict[str, Any]]
    timestamp: datetime = field(default_factory=datetime.now)
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_kind: Optional[str] = None
    chunk_version: str = DEFAULT_CHUNK_VERSION
    interaction_id: Optional[str] = None


@dataclass
class InteractionRequest:
    """Request for user interaction during task execution."""

    interaction_id: str
    interaction_type: InteractionType
    task_id: str
    content: Union[str, Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class InteractionResponse:
    """User response to an interaction request."""

    interaction_id: str
    interaction_type: InteractionType
    approved: bool
    response_data: Optional[Dict[str, Any]] = None
    user_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


# Type aliases for better readability
LiveSession = AsyncIterator[TaskStreamChunk]
LiveExecutionResult = tuple[LiveSession, "LiveCommunicator"]
