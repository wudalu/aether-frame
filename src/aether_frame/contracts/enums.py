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


class AgentStatus(Enum):
    """Agent lifecycle status."""

    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    IDLE = "idle"
    ERROR = "error"
    CLEANUP = "cleanup"
    TERMINATED = "terminated"
