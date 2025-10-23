# -*- coding: utf-8 -*-
"""Task request factory with integrated tool resolution."""

import logging
from typing import Any, Dict, List, Optional

from aether_frame.contracts import (
    AgentConfig,
    ExecutionConfig,
    ExecutionContext,
    FileReference,
    KnowledgeSource,
    SessionContext,
    TaskRequest,
    UniversalMessage,
    UniversalTool,
    UserContext,
)
from aether_frame.tools.resolver import ToolResolver, ToolNotFoundError
from aether_frame.tools.service import ToolService


logger = logging.getLogger(__name__)


class TaskRequestBuilder:
    """Builder for creating TaskRequest objects with automatic tool resolution.
    
    This builder provides a user-friendly interface for creating TaskRequest objects
    while automatically resolving tool names to UniversalTool objects using the
    ToolResolver integration.
    
    Example usage:
        builder = TaskRequestBuilder(tool_service)
        task_request = await builder.create(
            task_id="my_task",
            task_type="chat",
            description="Process user request",
            tool_names=["echo", "search", "weather"]  # Automatically resolved
        )
    """
    
    def __init__(self, tool_service: ToolService):
        """Initialize the task request builder.
        
        Args:
            tool_service: The tool service instance for tool resolution
        """
        self.tool_service = tool_service
        self.tool_resolver = ToolResolver(tool_service)
        self._logger = logger
    
    async def create(
        self,
        task_id: str,
        task_type: str,
        description: str,
        tool_names: Optional[List[str]] = None,
        user_context: Optional[UserContext] = None,
        session_context: Optional[SessionContext] = None,
        execution_context: Optional[ExecutionContext] = None,
        messages: Optional[List[UniversalMessage]] = None,
        available_knowledge: Optional[List[KnowledgeSource]] = None,
        attachments: Optional[List[FileReference]] = None,
        execution_config: Optional[ExecutionConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        agent_config: Optional[AgentConfig] = None,
        agent_id: Optional[str] = None,
    ) -> TaskRequest:
        """Create a TaskRequest with automatic tool resolution.
        
        Args:
            task_id: Unique identifier for the task
            task_type: Type of task to be executed
            description: Human-readable description of the task
            tool_names: List of tool names to resolve (supports simplified names)
            user_context: User context for permissions and preferences
            session_context: Session context for conversation state
            execution_context: Execution context for runtime configuration
            messages: List of messages for multi-turn conversations
            available_knowledge: List of knowledge sources
            execution_config: Configuration for task execution
            metadata: Additional metadata for the task
            session_id: Session ID for continuing existing sessions
            agent_config: Agent configuration for creating new sessions
            agent_id: Agent ID for continuing with existing agent
            
        Returns:
            TaskRequest: Fully configured task request with resolved tools
            
        Raises:
            ToolNotFoundError: When a requested tool cannot be resolved
        """
        self._logger.info(f"Creating TaskRequest - task_id: {task_id}, tool_names: {tool_names}")
        
        # Resolve tools if tool names are provided
        available_tools: List[UniversalTool] = []
        if tool_names:
            try:
                available_tools = await self.tool_resolver.resolve_tools(
                    tool_names, user_context
                )
                self._logger.info(
                    f"Successfully resolved {len(available_tools)} tools: "
                    f"{[tool.name for tool in available_tools]}"
                )
            except ToolNotFoundError as e:
                self._logger.error(f"Tool resolution failed for task {task_id}: {e}")
                raise
        
        # Create TaskRequest with resolved tools
        task_request = TaskRequest(
            task_id=task_id,
            task_type=task_type,
            description=description,
            user_context=user_context,
            session_context=session_context,
            execution_context=execution_context,
            messages=messages or [],
            available_tools=available_tools,
            available_knowledge=available_knowledge or [],
             attachments=attachments or [],
            execution_config=execution_config,
            metadata=metadata or {},
            session_id=session_id,
            agent_config=agent_config,
            agent_id=agent_id,
        )
        
        self._logger.debug(f"TaskRequest created successfully - task_id: {task_id}")
        return task_request
    
    async def create_with_manual_tools(
        self,
        task_id: str,
        task_type: str,
        description: str,
        available_tools: List[UniversalTool],
        **kwargs
    ) -> TaskRequest:
        """Create a TaskRequest with manually provided UniversalTool objects.
        
        This method bypasses tool resolution and uses pre-configured UniversalTool
        objects directly. Useful for advanced use cases or testing.
        
        Args:
            task_id: Unique identifier for the task
            task_type: Type of task to be executed
            description: Human-readable description of the task
            available_tools: Pre-configured UniversalTool objects
            **kwargs: Additional TaskRequest parameters
            
        Returns:
            TaskRequest: Task request with manually provided tools
        """
        self._logger.info(
            f"Creating TaskRequest with manual tools - task_id: {task_id}, "
            f"tool_count: {len(available_tools)}"
        )
        
        task_request = TaskRequest(
            task_id=task_id,
            task_type=task_type,
            description=description,
            available_tools=available_tools,
            messages=kwargs.get('messages', []),
            available_knowledge=kwargs.get('available_knowledge', []),
            attachments=kwargs.get('attachments', []),
            metadata=kwargs.get('metadata', {}),
            **kwargs
        )
        
        self._logger.debug(f"TaskRequest with manual tools created - task_id: {task_id}")
        return task_request
    
    async def list_available_tools(
        self, 
        user_context: Optional[UserContext] = None,
        namespace_filter: Optional[str] = None
    ) -> List[UniversalTool]:
        """List tools available for task creation.
        
        Args:
            user_context: User context for permission filtering
            namespace_filter: Optional namespace to filter by
            
        Returns:
            List of available UniversalTool objects
        """
        return await self.tool_resolver.list_available_tools(
            namespace_filter=namespace_filter,
            user_context=user_context
        )


class TaskRequestFactory:
    """Factory class for creating TaskRequest objects with tool resolution.
    
    This is a convenience wrapper around TaskRequestBuilder that provides
    a simpler interface for common use cases.
    
    Example usage:
        factory = TaskRequestFactory(tool_service)
        
        # Simple task with tools
        task = await factory.create_chat_task(
            task_id="chat_001",
            description="Help user with search",
            tools=["search", "echo"]
        )
        
        # Task without tools
        task = await factory.create_simple_task(
            task_id="simple_001",
            task_type="processing",
            description="Process data"
        )
    """
    
    def __init__(self, tool_service: ToolService):
        """Initialize the task request factory.
        
        Args:
            tool_service: The tool service instance for tool resolution
        """
        self.builder = TaskRequestBuilder(tool_service)
        self._logger = logger
    
    async def create_chat_task(
        self,
        task_id: str,
        description: str,
        tools: Optional[List[str]] = None,
        user_context: Optional[UserContext] = None,
        messages: Optional[List[UniversalMessage]] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> TaskRequest:
        """Create a chat task with optional tools.
        
        Args:
            task_id: Unique task identifier
            description: Task description
            tools: Optional list of tool names to resolve
            user_context: User context for permissions
            messages: Chat messages for multi-turn conversations
            session_id: Session ID for conversation continuity
            **kwargs: Additional TaskRequest parameters
            
        Returns:
            TaskRequest: Configured chat task
        """
        return await self.builder.create(
            task_id=task_id,
            task_type="chat",
            description=description,
            tool_names=tools,
            user_context=user_context,
            messages=messages,
            session_id=session_id,
            **kwargs
        )
    
    async def create_simple_task(
        self,
        task_id: str,
        task_type: str,
        description: str,
        **kwargs
    ) -> TaskRequest:
        """Create a simple task without tools.
        
        Args:
            task_id: Unique task identifier
            task_type: Type of task
            description: Task description
            **kwargs: Additional TaskRequest parameters
            
        Returns:
            TaskRequest: Configured simple task
        """
        return await self.builder.create(
            task_id=task_id,
            task_type=task_type,
            description=description,
            tool_names=None,
            **kwargs
        )
    
    async def create_tool_task(
        self,
        task_id: str,
        description: str,
        tools: List[str],
        user_context: Optional[UserContext] = None,
        **kwargs
    ) -> TaskRequest:
        """Create a task specifically focused on tool usage.
        
        Args:
            task_id: Unique task identifier
            description: Task description
            tools: List of tool names to resolve (required)
            user_context: User context for permissions
            **kwargs: Additional TaskRequest parameters
            
        Returns:
            TaskRequest: Configured tool task
        """
        if not tools:
            raise ValueError("Tool task requires at least one tool")
        
        return await self.builder.create(
            task_id=task_id,
            task_type="tool_execution",
            description=description,
            tool_names=tools,
            user_context=user_context,
            **kwargs
        )
