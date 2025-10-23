# -*- coding: utf-8 -*-
"""Request data structures for Aether Frame."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .configs import AgentConfig, ExecutionConfig
from .contexts import (
    FileReference,
    ExecutionContext,
    KnowledgeSource,
    SessionContext,
    UniversalMessage,
    UniversalTool,
    UserContext,
)
from .enums import FrameworkType


@dataclass
class TaskRequest:
    """Unified task request for framework-agnostic processing."""

    task_id: str
    task_type: str
    description: str
    user_context: Optional[UserContext] = None
    session_context: Optional[SessionContext] = None
    execution_context: Optional[ExecutionContext] = None
    messages: List[UniversalMessage] = field(default_factory=list)
    available_tools: List[UniversalTool] = field(default_factory=list)
    available_knowledge: List[KnowledgeSource] = field(default_factory=list)
    attachments: List[FileReference] = field(default_factory=list)
    execution_config: Optional[ExecutionConfig] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Session management for multi-turn conversations
    session_id: Optional[str] = None  # For continuing existing sessions
    agent_config: Optional[AgentConfig] = None  # For creating new sessions
    agent_id: Optional[str] = None  # For continuing with existing agent



@dataclass
class AgentRequest:
    """Request for agent execution within a framework."""

    agent_type: str = "general"
    framework_type: FrameworkType = FrameworkType.ADK
    task_request: Optional[TaskRequest] = None
    agent_config: Optional[AgentConfig] = None
    runtime_options: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Session management for agent execution
    session_id: Optional[str] = None  # Session context for agent execution


@dataclass
class ToolRequest:
    """Request for tool execution."""

    tool_name: str
    tool_namespace: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    user_context: Optional[UserContext] = None
    session_context: Optional[SessionContext] = None
    execution_context: Optional[ExecutionContext] = None
    timeout: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Session management for tool execution
    session_id: Optional[str] = None  # Session context for tool execution
