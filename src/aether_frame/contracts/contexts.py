# -*- coding: utf-8 -*-
"""Context data structures for Aether Frame."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from .enums import FrameworkType

if TYPE_CHECKING:
    pass


@dataclass
class UserPermissions:
    """User access permissions."""

    permissions: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    restrictions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserPreferences:
    """User preference settings."""

    language: str = "en"
    timezone: str = "UTC"
    preferred_framework: Optional[FrameworkType] = None
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserContext:
    """Flexible user identification supporting different frameworks."""

    user_id: Optional[str] = None  # Explicit user identifier (ADK required)
    user_name: Optional[str] = None  # Human-readable username
    session_token: Optional[str] = None  # Session-based identification
    permissions: Optional[UserPermissions] = None  # User access permissions
    preferences: Optional[UserPreferences] = None  # User preference settings

    def get_adk_user_id(self) -> str:
        """Get or generate user_id for ADK compatibility."""
        if self.user_id:
            return self.user_id
        if self.user_name:
            return f"user_{self.user_name}"
        if self.session_token:
            return f"session_{self.session_token[:8]}"
        return "anonymous_user"


@dataclass
class ToolCall:
    """Tool invocation request."""

    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    tool_namespace: Optional[str] = None
    call_id: Optional[str] = None


@dataclass
class FileReference:
    """File reference for multi-modal content."""

    file_path: str
    file_type: str
    file_size: Optional[int] = None
    encoding: str = "utf-8"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageReference:
    """Image reference for multi-modal content."""

    image_path: str
    image_format: str
    width: Optional[int] = None
    height: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentPart:
    """Multi-modal content part compatible with ADK parts structure."""

    text: Optional[str] = None
    function_call: Optional[ToolCall] = None
    file_reference: Optional[FileReference] = None
    image_reference: Optional[ImageReference] = None


@dataclass
class UniversalMessage:
    """Framework-agnostic message format with ADK compatibility."""

    role: str  # Message role: "user", "assistant", "system", "tool"
    # Message content (text or multi-modal)
    content: Union[str, List[ContentPart]]
    author: Optional[str] = None  # ADK uses 'author' instead of 'role'
    name: Optional[str] = None  # AutoGen agent name identifier
    tool_calls: Optional[List[ToolCall]] = None  # Tool invocation requests
    metadata: Dict[str, Any] = field(default_factory=dict)



@dataclass
class SessionContext:
    """Unified session management across frameworks."""

    session_id: Optional[str] = None  # ADK-compatible session identifier
    conversation_id: Optional[str] = None  # Alternative session tracking ID
    conversation_history: List[UniversalMessage] = field(default_factory=list)
    session_state: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None

    def get_adk_session_id(self) -> Optional[str]:
        """Get ADK-compatible session_id."""
        return self.session_id or self.conversation_id


@dataclass
class ExecutionContext:
    """Execution context for task processing."""

    execution_id: str
    framework_type: FrameworkType
    execution_mode: str = "sync"
    timeout: Optional[int] = None
    available_tools: List["UniversalTool"] = field(default_factory=list)
    available_knowledge: List["KnowledgeSource"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None


@dataclass
class UniversalTool:
    """Universal tool definition for framework-agnostic tool usage."""

    name: str
    description: str
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    namespace: Optional[str] = None
    required_permissions: List[str] = field(default_factory=list)
    supports_streaming: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)



@dataclass
class RuntimeContext:
    """Runtime execution context for framework adapters.
    
    This context consolidates all runtime state needed during task execution,
    including agent, session, and framework-specific information.
    
    TODO: This class has overlapping fields with ExecutionContext, 
    SessionContext, and UserContext. After the execute_task refactor 
    is complete, we should consolidate the Context architecture.
    """
    
    # Core identifiers (required)
    session_id: str
    user_id: str  
    framework_type: FrameworkType
    
    # Agent runtime state
    agent_id: Optional[str] = None
    agent_config: Optional["AgentConfig"] = None
    
    # Framework-specific runtime state
    runner_id: Optional[str] = None
    runner_context: Optional[Dict[str, Any]] = None
    framework_session: Optional[Any] = None  # ADK Session, AutoGen Conversation, etc.
    
    # Services and tools
    tool_service: Optional[Any] = None
    
    # Execution tracking (TODO: overlaps with ExecutionContext)
    execution_id: Optional[str] = None
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps (TODO: overlaps with SessionContext)
    created_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def get_runtime_dict(self) -> Dict[str, Any]:
        """Get runtime context as dictionary for backward compatibility."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "framework_type": self.framework_type,
            "agent_id": self.agent_id,
            "agent_config": self.agent_config,
            "runner": self.runner_context.get("runner") if self.runner_context else None,
            "session_service": self.runner_context.get("session_service") if self.runner_context else None,
            "adk_session": self.framework_session,
            "tool_service": self.tool_service,
            "runner_context": self.runner_context,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            **self.metadata
        }


@dataclass
class KnowledgeSource:
    """Knowledge source definition for agent access."""

    name: str
    source_type: str  # "file", "database", "api", "vector_store"
    location: str
    description: str
    access_config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

