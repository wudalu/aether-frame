# -*- coding: utf-8 -*-
"""Streaming data structures for Aether Frame Live Execution."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Optional, Union

from .enums import InteractionType, TaskChunkType

if TYPE_CHECKING:
    pass

DEFAULT_CHUNK_VERSION = "2025-03-01"


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
