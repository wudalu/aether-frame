# -*- coding: utf-8 -*-
"""Test real streaming MCP implementation."""

import asyncio
import pytest
from unittest.mock import patch

from aether_frame.tools.mcp.client_with_real_streaming import MCPClient
from aether_frame.tools.mcp.config import MCPServerConfig


class TestRealStreamingMCP:
    """Test real streaming MCP functionality."""
    
    @pytest.mark.asyncio
    async def test_streaming_detection(self) -> None:
        """Test streaming capability detection."""
        config = MCPServerConfig(
            name="streaming_server",
            endpoint="http://localhost:8000/mcp"
        )
        
        # Mock the streaming client setup
        with patch('aether_frame.tools.mcp.client_with_real_streaming.streamablehttp_client') as mock_client, \
             patch('aether_frame.tools.mcp.client_with_real_streaming.ClientSession') as mock_session:
            
            # Mock successful connection
            mock_stream_context = mock_client.return_value
            mock_stream_context.__aenter__.return_value = (None, None, None)
            
            mock_session_context = mock_session.return_value
            mock_session_context.__aenter__.return_value.initialize = lambda: None
            
            # Mock streaming detection
            with patch('aiohttp.ClientSession') as mock_http_session:
                mock_response = mock_http_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value
                mock_response.status = 200  # SSE endpoint available
                
                client = MCPClient(config)
                await client.connect()
                
                # Should detect streaming support
                assert client.supports_streaming is True
                
                await client.disconnect()
    
    @pytest.mark.asyncio 
    async def test_real_vs_simulated_streaming(self) -> None:
        """Test the difference between real and simulated streaming."""
        config = MCPServerConfig(
            name="test_server", 
            endpoint="http://localhost:8000/mcp"
        )
        
        client = MCPClient(config)
        
        # Test simulated streaming (when server doesn't support streaming)
        with patch.object(client, '_supports_streaming', False), \
             patch.object(client, '_connected', True), \
             patch.object(client, 'call_tool', return_value="Long test result that should be chunked into multiple pieces"):
            
            chunks = []
            async for chunk in client.call_tool_stream("test_tool", {}):
                chunks.append(chunk)
            
            # Should have multiple chunks with simulated streaming
            assert len(chunks) > 1
            assert all(chunk.get("real_streaming") is False for chunk in chunks)
    
    @pytest.mark.asyncio
    async def test_universal_tool_streaming_metadata(self) -> None:
        """Test that UniversalTool includes streaming metadata."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        
        client = MCPClient(config)
        client._supports_streaming = True  # Mock streaming support
        
        # Mock MCP tool
        from unittest.mock import MagicMock
        mock_mcp_tool = MagicMock()
        mock_mcp_tool.name = "test_tool"
        mock_mcp_tool.description = "Test streaming tool"
        mock_mcp_tool.inputSchema = {"type": "object"}
        
        universal_tool = client._convert_mcp_tool_to_universal(mock_mcp_tool)
        
        # Should include streaming metadata
        assert universal_tool.supports_streaming is True
        assert universal_tool.metadata["supports_real_streaming"] is True
        assert universal_tool.metadata["mcp_tool_type"] == "mcp_sdk_tool"


if __name__ == "__main__":
    # Manual test with real server
    async def manual_test():
        print("=== Manual Real Streaming Test ===")
        
        # First, let's start the test server in background
        print("Note: Start the streaming test server first:")
        print("python tests/tools/mcp/streaming_test_server.py")
        print()
        
        config = MCPServerConfig(
            name="streaming_test",
            endpoint="http://localhost:8000/mcp"
        )
        
        try:
            async with MCPClient(config) as client:
                print(f"Connected to server: {client.is_connected}")
                print(f"Supports streaming: {client.supports_streaming}")
                
                # Discover tools
                tools = await client.discover_tools()
                print(f"Available tools: {[tool.name for tool in tools]}")
                
                # Test streaming
                print("\n--- Testing streaming ---")
                
                chunks = []
                async for chunk in client.call_tool_stream("streaming_search", {"query": "test"}):
                    chunks.append(chunk)
                    print(f"Chunk {len(chunks)}: {chunk.get('type')} - {chunk.get('content', '')[:50]}...")
                
                print(f"\nTotal chunks received: {len(chunks)}")
                print(f"Real streaming: {chunks[0].get('real_streaming', False) if chunks else 'N/A'}")
                
        except Exception as e:
            print(f"Connection failed: {e}")
            print("Make sure the streaming test server is running!")
    
    # Run manual test
    if __name__ == "__main__":
        asyncio.run(manual_test())