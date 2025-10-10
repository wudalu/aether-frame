# -*- coding: utf-8 -*-
"""MCP tool wrapper implementing the Tool interface."""

from typing import Any, AsyncIterator, Dict, List, Optional
from datetime import datetime

from aether_frame.tools.base.tool import Tool
from aether_frame.contracts import ToolRequest, ToolResult
from aether_frame.contracts.responses import ToolStatus
from aether_frame.contracts.enums import TaskChunkType
from aether_frame.contracts.streaming import TaskStreamChunk
from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError


class MCPTool(Tool):
    """MCP tool wrapper implementing the Tool interface.
    
    This class wraps an MCP tool and provides a unified interface
    for tool execution within the Aether Frame system.
    
    Attributes:
        mcp_client: The MCP client for communication
        original_tool_name: Original tool name (without namespace)
        tool_description: Tool description
        tool_schema: Tool parameter schema
    """
    
    def __init__(
        self,
        mcp_client: MCPClient,
        tool_name: str,
        tool_description: str,
        tool_schema: Dict[str, Any],
        namespace: str
    ):
        """Initialize MCP tool wrapper.
        
        Args:
            mcp_client: Connected MCP client instance
            tool_name: Original tool name (without namespace prefix)
            tool_description: Tool description
            tool_schema: Tool parameter schema
            namespace: MCP server namespace
        """
        # Initialize base Tool class
        super().__init__(name=tool_name, namespace=namespace)
        
        self.mcp_client = mcp_client
        self.original_tool_name = tool_name
        self.tool_description = tool_description
        self.tool_schema = tool_schema
        self._initialized = True  # MCP tools are initialized when created
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the MCP tool.
        
        MCP tools are initialized through the MCP client connection.
        """
        # Check if MCP client is connected
        if not self.mcp_client.is_connected:
            raise MCPConnectionError("MCP client is not connected")
        
        self._initialized = True
    
    async def execute(self, tool_request: ToolRequest) -> ToolResult:
        """Execute tool synchronously.
        
        Args:
            tool_request: Tool execution request
            
        Returns:
            Tool execution result
        """
        try:
            # Ensure client is connected
            if not self.mcp_client.is_connected:
                raise MCPConnectionError("MCP client is not connected")
            
            # Extract parameters from tool request
            parameters = tool_request.parameters or {}
            
            # Call the MCP tool using the original name (without namespace)
            result = await self.mcp_client.call_tool(self.original_tool_name, parameters)
            
            # Create tool result
            return ToolResult(
                tool_name=self.full_name,
                status=ToolStatus.SUCCESS,
                tool_namespace=self.namespace,
                result_data=result,
                created_at=datetime.now(),
                metadata={
                    "mcp_server": self.namespace,
                    "original_tool_name": self.original_tool_name,
                    "mcp_client_endpoint": self.mcp_client.config.endpoint
                }
            )
            
        except (MCPConnectionError, MCPToolError) as e:
            # MCP specific errors
            return ToolResult(
                tool_name=self.full_name,
                status=ToolStatus.ERROR,
                tool_namespace=self.namespace,
                result_data=None,
                error_message=str(e),
                created_at=datetime.now(),
                metadata={
                    "error_type": type(e).__name__,
                    "mcp_server": self.namespace,
                    "original_tool_name": self.original_tool_name
                }
            )
            
        except Exception as e:
            # Generic errors
            return ToolResult(
                tool_name=self.full_name,
                status=ToolStatus.ERROR,
                tool_namespace=self.namespace,
                result_data=None,
                error_message=f"Unexpected error: {e}",
                created_at=datetime.now(),
                metadata={
                    "error_type": "UnexpectedError",
                    "mcp_server": self.namespace,
                    "original_tool_name": self.original_tool_name
                }
            )
    
    async def execute_stream(self, tool_request: ToolRequest) -> AsyncIterator[TaskStreamChunk]:
        """Execute tool with streaming response.
        
        Uses the enhanced streaming implementation from MCPClient.
        
        Args:
            tool_request: Tool execution request
            
        Yields:
            Streaming response chunks from tool execution
        """
        try:
            # Ensure client is connected
            if not self.mcp_client.is_connected:
                raise MCPConnectionError("MCP client is not connected")
            
            # Extract parameters from tool request
            parameters = tool_request.parameters or {}
            
            sequence_id = 0
            
            # Stream from MCP client with enhanced streaming
            async for chunk in self.mcp_client.call_tool_stream(self.original_tool_name, parameters):
                
                # Determine chunk type from MCP response
                chunk_type_mapping = {
                    "data": TaskChunkType.RESPONSE,
                    "result": TaskChunkType.RESPONSE, 
                    "complete": TaskChunkType.COMPLETE,
                    "error": TaskChunkType.ERROR
                }
                
                mcp_type = chunk.get("type", "data")
                chunk_type = chunk_type_mapping.get(mcp_type, TaskChunkType.RESPONSE)
                
                # Convert MCP chunk to TaskStreamChunk
                stream_chunk = TaskStreamChunk(
                    task_id=f"tool_execution_{self.full_name}",
                    chunk_type=chunk_type,
                    sequence_id=sequence_id,
                    content=chunk.get("content") or chunk.get("data", ""),
                    is_final=chunk.get("is_final", False),
                    metadata={
                        "tool_name": self.full_name,
                        "mcp_server": self.namespace,
                        "original_tool_name": self.original_tool_name,
                        "mcp_timestamp": chunk.get("timestamp"),
                        "mcp_chunk_type": mcp_type
                    }
                )
                
                yield stream_chunk
                sequence_id += 1
                
        except (MCPConnectionError, MCPToolError) as e:
            # Yield error chunk
            yield TaskStreamChunk(
                task_id=f"tool_execution_{self.full_name}",
                chunk_type=TaskChunkType.ERROR,
                sequence_id=0,
                content=str(e),
                is_final=True,
                metadata={
                    "tool_name": self.full_name,
                    "error_type": type(e).__name__,
                    "mcp_server": self.namespace,
                    "original_tool_name": self.original_tool_name
                }
            )
            
        except Exception as e:
            # Yield generic error chunk
            yield TaskStreamChunk(
                task_id=f"tool_execution_{self.full_name}",
                chunk_type=TaskChunkType.ERROR,
                sequence_id=0,
                content=f"Unexpected error: {e}",
                is_final=True,
                metadata={
                    "tool_name": self.full_name,
                    "error_type": "UnexpectedError",
                    "mcp_server": self.namespace,
                    "original_tool_name": self.original_tool_name
                }
            )
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get tool schema definition.
        
        Returns:
            Tool schema including parameters and description
        """
        return {
            "name": self.full_name,
            "description": self.tool_description,
            "parameters": self.tool_schema,
            "namespace": self.namespace,
            "supports_streaming": True,
            "metadata": {
                "mcp_server": self.namespace,
                "original_tool_name": self.original_tool_name,
                "mcp_endpoint": self.mcp_client.config.endpoint
            }
        }
    
    async def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate tool parameters against schema.
        
        Args:
            parameters: Parameters to validate
            
        Returns:
            True if parameters are valid
        """
        # Basic validation - check if schema has required fields
        if not self.tool_schema:
            return True  # No schema means all parameters are valid
        
        schema_properties = self.tool_schema.get("properties", {})
        required_fields = self.tool_schema.get("required", [])
        
        # Check if all required fields are present
        for field in required_fields:
            if field not in parameters:
                return False
        
        # Basic type checking for known properties
        for param_name, param_value in parameters.items():
            if param_name in schema_properties:
                expected_type = schema_properties[param_name].get("type")
                if expected_type == "string" and not isinstance(param_value, str):
                    return False
                elif expected_type == "number" and not isinstance(param_value, (int, float)):
                    return False
                elif expected_type == "boolean" and not isinstance(param_value, bool):
                    return False
        
        return True
    
    async def cleanup(self):
        """Cleanup tool resources.
        
        MCP tools cleanup is handled by the MCP client.
        """
        # MCP tool cleanup is managed by the client
        self._initialized = False
    
    async def get_capabilities(self) -> List[str]:
        """Get tool capabilities.
        
        Returns:
            List of capability names
        """
        capabilities = ["execute", "validate_parameters"]
        
        # Add streaming capability
        capabilities.append("execute_stream")
        
        return capabilities
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform tool health check.
        
        Returns:
            Health status information
        """
        base_health = await super().health_check()
        
        # Add MCP-specific health information
        mcp_health = {
            **base_health,
            "mcp_client_connected": self.mcp_client.is_connected,
            "mcp_server": self.namespace,
            "mcp_endpoint": self.mcp_client.config.endpoint,
            "original_tool_name": self.original_tool_name
        }
        
        # Update overall status based on MCP client
        if not self.mcp_client.is_connected:
            mcp_health["status"] = "unhealthy"
            mcp_health["issues"] = ["MCP client not connected"]
        
        return mcp_health
    
    @property
    def supports_streaming(self) -> bool:
        """Check if tool supports streaming execution.
        
        MCP tools support streaming through our enhanced client implementation.
        """
        return True
    
    def __str__(self) -> str:
        """String representation of the MCP tool."""
        return f"MCPTool({self.full_name})"
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"MCPTool("
            f"name='{self.full_name}', "
            f"namespace='{self.namespace}', "
            f"endpoint='{self.mcp_client.config.endpoint}'"
            f")"
        )