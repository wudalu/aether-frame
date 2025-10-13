#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive test suite for unified MCP interface."""

import asyncio
import pytest
import time
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src"))

from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig
from aether_frame.tools.mcp.tool_wrapper import MCPTool
from aether_frame.contracts import ToolRequest, ToolResult
from aether_frame.contracts.responses import ToolStatus


class TestUnifiedMCPInterface:
    """Comprehensive test suite for unified MCP interface."""
    
    @pytest.fixture
    def mock_config(self):
        """Create mock MCP server configuration."""
        return MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            timeout=30
        )
    
    @pytest.fixture
    async def mock_client(self, mock_config):
        """Create mock MCP client."""
        client = MCPClient(mock_config)
        
        # Mock the session and connection
        mock_session = AsyncMock()
        mock_stream_context = AsyncMock()
        mock_session_context = AsyncMock()
        
        client._session = mock_session
        client._stream_context = mock_stream_context
        client._session_context = mock_session_context
        client._connected = True
        
        return client
    
    @pytest.mark.asyncio
    async def test_call_tool_stream_basic_functionality(self, mock_client):
        """Test basic call_tool_stream functionality."""
        
        # Mock the session.call_tool to return a result
        mock_result = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Test result content"
        mock_result.content = [mock_content]
        mock_client._session.call_tool.return_value = mock_result
        
        # Test streaming
        chunks = []
        async for chunk in mock_client.call_tool_stream("test_tool", {"param": "value"}):
            chunks.append(chunk)
        
        # Verify chunks
        assert len(chunks) >= 2  # At least start and complete chunks
        
        # Verify start chunk
        start_chunk = chunks[0]
        assert start_chunk["type"] == "stream_start"
        assert start_chunk["tool_name"] == "test_tool"
        assert start_chunk["arguments"] == {"param": "value"}
        assert "progress_token" in start_chunk
        
        # Verify final chunk
        final_chunk = chunks[-1]
        assert final_chunk["type"] == "complete_result"
        assert final_chunk["is_final"] is True
        assert final_chunk["content"] == "Test result content"
        
        # Verify session.call_tool was called correctly with progress_callback
        mock_client._session.call_tool.assert_called_once()
        call_args = mock_client._session.call_tool.call_args
        assert call_args[0] == ("test_tool", {"param": "value"})  # positional args
        assert "progress_callback" in call_args[1]  # keyword args
    
    @pytest.mark.asyncio
    async def test_call_tool_synchronous_interface(self, mock_client):
        """Test that call_tool works by collecting streaming results."""
        
        # Mock the session.call_tool to return a result
        mock_result = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Synchronous result"
        mock_result.content = [mock_content]
        mock_client._session.call_tool.return_value = mock_result
        
        # Test synchronous call
        result = await mock_client.call_tool("sync_tool", {"sync_param": "sync_value"})
        
        # Verify result
        assert result == "Synchronous result"
    
    @pytest.mark.asyncio
    async def test_progress_notifications_handling(self, mock_client):
        """Test progress notifications are properly handled."""
        
        # Create a more complex mock that simulates progress
        async def mock_call_tool_with_delay(*args, **kwargs):
            """Simulate tool execution with delay."""
            await asyncio.sleep(0.1)
            mock_result = MagicMock()
            mock_content = MagicMock()
            mock_content.text = "Progress test result"
            mock_result.content = [mock_content]
            return mock_result
        
        mock_client._session.call_tool.side_effect = mock_call_tool_with_delay
        
        # Simulate progress notifications
        async def simulate_progress_notifications():
            """Simulate server sending progress notifications."""
            await asyncio.sleep(0.05)  # Small delay before first progress
            
            # Find the progress handler for this operation
            if mock_client._progress_handlers:
                progress_token = list(mock_client._progress_handlers.keys())[0]
                queue = mock_client._progress_handlers[progress_token]
                
                # Send progress notifications
                await queue.put({
                    "type": "progress_update",
                    "progress": 0.5,
                    "total": 1.0,
                    "message": "50% complete",
                    "progress_token": progress_token,
                    "timestamp": time.time()
                })
                
                await asyncio.sleep(0.05)
                await queue.put({
                    "type": "progress_update", 
                    "progress": 1.0,
                    "total": 1.0,
                    "message": "100% complete",
                    "progress_token": progress_token,
                    "timestamp": time.time()
                })
        
        # Start progress simulation
        progress_task = asyncio.create_task(simulate_progress_notifications())
        
        # Test streaming with progress
        chunks = []
        async for chunk in mock_client.call_tool_stream("progress_tool", {}):
            chunks.append(chunk)
            
        await progress_task
        
        # Verify we received progress updates
        progress_chunks = [c for c in chunks if c.get("type") == "progress_update"]
        assert len(progress_chunks) >= 1  # Should have received progress updates
        
        # Verify final result
        final_chunks = [c for c in chunks if c.get("type") == "complete_result"]
        assert len(final_chunks) == 1
        assert final_chunks[0]["content"] == "Progress test result"
    
    @pytest.mark.asyncio
    async def test_error_handling_in_streaming(self, mock_client):
        """Test error handling in streaming interface."""
        
        # Mock tool execution that raises an error
        mock_client._session.call_tool.side_effect = Exception("Tool execution failed")
        
        # Test streaming error handling
        chunks = []
        async for chunk in mock_client.call_tool_stream("error_tool", {}):
            chunks.append(chunk)
        
        # Verify error chunk
        error_chunks = [c for c in chunks if c.get("type") == "error"]
        assert len(error_chunks) == 1
        assert "Tool execution failed" in error_chunks[0]["error"]
        assert error_chunks[0]["is_final"] is True
    
    @pytest.mark.asyncio
    async def test_error_handling_in_synchronous(self, mock_client):
        """Test error handling in synchronous interface."""
        
        # Mock tool execution that raises an error
        mock_client._session.call_tool.side_effect = Exception("Sync tool failed")
        
        # Test synchronous error handling
        with pytest.raises(MCPToolError) as exc_info:
            await mock_client.call_tool("error_sync_tool", {})
        
        # The error message should contain either the original error or "Tool execution failed"
        error_msg = str(exc_info.value)
        assert "Sync tool failed" in error_msg or "Tool execution failed" in error_msg
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self, mock_config):
        """Test connection error handling."""
        
        # Create disconnected client
        client = MCPClient(mock_config)
        client._connected = False
        
        # Test streaming with disconnected client
        with pytest.raises(MCPConnectionError):
            async for chunk in client.call_tool_stream("test_tool", {}):
                pass
        
        # Test synchronous with disconnected client
        with pytest.raises(MCPConnectionError):
            await client.call_tool("test_tool", {})
    
    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, mock_client):
        """Test multiple concurrent tool calls."""
        
        # Mock different results for different tools
        call_count = 0
        async def mock_call_tool_varied(name, args, progress_callback=None, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate work
            
            mock_result = MagicMock()
            mock_content = MagicMock()
            mock_content.text = f"Result for {name} (call {call_count})"
            mock_result.content = [mock_content]
            return mock_result
        
        mock_client._session.call_tool.side_effect = mock_call_tool_varied
        
        # Start multiple concurrent streams
        tasks = [
            asyncio.create_task(mock_client.call_tool("tool_1", {"id": 1})),
            asyncio.create_task(mock_client.call_tool("tool_2", {"id": 2})),
            asyncio.create_task(mock_client.call_tool("tool_3", {"id": 3}))
        ]
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks)
        
        # Verify all completed successfully
        assert len(results) == 3
        assert all("Result for tool_" in str(result) for result in results)
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_tool_wrapper_integration(self, mock_client):
        """Test MCPTool wrapper integration with unified interface."""
        
        # Mock tool execution
        mock_result = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Wrapper test result"
        mock_result.content = [mock_content]
        mock_client._session.call_tool.return_value = mock_result
        
        # Create MCPTool wrapper
        mcp_tool = MCPTool(
            mcp_client=mock_client,
            tool_name="wrapper_tool",
            tool_description="Test wrapper tool",
            tool_schema={"type": "object"},
            namespace="test_namespace"
        )
        
        # Test synchronous execution via wrapper
        tool_request = ToolRequest(
            tool_name="wrapper_tool",
            tool_namespace="test_namespace",
            parameters={"wrapper_param": "wrapper_value"}
        )
        
        result = await mcp_tool.execute(tool_request)
        
        # Verify wrapper result
        assert isinstance(result, ToolResult)
        assert result.status == ToolStatus.SUCCESS
        assert result.result_data == "Wrapper test result"
        assert result.tool_name == "test_namespace.wrapper_tool"
    
    @pytest.mark.asyncio
    async def test_streaming_wrapper_integration(self, mock_client):
        """Test MCPTool streaming wrapper integration."""
        
        # Mock tool execution
        mock_result = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Streaming wrapper result"
        mock_result.content = [mock_content]
        mock_client._session.call_tool.return_value = mock_result
        
        # Create MCPTool wrapper
        mcp_tool = MCPTool(
            mcp_client=mock_client,
            tool_name="streaming_wrapper_tool",
            tool_description="Test streaming wrapper tool",
            tool_schema={"type": "object"},
            namespace="test_namespace"
        )
        
        # Test streaming execution via wrapper
        tool_request = ToolRequest(
            tool_name="streaming_wrapper_tool",
            tool_namespace="test_namespace",
            parameters={"stream_param": "stream_value"}
        )
        
        chunks = []
        async for chunk in mcp_tool.execute_stream(tool_request):
            chunks.append(chunk)
        
        # Verify streaming wrapper results
        assert len(chunks) >= 2  # At least start and complete
        
        # Check final chunk
        final_chunks = [c for c in chunks if c.is_final]
        assert len(final_chunks) >= 1
        final_chunk = final_chunks[-1]
        assert "Streaming wrapper result" in str(final_chunk.content)
    
    @pytest.mark.asyncio
    async def test_notification_handler_routing(self, mock_client):
        """Test notification handler correctly routes progress events."""
        
        # Test multiple concurrent operations with different tokens
        progress_tokens = []
        received_events = {}
        
        # Mock notification handler behavior
        original_handler = mock_client._notification_handler
        
        async def tracked_handler(message):
            """Track notification handling."""
            if hasattr(message, 'method') and message.method == "notifications/progress":
                params = getattr(message, 'params', {})
                token = params.get('progressToken') or params.get('progress_token')
                if token:
                    if token not in received_events:
                        received_events[token] = []
                    received_events[token].append(params)
            
            return await original_handler(message)
        
        mock_client._notification_handler = tracked_handler
        
        # Create mock message for testing
        mock_message = MagicMock()
        mock_message.method = "notifications/progress"
        mock_message.params = {
            'progressToken': 'test_token_123',
            'progress': 0.5,
            'total': 1.0,
            'message': 'Test progress'
        }
        
        # Test notification handling
        await mock_client._notification_handler(mock_message)
        
        # Verify routing (basic test - full integration needs real server)
        # This tests the handler doesn't crash
        assert True  # Handler completed without error
    
    def test_supports_streaming_property(self, mock_client):
        """Test that client reports streaming support."""
        assert mock_client.supports_streaming is True
    
    @pytest.mark.asyncio
    async def test_cleanup_and_disconnect(self, mock_client):
        """Test proper cleanup on disconnect."""
        
        # Add some progress handlers
        mock_client._progress_handlers["test_token_1"] = asyncio.Queue()
        mock_client._progress_handlers["test_token_2"] = asyncio.Queue()
        
        # Test disconnect
        await mock_client.disconnect()
        
        # Verify cleanup
        assert len(mock_client._progress_handlers) == 0
        assert mock_client._connected is False


class TestRealServerIntegration:
    """Integration tests with real MCP server (requires server running)."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_server_basic_tools(self):
        """Test basic tools with real server."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            timeout=10
        )
        
        try:
            async with MCPClient(config) as client:
                # Test echo tool
                result = await client.call_tool("echo", {"text": "Integration test"})
                assert "Integration test" in str(result)
                
                # Test add tool
                result = await client.call_tool("add", {"a": 5, "b": 3})
                assert result == 8 or "8" in str(result)
                
        except MCPConnectionError:
            pytest.skip("MCP test server not available")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_server_streaming(self):
        """Test streaming with real server."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            timeout=10
        )
        
        try:
            async with MCPClient(config) as client:
                chunks = []
                async for chunk in client.call_tool_stream("echo", {"text": "Streaming test"}):
                    chunks.append(chunk)
                
                assert len(chunks) >= 2  # Start and complete
                assert any(c.get("type") == "stream_start" for c in chunks)
                assert any(c.get("type") == "complete_result" for c in chunks)
                
        except MCPConnectionError:
            pytest.skip("MCP test server not available")


if __name__ == "__main__":
    # Run basic tests
    print("🧪 Running Unified MCP Interface Tests")
    print("=" * 50)
    
    # Run pytest with verbose output
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "-m", "not integration"  # Skip integration tests by default
    ])