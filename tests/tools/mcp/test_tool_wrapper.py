# -*- coding: utf-8 -*-
"""Test suite for MCPTool wrapper implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Any, Dict

from aether_frame.tools.mcp.tool_wrapper import MCPTool
from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig
from aether_frame.contracts import ToolRequest, ToolResult
from aether_frame.contracts.responses import ToolStatus
from aether_frame.contracts.streaming import TaskStreamChunk
from aether_frame.contracts.enums import TaskChunkType


class TestMCPToolWrapper:
    """Test MCPTool wrapper implementation."""
    
    def test_mcp_tool_initialization(self) -> None:
        """Test MCPTool initialization with proper attributes."""
        # Create mock MCP client
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        # Create MCPTool
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="search",
            tool_description="Search for information",
            tool_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            namespace="test_server"
        )
        
        # Verify initialization
        assert tool.original_tool_name == "search"
        assert tool.full_name == "test_server.search"
        assert tool.name == "search"  # Base class name
        assert tool.namespace == "test_server"
        assert tool.tool_description == "Search for information"
        assert tool.supports_streaming is True
        assert tool.tool_schema["type"] == "object"
    
    @pytest.mark.asyncio
    async def test_successful_execute(self) -> None:
        """Test successful synchronous tool execution."""
        # Setup
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        # Mock client methods
        mock_client.call_tool = AsyncMock(return_value="Search results: Found 3 items")
        
        with patch.object(mock_client, 'is_connected', True):
            tool = MCPTool(
                mcp_client=mock_client,
                tool_name="search", 
                tool_description="Search tool",
                tool_schema={},
                namespace="test_server"
            )
            
            # Create tool request
            tool_request = ToolRequest(
                tool_name="test_server.search",
                parameters={"query": "test search"}
            )
            
            # Execute tool
            result = await tool.execute(tool_request)
            
            # Verify result
            assert isinstance(result, ToolResult)
            assert result.status == ToolStatus.SUCCESS
            assert result.result_data == "Search results: Found 3 items"
            assert result.tool_name == "test_server.search"
            assert result.tool_namespace == "test_server"
            assert result.error_message is None
            assert "mcp_server" in result.metadata
            assert result.metadata["mcp_server"] == "test_server"
            
            # Verify client was called correctly
            mock_client.call_tool.assert_called_once_with("search", {"query": "test search"})
    
    @pytest.mark.asyncio
    async def test_execute_connection_error(self) -> None:
        """Test tool execution when client is not connected."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        # Mock disconnected client
        mock_client.is_connected = False
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="search",
            tool_description="Search tool", 
            tool_schema={},
            namespace="test_server"
        )
        
        tool_request = ToolRequest(
            tool_name="test_server.search",
            parameters={"query": "test"},
            session_id="session_123"
        )
        
        # Execute tool
        result = await tool.execute(tool_request)
        
        # Verify error result
        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.ERROR
        assert "not connected" in result.error_message
        assert result.result_data is None
        assert result.metadata["error_type"] == "MCPConnectionError"
    
    @pytest.mark.asyncio
    async def test_execute_tool_error(self) -> None:
        """Test tool execution when MCP tool call fails."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        # Mock client with error
        mock_client.is_connected = True
        mock_client.call_tool = AsyncMock(side_effect=MCPToolError("Tool execution failed"))
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="search",
            tool_description="Search tool",
            tool_schema={}, 
            namespace="test_server"
        )
        
        tool_request = ToolRequest(
            tool_name="test_server.search",
            parameters={"query": "test"},
            session_id="session_123"
        )
        
        # Execute tool
        result = await tool.execute(tool_request)
        
        # Verify error result
        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.ERROR
        assert result.error_message == "Tool execution failed"
        assert result.metadata["error_type"] == "MCPToolError"
    
    @pytest.mark.asyncio
    async def test_successful_execute_stream(self) -> None:
        """Test successful streaming tool execution."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        # Mock streaming response
        async def mock_stream():
            yield {"type": "data", "content": "First chunk", "is_final": False, "chunk_index": 0}
            yield {"type": "data", "content": "Second chunk", "is_final": False, "chunk_index": 1}
            yield {"type": "complete", "content": "Done", "is_final": True, "chunk_index": 2}
        
        mock_client.is_connected = True
        mock_client.call_tool_stream = AsyncMock(return_value=mock_stream())
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="search",
            tool_description="Search tool",
            tool_schema={},
            namespace="test_server"
        )
        
        tool_request = ToolRequest(
            tool_name="test_server.search",
            parameters={"query": "streaming test"},
            session_id="session_123"
        )
        
        # Execute streaming
        chunks = []
        async for chunk in tool.execute_stream(tool_request):
            chunks.append(chunk)
        
        # Verify chunks
        assert len(chunks) == 3
        
        # Check first chunk
        assert isinstance(chunks[0], TaskStreamChunk)
        assert chunks[0].metadata["tool_name"] == "test_server.search"
        assert chunks[0].chunk_type == TaskChunkType.RESPONSE
        assert chunks[0].content == "First chunk"
        assert chunks[0].is_final is False
        assert chunks[0].sequence_id == 0
        assert chunks[0].metadata["mcp_server"] == "test_server"
        
        # Check last chunk
        assert chunks[2].chunk_type == TaskChunkType.COMPLETE
        assert chunks[2].is_final is True
        
        # Verify client was called correctly
        mock_client.call_tool_stream.assert_called_once_with("search", {"query": "streaming test"})
    
    @pytest.mark.asyncio
    async def test_execute_stream_connection_error(self) -> None:
        """Test streaming execution when client is not connected."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        # Mock disconnected client
        mock_client.is_connected = False
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="search",
            tool_description="Search tool",
            tool_schema={},
            namespace="test_server"
        )
        
        tool_request = ToolRequest(
            tool_name="test_server.search",
            parameters={"query": "test"},
            session_id="session_123"
        )
        
        # Execute streaming
        chunks = []
        async for chunk in tool.execute_stream(tool_request):
            chunks.append(chunk)
        
        # Should get one error chunk
        assert len(chunks) == 1
        assert chunks[0].chunk_type == TaskChunkType.ERROR
        assert "not connected" in chunks[0].content
        assert chunks[0].is_final is True
        assert chunks[0].metadata["error_type"] == "MCPConnectionError"
    
    @pytest.mark.asyncio
    async def test_execute_stream_tool_error(self) -> None:
        """Test streaming execution when MCP tool stream fails."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        # Mock client with streaming error
        mock_client.is_connected = True
        mock_client.call_tool_stream = AsyncMock(side_effect=MCPToolError("Streaming failed"))
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="search", 
            tool_description="Search tool",
            tool_schema={},
            namespace="test_server"
        )
        
        tool_request = ToolRequest(
            tool_name="test_server.search",
            parameters={"query": "test"},
            session_id="session_123"
        )
        
        # Execute streaming
        chunks = []
        async for chunk in tool.execute_stream(tool_request):
            chunks.append(chunk)
        
        # Should get one error chunk
        assert len(chunks) == 1
        assert chunks[0].chunk_type == TaskChunkType.ERROR
        assert chunks[0].content == "Streaming failed"
        assert chunks[0].is_final is True
        assert chunks[0].metadata["error_type"] == "MCPToolError"
    
    def test_tool_properties(self) -> None:
        """Test MCPTool property access."""
        config = MCPServerConfig(name="my_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        tool_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="advanced_search",
            tool_description="Advanced search functionality",
            tool_schema=tool_schema,
            namespace="my_server"
        )
        
        # Test all properties
        assert tool.full_name == "my_server.advanced_search"
        assert tool.name == "advanced_search"  # Base class name
        assert tool.namespace == "my_server"
        assert tool.tool_description == "Advanced search functionality"
        assert tool.tool_schema == tool_schema
        assert tool.supports_streaming is True
        
        # Test string representations
        assert "advanced_search" in str(tool)
        assert "my_server" in repr(tool)
        assert "localhost:8000" in repr(tool)
    
    @pytest.mark.asyncio
    async def test_tool_request_without_parameters(self) -> None:
        """Test tool execution with no parameters."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        # Mock client
        mock_client.is_connected = True
        mock_client.call_tool = AsyncMock(return_value="No params result")
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="ping",
            tool_description="Ping tool",
            tool_schema={},
            namespace="test_server"
        )
        
        # Tool request without parameters
        tool_request = ToolRequest(
            tool_name="test_server.ping",
            parameters=None,  # No parameters
            session_id="session_123"
        )
        
        result = await tool.execute(tool_request)
        
        # Verify
        assert result.status == ToolStatus.SUCCESS
        assert result.result_data == "No params result"
        
        # Client should have been called with empty dict
        mock_client.call_tool.assert_called_once_with("ping", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])