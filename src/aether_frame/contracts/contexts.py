# -*- coding: utf-8 -*-
"""Context data structures for Aether Frame."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, TYPE_CHECKING
from .enums import FrameworkType

if TYPE_CHECKING:
    from .contexts import UniversalTool, KnowledgeSource


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
    content: Union[str, List[ContentPart]]  # Message content (text or multi-modal)
    author: Optional[str] = None  # ADK uses 'author' instead of 'role'
    name: Optional[str] = None    # AutoGen agent name identifier
    tool_calls: Optional[List[ToolCall]] = None  # Tool invocation requests
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_adk_format(self) -> Dict[str, Any]:
        """Convert to ADK native format."""
        adk_content = self.content
        if isinstance(self.content, list):
            # Convert ContentPart list to ADK parts format
            adk_parts = []
            for part in self.content:
                if part.text:
                    adk_parts.append({"text": part.text})
                elif part.function_call:
                    adk_parts.append({
                        "function_call": {
                            "name": part.function_call.tool_name,
                            "arguments": part.function_call.parameters
                        }
                    })
            adk_content = adk_parts if adk_parts else str(self.content)
        
        result = {
            "author": self.author or self.role,
            "content": adk_content
        }
        
        if self.tool_calls:
            result["tool_calls"] = [
                {
                    "name": call.tool_name,
                    "arguments": call.parameters
                } for call in self.tool_calls
            ]
        
        if self.metadata:
            result["metadata"] = self.metadata
            
        return result


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
    available_tools: List['UniversalTool'] = field(default_factory=list)
    available_knowledge: List['KnowledgeSource'] = field(default_factory=list)
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
    
    def to_adk_format(self) -> Dict[str, Any]:
        """Convert to ADK tool definition format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
            "required_permissions": self.required_permissions,
            "metadata": self.metadata
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
    
    def to_adk_format(self) -> Dict[str, Any]:
        """Convert to ADK knowledge source format."""
        return {
            "name": self.name,
            "type": self.source_type,
            "location": self.location,
            "description": self.description,
            "config": self.access_config,
            "metadata": self.metadata
        }