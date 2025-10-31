# -*- coding: utf-8 -*-
"""Response data structures for Aether Frame."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .contexts import ExecutionContext, UniversalMessage
from .enums import TaskStatus, ToolStatus
from .errors import ErrorPayload


@dataclass
class TaskResult:
    """Unified task result from framework processing."""

    task_id: str
    status: TaskStatus
    result_data: Optional[Dict[str, Any]] = None
    messages: List[UniversalMessage] = field(default_factory=list)
    tool_results: List["ToolResult"] = field(default_factory=list)
    execution_context: Optional[ExecutionContext] = None
    error_message: Optional[str] = None
    error: Optional[ErrorPayload] = None
    execution_time: Optional[float] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Session management for multi-turn conversations
    session_id: Optional[str] = None  # Session ID for follow-up requests
    agent_id: Optional[str] = None  # Agent ID for follow-up requests


@dataclass
class AgentResponse:
    """Response from agent execution."""

    agent_id: Optional[str] = None
    agent_type: str = "general"
    task_result: Optional[TaskResult] = None
    agent_state: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    error_details: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Session management for agent response
    session_id: Optional[str] = None  # Session context for response tracking


@dataclass
class ToolResult:
    """Result from tool execution."""

    tool_name: str
    status: ToolStatus
    tool_namespace: Optional[str] = None
    result_data: Optional[Any] = None
    error_message: Optional[str] = None
    error: Optional[ErrorPayload] = None
    execution_time: Optional[float] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Session management for tool result (optional)
    session_id: Optional[str] = None  # Session context if tool produces session-level state
