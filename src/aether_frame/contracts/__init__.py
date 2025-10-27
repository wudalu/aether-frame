# -*- coding: utf-8 -*-
"""Data contracts for Aether Frame multi-agent system.

This module contains all the data structures that define contracts between
different layers of the architecture:

- requests.py: Request data structures (TaskRequest, AgentRequest,
  ToolRequest)
- responses.py: Response data structures (TaskResult, AgentResponse,
  ToolResult)
- contexts.py: Context data structures (UserContext, SessionContext,
  ExecutionContext)
- configs.py: Configuration data structures (AgentConfig, ExecutionConfig,
  StrategyConfig)
- enums.py: Enumerations (FrameworkType, TaskStatus, ToolStatus, etc.)
- streaming.py: Live streaming data structures (TaskStreamChunk,
  InteractionRequest, etc.)
"""

from .configs import AgentConfig, ExecutionConfig, StrategyConfig
from .contexts import (
    ContentPart,
    ExecutionContext,
    FileReference,
    ImageReference,
    KnowledgeSource,
    RuntimeContext,
    SessionContext,
    ToolCall,
    UniversalMessage,
    UniversalTool,
    UserContext,
    UserPermissions,
    UserPreferences,
)
from .enums import (
    AgentStatus,
    ExecutionMode,
    FrameworkType,
    InteractionType,
    TaskChunkType,
    TaskComplexity,
    TaskStatus,
    ToolStatus,
)
from .requests import AgentRequest, TaskRequest, ToolRequest
from .responses import AgentResponse, TaskResult, ToolResult
from .streaming import (
    DEFAULT_CHUNK_VERSION,
    InteractionRequest,
    InteractionResponse,
    LiveExecutionResult,
    LiveSession,
    TaskStreamChunk,
)

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
    "RuntimeContext",
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
    # Streaming types
    "TaskStreamChunk",
    "InteractionRequest",
    "InteractionResponse",
    "LiveSession",
    "LiveExecutionResult",
    "DEFAULT_CHUNK_VERSION",
    # Enums
    "FrameworkType",
    "TaskStatus",
    "ToolStatus",
    "TaskComplexity",
    "ExecutionMode",
    "AgentStatus",
    "TaskChunkType",
    "InteractionType",
]
