# -*- coding: utf-8 -*-
"""Tool Service - Unified tool execution interface."""

from typing import Any, Dict, List, Optional

from ..contracts import ToolRequest, ToolResult, ToolStatus
from .base.tool import Tool


class ToolService:
    """
    Unified tool execution service.

    Provides a centralized interface for tool discovery, registration,
    execution, and management across different tool types including
    builtin tools, MCP tools, ADK native tools, and external API tools.
    """

    def __init__(self):
        """Initialize tool service."""
        self._tools: Dict[str, Tool] = {}
        self._tool_namespaces: Dict[str, List[str]] = {}
        self._initialized = False

    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize tool service.

        Args:
            config: Tool service configuration
        """
        self._config = config or {}

        # Load builtin tools
        await self._load_builtin_tools()

        # Load MCP tools if configured
        if self._config.get("enable_mcp", False):
            await self._load_mcp_tools()

        # Load ADK native tools if configured
        if self._config.get("enable_adk_native", False):
            await self._load_adk_native_tools()

        self._initialized = True

    async def register_tool(self, tool: Tool):
        """
        Register a tool with the service.

        Args:
            tool: Tool instance to register
        """
        # Bootstrap ensures all tools are pre-initialized during registration
        # No need for runtime initialization check

        # Register tool
        self._tools[tool.full_name] = tool

        # Update namespace registry
        if tool.namespace:
            if tool.namespace not in self._tool_namespaces:
                self._tool_namespaces[tool.namespace] = []
            self._tool_namespaces[tool.namespace].append(tool.name)

    async def execute_tool(self, tool_request: ToolRequest) -> ToolResult:
        """
        Execute a tool with the given request.

        Args:
            tool_request: Request containing tool name and parameters

        Returns:
            ToolResult: Result of tool execution
        """
        # Determine full tool name
        if tool_request.tool_namespace:
            full_name = f"{tool_request.tool_namespace}.{tool_request.tool_name}"
        else:
            full_name = tool_request.tool_name

        # Find tool
        tool = self._tools.get(full_name)
        if not tool:
            return ToolResult(
                tool_name=tool_request.tool_name,
                tool_namespace=tool_request.tool_namespace,
                status=ToolStatus.NOT_FOUND,
                error_message=f"Tool {full_name} not found",
            )

        try:
            # Log tool execution chain
            from ..common.unified_logging import create_execution_context
            exec_context = create_execution_context(f"tool_{full_name}")
            exec_context.log_execution_chain({
                "tool_request": {
                    "tool_name": tool_request.tool_name,
                    "tool_namespace": tool_request.tool_namespace,
                    "parameters_count": len(tool_request.parameters)
                }
            })
            
            # Validate parameters
            if not await tool.validate_parameters(tool_request.parameters):
                return ToolResult(
                    tool_name=tool_request.tool_name,
                    tool_namespace=tool_request.tool_namespace,
                    status=ToolStatus.ERROR,
                    error_message="Invalid tool parameters",
                )

            # Execute tool
            result = await tool.execute(tool_request)
            
            # Log tool execution result
            exec_context.log_execution_chain({
                "tool_result": {
                    "tool_name": result.tool_name,
                    "status": result.status.value if result.status else "unknown",
                    "execution_time": result.execution_time,
                    "has_error": bool(result.error_message)
                }
            })
            
            return result

        except Exception as e:
            return ToolResult(
                tool_name=tool_request.tool_name,
                tool_namespace=tool_request.tool_namespace,
                status=ToolStatus.ERROR,
                error_message=f"Tool execution failed: {str(e)}",
            )

    async def list_tools(self, namespace: Optional[str] = None) -> List[str]:
        """
        List available tools.

        Args:
            namespace: Optional namespace filter

        Returns:
            List[str]: List of tool names
        """
        if namespace:
            return self._tool_namespaces.get(namespace, [])
        else:
            return list(self._tools.keys())

    async def get_tool_schema(
        self, tool_name: str, namespace: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get schema for a specific tool.

        Args:
            tool_name: Name of the tool
            namespace: Optional tool namespace

        Returns:
            Optional[Dict[str, Any]]: Tool schema or None if not found
        """
        full_name = f"{namespace}.{tool_name}" if namespace else tool_name
        tool = self._tools.get(full_name)

        if tool:
            return await tool.get_schema()
        return None

    async def get_tool_capabilities(
        self, tool_name: str, namespace: Optional[str] = None
    ) -> List[str]:
        """
        Get capabilities for a specific tool.

        Args:
            tool_name: Name of the tool
            namespace: Optional tool namespace

        Returns:
            List[str]: List of tool capabilities
        """
        full_name = f"{namespace}.{tool_name}" if namespace else tool_name
        tool = self._tools.get(full_name)

        if tool:
            return await tool.get_capabilities()
        return []

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of all tools.

        Returns:
            Dict[str, Any]: Health status information
        """
        tool_health = {}
        for name, tool in self._tools.items():
            tool_health[name] = await tool.health_check()

        return {
            "service_status": "healthy",  # Bootstrap ensures service is always initialized
            "total_tools": len(self._tools),
            "namespaces": list(self._tool_namespaces.keys()),
            "tools": tool_health,
        }

    async def shutdown(self):
        """Shutdown tool service and cleanup all tools."""
        for tool in self._tools.values():
            await tool.cleanup()

        self._tools.clear()
        self._tool_namespaces.clear()
        self._initialized = False

    async def _load_builtin_tools(self):
        """Load builtin system tools."""
        try:
            from .builtin.tools import EchoTool, TimestampTool
            from .builtin.chat_log_tool import ChatLogTool

            # Register builtin tools
            await self.register_tool(EchoTool())
            await self.register_tool(TimestampTool())
            await self.register_tool(ChatLogTool())

        except ImportError:
            # Builtin tools not available
            pass

    async def _load_mcp_tools(self):
        """Load MCP (Model Context Protocol) tools."""
        try:
            from .mcp import MCPClient, MCPServerConfig, MCPTool
            
            # Get MCP server configurations
            mcp_servers = self._config.get("mcp_servers", [])
            
            if not mcp_servers:
                print("⚠️ No MCP servers configured")
                return
                
            print(f"🔌 Loading MCP tools from {len(mcp_servers)} servers...")
            
            for server_config in mcp_servers:
                try:
                    # Create server configuration
                    config = MCPServerConfig(
                        name=server_config["name"],
                        endpoint=server_config["endpoint"],
                        headers=server_config.get("headers", {}),
                        timeout=server_config.get("timeout", 30)
                    )
                    
                    # Create and connect MCP client
                    client = MCPClient(config)
                    await client.connect()
                    
                    # Discover tools from this server
                    universal_tools = await client.discover_tools()
                    print(f"📋 Found {len(universal_tools)} tools from {config.name}")
                    
                    # Convert UniversalTools to MCPTools and register
                    for universal_tool in universal_tools:
                        # Create MCPTool wrapper
                        mcp_tool = MCPTool(
                            mcp_client=client,
                            tool_name=universal_tool.name.split('.')[-1],  # Remove namespace prefix
                            tool_description=universal_tool.description,
                            tool_schema=universal_tool.parameters_schema,
                            namespace=config.name
                        )
                        
                        # Initialize the tool
                        await mcp_tool.initialize()
                        
                        # Register with the service
                        await self.register_tool(mcp_tool)
                        
                    print(f"✅ Successfully loaded {len(universal_tools)} tools from {config.name}")
                    
                except Exception as e:
                    print(f"❌ Failed to load tools from {server_config.get('name', 'unknown')}: {e}")
                    continue
                    
        except ImportError as e:
            print(f"⚠️ MCP not available: {e}")
            pass

    async def _load_adk_native_tools(self):
        """Load ADK native tools."""
        try:
            # TODO: Implement ADK native tool loading
            # from .adk_native.wrappers import load_adk_tools
            # adk_tools = await load_adk_tools()
            # for tool in adk_tools:
            #     await self.register_tool(tool)
            pass
        except ImportError:
            # ADK native tools not available
            pass
