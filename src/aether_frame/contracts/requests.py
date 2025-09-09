# -*- coding: utf-8 -*-
"""Request data structures for Aether Frame."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from .contexts import UserContext, SessionContext, ExecutionContext, UniversalMessage, UniversalTool, KnowledgeSource
from .configs import AgentConfig, ExecutionConfig
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
    execution_config: Optional[ExecutionConfig] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_adk_format(self) -> Dict[str, Any]:
        """Convert to ADK task request format."""
        adk_request = {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "metadata": self.metadata
        }
        
        if self.user_context:
            adk_request["user_id"] = self.user_context.get_adk_user_id()
            
        if self.session_context:
            session_id = self.session_context.get_adk_session_id()
            if session_id:
                adk_request["session_id"] = session_id
            adk_request["conversation_history"] = [
                msg.to_adk_format() for msg in self.session_context.conversation_history
            ]
            
        if self.messages:
            adk_request["messages"] = [msg.to_adk_format() for msg in self.messages]
            
        if self.available_tools:
            adk_request["tools"] = [tool.to_adk_format() for tool in self.available_tools]
            
        if self.available_knowledge:
            adk_request["knowledge_sources"] = [
                ks.to_adk_format() for ks in self.available_knowledge
            ]
            
        return adk_request


@dataclass
class AgentRequest:
    """Request for agent execution within a framework."""
    agent_id: Optional[str] = None
    agent_type: str = "general"
    framework_type: FrameworkType = FrameworkType.ADK
    task_request: Optional[TaskRequest] = None
    agent_config: Optional[AgentConfig] = None
    runtime_options: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


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