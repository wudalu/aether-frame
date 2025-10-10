# -*- coding: utf-8 -*-
"""Simplified test suite for MCPClient Phase 1.2 validation."""

import pytest
from unittest.mock import AsyncMock, patch
from typing import Any, Dict, List

from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig
from aether_frame.contracts.contexts import UniversalTool


class TestMCPClientBasicValidation:
    """Core Phase 1.2 validation tests for MCPClient."""
    
    def test_client_initialization(self) -> None:
        """✅ Phase 1.2: Client basic initialization."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        
        client = MCPClient(config)
        
        assert client.config == config
        assert client._session is None
        assert not client.is_connected
    
    @pytest.mark.asyncio
    async def test_connection_with_mocking(self) -> None:
        """✅ Phase 1.2: Connection establishment to Mock MCP server."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock all the MCP SDK components
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=(mock_session, mock_session, None))
        mock_stream_context.__aexit__ = AsyncMock()
        
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock()
        
        with patch('aether_frame.tools.mcp.client.streamablehttp_client', return_value=mock_stream_context), \
             patch('aether_frame.tools.mcp.client.ClientSession', return_value=mock_session_context):
            
            # Test connection
            await client.connect()
            assert client.is_connected
            assert client._session is not None
            
            # Test disconnection
            await client.disconnect()
            assert not client.is_connected
    
    @pytest.mark.asyncio
    async def test_tool_discovery(self) -> None:
        """✅ Phase 1.2: Tool discovery functionality."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock session with tools response
        mock_session = AsyncMock()
        
        # Mock the MCP SDK tools response format
        mock_tools_result = AsyncMock()
        mock_tool1 = AsyncMock()
        mock_tool1.name = "search"
        mock_tool1.description = "Search for information"
        mock_tool1.inputSchema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
        
        mock_tool2 = AsyncMock()
        mock_tool2.name = "calculate"
        mock_tool2.description = "Perform calculations"
        mock_tool2.inputSchema = {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"]
        }
        
        mock_tools_result.tools = [mock_tool1, mock_tool2]
        mock_session.list_tools = AsyncMock(return_value=mock_tools_result)
        
        # Set session and connected state
        client._session = mock_session
        client._connected = True
        
        # Test tool discovery
        tools = await client.discover_tools()
        
        assert len(tools) == 2
        assert tools[0].name == "test_server.search"
        assert tools[0].description == "Search for information"
        assert tools[1].name == "test_server.calculate"
        assert tools[1].description == "Perform calculations"
    
    @pytest.mark.asyncio
    async def test_synchronous_tool_execution(self) -> None:
        """✅ Phase 1.2: Synchronous tool execution."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock session with call_tool response
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_content = AsyncMock()
        mock_content.text = "Search results: Found 5 items"
        mock_result.content = [mock_content]
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        
        # Set session and connected state
        client._session = mock_session
        client._connected = True
        
        # Test tool execution
        result = await client.call_tool("search", {"query": "test"})
        
        assert result == "Search results: Found 5 items"
        mock_session.call_tool.assert_called_once_with("search", {"query": "test"})
    
    @pytest.mark.asyncio
    async def test_streaming_tool_execution(self) -> None:
        """✅ Phase 1.2: Streaming tool execution."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock session for streaming (uses synchronous call internally)
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_content = AsyncMock()
        mock_content.text = "Streaming result data"
        mock_result.content = [mock_content]
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        
        # Set session and connected state
        client._session = mock_session
        client._connected = True
        
        # Test streaming execution
        chunks = []
        async for chunk in client.call_tool_stream("search", {"query": "test"}):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0]["type"] == "result"
        assert chunks[0]["content"] == "Streaming result data"
        assert chunks[0]["is_final"] is True
        assert chunks[0]["tool_name"] == "search"
    
    @pytest.mark.asyncio
    async def test_error_handling(self) -> None:
        """✅ Phase 1.2: Error handling (network, timeout, server errors)."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Test connection error
        with patch('aether_frame.tools.mcp.client.streamablehttp_client', side_effect=Exception("Connection failed")):
            with pytest.raises(MCPConnectionError, match="Failed to connect to MCP server"):
                await client.connect()
        
        # Test tool discovery without connection
        with pytest.raises(MCPConnectionError, match="Not connected to MCP server"):
            await client.discover_tools()
        
        # Test tool execution without connection
        with pytest.raises(MCPConnectionError, match="Not connected to MCP server"):
            await client.call_tool("test", {})
        
        # Test tool discovery error
        mock_session = AsyncMock()
        mock_session.list_tools = AsyncMock(side_effect=Exception("Server error"))
        client._session = mock_session
        client._connected = True
        
        with pytest.raises(MCPToolError, match="Tool discovery failed"):
            await client.discover_tools()
        
        # Test tool execution error
        mock_session.call_tool = AsyncMock(side_effect=Exception("Execution failed"))
        
        with pytest.raises(MCPToolError, match="Tool execution failed"):
            await client.call_tool("test", {})


class TestMCPClientConfiguration:
    """Test configuration options and edge cases."""
    
    def test_timeout_configuration(self) -> None:
        """✅ Test custom timeout configuration."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            timeout=60
        )
        client = MCPClient(config)
        
        assert client.config.timeout == 60
    
    def test_headers_configuration(self) -> None:
        """✅ Test custom headers configuration."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            headers={"Authorization": "Bearer token123"}
        )
        client = MCPClient(config)
        
        assert client.config.headers["Authorization"] == "Bearer token123"