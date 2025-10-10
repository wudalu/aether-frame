# -*- coding: utf-8 -*-
"""Test suite for MCPClient implementation."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict, List
import aiohttp

from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig
from aether_frame.contracts.contexts import UniversalTool


def create_mock_context_manager(mock_response):
    """Helper to create properly configured async context manager mock."""
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__.return_value = mock_response
    mock_context_manager.__aexit__.return_value = None
    return mock_context_manager


class TestMCPClientInitialization:
    """Test MCPClient initialization and connection management."""
    
    def test_client_initialization(self) -> None:
        """Test basic client initialization."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        
        client = MCPClient(config)
        
        assert client.config == config
        assert client.session is None
        assert not client.is_connected
    
    @pytest.mark.asyncio
    async def test_context_manager_usage(self) -> None:
        """Test client usage as async context manager."""
        config = MCPServerConfig(
            name="test_server", 
            endpoint="http://localhost:8000/mcp"
        )
        
        # Mock the streaming client and session
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
            async with MCPClient(config) as client:
                assert client.is_connected
                assert client._session is not None
                assert client.session is not None
            
            assert not client.is_connected
            assert client.session is None


class TestMCPClientConnection:
    """Test connection establishment and health checks."""
    
    @pytest.mark.asyncio
    async def test_successful_connection(self) -> None:
        """Test successful connection to MCP server."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            timeout=30
        )
        client = MCPClient(config)
        
        # Mock the streaming client and session
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
            await client.connect()
            
            assert client.is_connected
            assert client._session is not None
            
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_connection_failure(self) -> None:
        """Test connection failure handling."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        with patch('aether_frame.tools.mcp.client.Session') as mock_session_class, \
             patch('aether_frame.tools.mcp.client.ClientTransport'):
            mock_session_class.side_effect = Exception("Connection failed")
            
            with pytest.raises(MCPConnectionError, match="Failed to connect to MCP server"):
                await client.connect()
            
            assert not client.is_connected
            assert client.session is None
    
    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test successful health check."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock successful health check
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value='{"status": "healthy"}')
        
        with patch('aiohttp.ClientSession.get', return_value=create_mock_context_manager(mock_response)):
            client._session = mock_session
            await client._health_check()  # Should not raise
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self) -> None:
        """Test health check failure."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock failed health check
        mock_session = AsyncMock()
        
        with patch('aiohttp.ClientSession.get', side_effect=aiohttp.ClientError("Health check failed")):
            client._session = mock_session
            with pytest.raises(MCPConnectionError, match="Health check failed"):
                await client._health_check()
    
    @pytest.mark.asyncio
    async def test_health_check_no_session(self) -> None:
        """Test health check when no session exists."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        with pytest.raises(MCPConnectionError, match="No active session"):
            await client._health_check()
    
    @pytest.mark.asyncio
    async def test_double_connection(self) -> None:
        """Test that connecting twice doesn't create issues."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        
        with patch('aether_frame.tools.mcp.client.Session', return_value=mock_session), \
             patch('aether_frame.tools.mcp.client.ClientTransport'), \
             patch.object(client, '_health_check', new_callable=AsyncMock):
            
            await client.connect()
            first_session = client._session
            
            await client.connect()  # Second connection
            assert client._session == first_session  # Same session
            
            await client.disconnect()


class TestMCPClientToolDiscovery:
    """Test tool discovery functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_tool_discovery(self) -> None:
        """Test successful tool discovery."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock tools response
        mock_session = AsyncMock()
        mock_tools_response = {
            "tools": [
                {
                    "name": "search",
                    "description": "Search for information",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "calculate",
                    "description": "Perform calculations",
                    "inputSchema": {
                        "type": "object", 
                        "properties": {
                            "expression": {"type": "string", "description": "Math expression"}
                        },
                        "required": ["expression"]
                    }
                }
            ]
        }
        
        mock_session.list_tools = AsyncMock(return_value=mock_tools_response)
        client._session = mock_session
        
        tools = await client.discover_tools()
        
        assert len(tools) == 2
        assert tools[0].name == "search"
        assert tools[0].description == "Search for information"
        assert tools[1].name == "calculate"
        assert tools[1].description == "Perform calculations"
        
        mock_session.list_tools.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_tool_discovery_server_error(self) -> None:
        """Test tool discovery when server returns error."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        mock_session = AsyncMock()
        mock_session.list_tools = AsyncMock(side_effect=Exception("Server error"))
        client._session = mock_session
        
        with pytest.raises(MCPToolError, match="Failed to discover tools"):
            await client.discover_tools()
    
    @pytest.mark.asyncio
    async def test_tool_discovery_invalid_json(self) -> None:
        """Test tool discovery with malformed response."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        mock_session = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value={"invalid": "response"})
        client._session = mock_session
        
        with pytest.raises(MCPToolError, match="Invalid tools response format"):
            await client.discover_tools()


class TestMCPClientToolExecution:
    """Test tool execution functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_tool_call(self) -> None:
        """Test successful tool execution."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        mock_session = AsyncMock()
        mock_response = {
            "content": [
                {
                    "type": "text",
                    "text": "Search results: Found 5 items"
                }
            ]
        }
        mock_session.call_tool = AsyncMock(return_value=mock_response)
        client._session = mock_session
        
        result = await client.call_tool("search", {"query": "test"})
        
        assert result == "Search results: Found 5 items"
        mock_session.call_tool.assert_called_once_with(
            name="search",
            arguments={"query": "test"}
        )
    
    @pytest.mark.asyncio
    async def test_tool_call_server_error(self) -> None:
        """Test tool execution with server error."""
        config = MCPServerConfig(
            name="test_server", 
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(side_effect=Exception("Tool execution failed"))
        client._session = mock_session
        
        with pytest.raises(MCPToolError, match="Tool execution failed"):
            await client.call_tool("search", {"query": "test"})
    
    @pytest.mark.asyncio
    async def test_tool_call_execution_error(self) -> None:
        """Test tool execution with execution error in response."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        mock_session = AsyncMock()
        mock_response = {
            "content": [
                {
                    "type": "text",
                    "text": "Error: Invalid query format"
                }
            ],
            "isError": True
        }
        mock_session.call_tool = AsyncMock(return_value=mock_response)
        client._session = mock_session
        
        with pytest.raises(MCPToolError, match="Tool execution error"):
            await client.call_tool("search", {"query": ""})


class TestMCPClientStreamingExecution:
    """Test streaming tool execution functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_streaming_call(self) -> None:
        """Test successful streaming tool execution."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock streaming response
        async def mock_stream():
            yield {"type": "data", "content": "First chunk"}
            yield {"type": "data", "content": "Second chunk"}
            yield {"type": "complete", "content": "Done"}
        
        mock_session = AsyncMock()
        client._session = mock_session
        
        with patch.object(client, '_call_tool_stream_http', return_value=mock_stream()):
            chunks = []
            async for chunk in client.call_tool_stream("search", {"query": "test"}):
                chunks.append(chunk)
            
            assert len(chunks) == 3
            assert chunks[0]["content"] == "First chunk"
            assert chunks[1]["content"] == "Second chunk"
            assert chunks[2]["type"] == "complete"
    
    @pytest.mark.asyncio
    async def test_streaming_call_server_error(self) -> None:
        """Test streaming tool execution with server error."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        mock_session = AsyncMock()
        client._session = mock_session
        
        with patch.object(client, '_call_tool_stream_http', side_effect=aiohttp.ClientError("Streaming failed")):
            with pytest.raises(MCPToolError, match="Streaming tool execution failed"):
                async for chunk in client.call_tool_stream("search", {"query": "test"}):
                    pass
    
    @pytest.mark.asyncio
    async def test_streaming_call_malformed_json(self) -> None:
        """Test streaming with malformed JSON chunks."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock streaming response with malformed JSON
        async def mock_stream():
            yield "invalid json chunk"
            yield '{"type": "data", "content": "valid chunk"}'
        
        mock_session = AsyncMock()
        client._session = mock_session
        
        with patch.object(client, '_call_tool_stream_http', return_value=mock_stream()):
            chunks = []
            async for chunk in client.call_tool_stream("search", {"query": "test"}):
                chunks.append(chunk)
            
            # Should skip malformed chunk and only return valid one
            assert len(chunks) == 1
            assert chunks[0]["content"] == "valid chunk"


class TestMCPClientEdgeCases:
    """Test edge cases and configuration options."""
    
    @pytest.mark.asyncio
    async def test_client_timeout_configuration(self) -> None:
        """Test client with custom timeout configuration."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            timeout=60
        )
        client = MCPClient(config)
        
        assert client.config.timeout == 60
    
    @pytest.mark.asyncio
    async def test_client_headers_configuration(self) -> None:
        """Test client with custom headers."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            headers={"Authorization": "Bearer token123", "Custom-Header": "value"}
        )
        client = MCPClient(config)
        
        assert client.config.headers["Authorization"] == "Bearer token123"
        assert client.config.headers["Custom-Header"] == "value"
    
    @pytest.mark.asyncio
    async def test_client_multiple_sessions(self) -> None:
        """Test that multiple clients can exist independently."""
        config1 = MCPServerConfig(name="server1", endpoint="http://localhost:8000/mcp")
        config2 = MCPServerConfig(name="server2", endpoint="http://localhost:8001/mcp")
        
        client1 = MCPClient(config1)
        client2 = MCPClient(config2)
        
        assert client1.config.name == "server1"
        assert client2.config.name == "server2"
        assert client1.config.endpoint != client2.config.endpoint
    
    @pytest.mark.asyncio
    async def test_session_property_access(self) -> None:
        """Test session property returns None when not connected."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        assert client.session is None
        assert not client.is_connected
        
        # Mock connection
        mock_session = AsyncMock()
        client._session = mock_session
        
        assert client.session == mock_session
        assert client.is_connected