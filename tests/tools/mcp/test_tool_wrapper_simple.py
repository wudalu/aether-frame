# -*- coding: utf-8 -*-
"""Simplified test suite for MCPTool wrapper implementation."""

import pytest
from unittest.mock import AsyncMock, patch

from aether_frame.tools.mcp.tool_wrapper import MCPTool
from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig
from aether_frame.contracts import ToolRequest, ToolResult
from aether_frame.contracts.responses import ToolStatus
from aether_frame.contracts.streaming import TaskStreamChunk
from aether_frame.contracts.enums import TaskChunkType


class TestMCPToolCore:
    """Core tests for MCPTool wrapper."""
    
    def test_mcp_tool_initialization(self) -> None:
        """Test MCPTool initialization."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="search",
            tool_description="Search tool",
            tool_schema={"type": "object"},
            namespace="test_server"
        )
        
        # Basic properties
        assert tool.full_name == "test_server.search"
        assert tool.name == "search"
        assert tool.namespace == "test_server"
        assert tool.supports_streaming is True
    
    @pytest.mark.asyncio
    async def test_successful_execute(self) -> None:
        """Test successful tool execution."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        # Mock client methods
        mock_client.call_tool = AsyncMock(return_value="Test result")
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="test_tool",
            tool_description="Test tool",
            tool_schema={},
            namespace="test_server"
        )
        
        # Use patch to mock is_connected
        with patch.object(mock_client, 'is_connected', True):
            tool_request = ToolRequest(
                tool_name="test_server.test_tool",
                parameters={"param": "value"}
            )
            
            result = await tool.execute(tool_request)
            
            # Verify success
            assert isinstance(result, ToolResult)
            assert result.status == ToolStatus.SUCCESS
            assert result.result_data == "Test result"
            assert result.tool_name == "test_server.test_tool"
            mock_client.call_tool.assert_awaited_once()
            call_args = mock_client.call_tool.call_args
            assert call_args.args == ("test_tool", {"param": "value"})
            assert call_args.kwargs.get("extra_headers") is None
    
    @pytest.mark.asyncio
    async def test_execute_connection_error(self) -> None:
        """Test execution when not connected."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="test_tool",
            tool_description="Test tool",
            tool_schema={},
            namespace="test_server"
        )
        
        # Mock disconnected client
        with patch.object(mock_client, 'is_connected', False):
            tool_request = ToolRequest(
                tool_name="test_server.test_tool",
                parameters={}
            )
            
            result = await tool.execute(tool_request)
            
            # Verify error
            assert result.status == ToolStatus.ERROR
            assert "not connected" in result.error_message
    
    @pytest.mark.asyncio
    async def test_streaming_execute(self) -> None:
        """Test streaming execution."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        # Mock streaming response
        async def mock_stream():
            yield {"type": "data", "content": "chunk1", "is_final": False}
            yield {"type": "complete", "content": "done", "is_final": True}
        
        mock_client.call_tool_stream = AsyncMock(return_value=mock_stream())
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="test_tool",
            tool_description="Test tool",
            tool_schema={},
            namespace="test_server"
        )
        
        with patch.object(mock_client, 'is_connected', True):
            tool_request = ToolRequest(
                tool_name="test_server.test_tool",
                parameters={}
            )
            
            chunks = []
            async for chunk in tool.execute_stream(tool_request):
                chunks.append(chunk)
            
            # Verify streaming
            assert len(chunks) == 2
            assert isinstance(chunks[0], TaskStreamChunk)
            assert chunks[0].chunk_type == TaskChunkType.RESPONSE
            assert chunks[0].content == "chunk1"
            assert chunks[1].chunk_type == TaskChunkType.COMPLETE
            assert chunks[1].is_final is True
            mock_client.call_tool_stream.assert_awaited_once()
            stream_call = mock_client.call_tool_stream.call_args
            assert stream_call.args == ("test_tool", {})
            assert stream_call.kwargs.get("extra_headers") is None
    
    @pytest.mark.asyncio
    async def test_tool_schema(self) -> None:
        """Test tool schema retrieval."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        tool_schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="search",
            tool_description="Search tool",
            tool_schema=tool_schema,
            namespace="test_server"
        )
        
        schema = await tool.get_schema()
        
        assert schema["name"] == "test_server.search"
        assert schema["description"] == "Search tool"
        assert schema["parameters"] == tool_schema
        assert schema["supports_streaming"] is True
    
    @pytest.mark.asyncio
    async def test_parameter_validation(self) -> None:
        """Test parameter validation."""
        config = MCPServerConfig(name="test_server", endpoint="http://localhost:8000/mcp")
        mock_client = MCPClient(config)
        
        tool_schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
        
        tool = MCPTool(
            mcp_client=mock_client,
            tool_name="search",
            tool_description="Search tool",
            tool_schema=tool_schema,
            namespace="test_server"
        )
        
        # Valid parameters
        assert await tool.validate_parameters({"query": "test"}) is True
        
        # Missing required parameter
        assert await tool.validate_parameters({}) is False
        
        # Wrong type
        assert await tool.validate_parameters({"query": 123}) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
