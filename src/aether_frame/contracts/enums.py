# -*- coding: utf-8 -*-
"""Enumeration types for Aether Frame data contracts."""

from enum import Enum


class FrameworkType(Enum):
    """Supported agent frameworks."""

    ADK = "adk"
    AUTOGEN = "autogen"
    LANGGRAPH = "langgraph"


class TaskStatus(Enum):
    """Task execution status."""

    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ErrorCategory(Enum):
    """High-level error classification for observability."""

    INITIALIZATION = "initialization"
    RUNTIME_CONTEXT = "runtime_context"
    MODEL_INVOCATION = "model_invocation"
    TOOL_CALL = "tool_call"
    STREAM_INTERRUPTED = "stream_interrupted"
    SYSTEM = "system"


class ToolStatus(Enum):
    """Tool execution status."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"


class TaskComplexity(Enum):
    """Task complexity levels for strategy selection."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    ADVANCED = "advanced"


class ExecutionMode(Enum):
    """Execution modes."""

    SYNC = "sync"
    ASYNC = "async"
    STREAMING = "streaming"
    BATCH = "batch"
    INTERACTIVE = "interactive"  # New: Live streaming mode


class AgentStatus(Enum):
    """Agent lifecycle status."""

    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    IDLE = "idle"
    ERROR = "error"
    CLEANUP = "cleanup"
    TERMINATED = "terminated"


class TaskChunkType(Enum):
    """Streaming task chunk types for live execution."""

    PROCESSING = "processing"
    PLAN_DELTA = "plan_delta"
    PLAN_SUMMARY = "plan_summary"
    TOOL_CALL_REQUEST = "tool_call_request"
    TOOL_APPROVAL_REQUEST = "tool_approval_request"
    TOOL_PROPOSAL = "tool_proposal"
    TOOL_RESULT = "tool_result"
    USER_INPUT_REQUEST = "user_input_request"
    RESPONSE = "response"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


class InteractionType(Enum):
    """Types of user interactions during live execution."""

    TOOL_APPROVAL = "tool_approval"
    USER_INPUT = "user_input"
    CONFIRMATION = "confirmation"
    CANCELLATION = "cancellation"
