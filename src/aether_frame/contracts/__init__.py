# -*- coding: utf-8 -*-
"""Data contracts for Aether Frame multi-agent system.

This module contains all the data structures that define contracts between
different layers of the architecture:

- requests.py: Request data structures (TaskRequest, AgentRequest, ToolRequest)
- responses.py: Response data structures (TaskResult, AgentResponse, ToolResult)  
- contexts.py: Context data structures (UserContext, SessionContext, ExecutionContext)
- configs.py: Configuration data structures (AgentConfig, ExecutionConfig, StrategyConfig)
- enums.py: Enumerations (FrameworkType, TaskStatus, ToolStatus, etc.)
"""

from .requests import TaskRequest, AgentRequest, ToolRequest
from .responses import TaskResult, AgentResponse, ToolResult
from .contexts import (
    UserContext, SessionContext, ExecutionContext,
    UserPermissions, UserPreferences,
    UniversalMessage, UniversalTool, KnowledgeSource,
    ToolCall, FileReference, ImageReference, ContentPart
)
from .configs import AgentConfig, ExecutionConfig, StrategyConfig
from .enums import FrameworkType, TaskStatus, ToolStatus, TaskComplexity, ExecutionMode, AgentStatus

__all__ = [
    # Request types
    "TaskRequest",
    "AgentRequest", 
    "ToolRequest",
    
    # Response types
    "TaskResult",
    "AgentResponse",
    "ToolResult",
    
    # Context types
    "UserContext",
    "SessionContext", 
    "ExecutionContext",
    "UserPermissions",
    "UserPreferences",
    "UniversalMessage",
    "UniversalTool",
    "KnowledgeSource",
    "ToolCall",
    "FileReference",
    "ImageReference",
    "ContentPart",
    
    # Configuration types
    "AgentConfig",
    "ExecutionConfig",
    "StrategyConfig",
    
    # Enums
    "FrameworkType",
    "TaskStatus",
    "ToolStatus", 
    "TaskComplexity",
    "ExecutionMode",
    "AgentStatus",
]