# -*- coding: utf-8 -*-
"""Tool Abstract Base Class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ...contracts import ToolRequest, ToolResult


class Tool(ABC):
    """
    Abstract base class for all tools in the Aether Frame system.

    Tools provide specific functionality that can be invoked by agents
    during task execution. This includes builtin tools, external API tools,
    MCP tools, and framework-native tools.
    """

    def __init__(self, name: str, namespace: Optional[str] = None):
        """Initialize tool."""
        self.name = name
        self.namespace = namespace
        self._initialized = False

    @property
    def full_name(self) -> str:
        """Get fully qualified tool name."""
        if self.namespace:
            return f"{self.namespace}.{self.name}"
        return self.name

    @abstractmethod
    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the tool.

        Args:
            config: Tool-specific configuration
        """
        pass

    @abstractmethod
    async def execute(self, tool_request: ToolRequest) -> ToolResult:
        """
        Execute the tool with given parameters.

        Args:
            tool_request: Request containing tool parameters and context

        Returns:
            ToolResult: Result of tool execution
        """
        pass

    @abstractmethod
    async def get_schema(self) -> Dict[str, Any]:
        """
        Get tool schema definition.

        Returns:
            Dict[str, Any]: Tool schema including parameters and description
        """
        pass

    @abstractmethod
    async def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Validate tool parameters.

        Args:
            parameters: Parameters to validate

        Returns:
            bool: True if parameters are valid
        """
        pass

    @abstractmethod
    async def cleanup(self):
        """Cleanup tool resources."""
        pass

    @property
    def is_initialized(self) -> bool:
        """Check if tool is initialized."""
        return self._initialized

    async def get_capabilities(self) -> List[str]:
        """
        Get tool capabilities (default implementation).

        Returns:
            List[str]: List of capability names
        """
        return []

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform tool health check (default implementation).

        Returns:
            Dict[str, Any]: Health status information
        """
        return {
            "tool": self.full_name,
            "status": "healthy" if self.is_initialized else "not_initialized",
        }
