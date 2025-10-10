# -*- coding: utf-8 -*-
"""Enhanced streaming validation for improved MCPClient implementation."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import AsyncIterator
import aiohttp

from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig


class TestImprovedMCPClientStreaming:
    """Test the improved streaming implementation."""
    
    @pytest.mark.asyncio
    async def test_simulated_streaming_with_chunking(self) -> None:
        """Test that the improved implementation provides real streaming chunks."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock session with a longer response for chunking
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_content = AsyncMock()
        mock_content.text = "This is a longer response that should be chunked into multiple pieces for streaming demonstration and testing purposes."
        mock_result.content = [mock_content]
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        
        # Set session and connected state
        client._session = mock_session
        client._connected = True
        
        # Mock the HTTP streaming to fall back to sync method
        async def mock_http_streaming(*args, **kwargs):
            raise Exception("HTTP streaming not available - fallback")
            
        with patch.object(client, '_call_tool_stream_http', side_effect=mock_http_streaming):
            
            # Record timing and chunks
            start_time = asyncio.get_event_loop().time()
            chunks = []
            chunk_times = []
            
            async for chunk in client.call_tool_stream("test", {"param": "value"}):
                chunk_time = asyncio.get_event_loop().time() - start_time
                chunks.append(chunk)
                chunk_times.append(chunk_time)
            
            # Validation: Should have multiple chunks now
            print(f"\n=== IMPROVED STREAMING RESULTS ===")
            print(f"Total chunks: {len(chunks)}")
            print(f"Chunk timings: {[round(t, 3) for t in chunk_times]}")
            for i, chunk in enumerate(chunks):
                print(f"Chunk {i}: {chunk['type']} - {chunk['content'][:50]}...")
            print("================================\n")
            
            # Real streaming validation
            assert len(chunks) > 1, "Improved implementation should yield multiple chunks"
            assert chunk_times[-1] > 0.1, "Streaming should take noticeable time due to delays"
            
            # Verify chunks have timestamps and proper structure
            for chunk in chunks:
                assert "timestamp" in chunk
                assert "tool_name" in chunk
                assert chunk["tool_name"] == "test"
                assert chunk["type"] in ["data", "result"]
            
            # Last chunk should be marked as final
            assert chunks[-1]["is_final"] is True
    
    @pytest.mark.asyncio
    async def test_http_sse_streaming_simulation(self) -> None:
        """Test HTTP SSE streaming handling."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        client._connected = True
        client._session = AsyncMock()  # Add session mock
        
        # Mock SSE streaming response
        class MockSSEResponse:
            def __init__(self):
                self.status = 200
                self.headers = {'content-type': 'text/event-stream'}
                self.content = self._create_sse_content()
            
            async def _create_sse_content(self):
                sse_lines = [
                    b'data: {"type": "start", "content": "Processing request..."}\n',
                    b'data: {"type": "progress", "content": "50% complete"}\n', 
                    b'data: {"type": "data", "content": "Here are the results"}\n',
                    b'data: [DONE]\n'
                ]
                for line in sse_lines:
                    await asyncio.sleep(0.05)  # Simulate network delay
                    yield line
        
        mock_response = MockSSEResponse()
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.post.return_value.__aenter__.return_value = mock_response
            
            chunks = []
            async for chunk in client.call_tool_stream("test", {}):
                chunks.append(chunk)
            
            # Should have processed SSE chunks
            assert len(chunks) == 4  # 3 data chunks + 1 completion
            assert chunks[0]["content"]["type"] == "start"
            assert chunks[1]["content"]["type"] == "progress"
            assert chunks[2]["content"]["type"] == "data"
            assert chunks[3]["type"] == "complete"
    
    @pytest.mark.asyncio
    async def test_streaming_fallback_chain(self) -> None:
        """Test the complete fallback chain: HTTP -> SDK -> Simulation."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        client = MCPClient(config)
        
        # Mock all components for complete fallback test
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_content = AsyncMock()
        mock_content.text = "Final fallback result"
        mock_result.content = [mock_content]
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        
        client._session = mock_session
        client._connected = True
        
        # Mock HTTP failure to trigger fallback
        async def mock_http_failure(*args, **kwargs):
            raise aiohttp.ClientError("Network error")
            
        with patch.object(client, '_call_tool_stream_http', side_effect=mock_http_failure):
            chunks = []
            async for chunk in client.call_tool_stream("test", {}):
                chunks.append(chunk)
            
            # Should fallback to simulated streaming
            assert len(chunks) >= 1
            assert any("Final fallback result" in str(chunk.get("content", "")) or 
                     "Final fallback result" in str(chunk.get("data", "")) 
                     for chunk in chunks)
    
    @pytest.mark.asyncio
    async def test_streaming_performance_comparison(self) -> None:
        """Compare old vs new streaming performance."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        
        # Test old implementation (single chunk)
        old_client = MCPClient(config)
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_content = AsyncMock()
        mock_content.text = "Test result " * 20  # Long result
        mock_result.content = [mock_content]
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        
        old_client._session = mock_session
        old_client._connected = True
        
        # Simulate old behavior (single chunk)
        old_start = asyncio.get_event_loop().time()
        old_chunks = []
        
        # Create single chunk like old implementation
        result = await old_client.call_tool("test", {})
        old_chunks.append({
            "type": "result",
            "data": result,
            "is_final": True,
            "tool_name": "test"
        })
        old_duration = asyncio.get_event_loop().time() - old_start
        
        # Test new implementation (multiple chunks)
        new_client = MCPClient(config)
        new_client._session = mock_session
        new_client._connected = True
        
        with patch.object(new_client, '_call_tool_stream_http', side_effect=Exception("Use fallback")):
            new_start = asyncio.get_event_loop().time()
            new_chunks = []
            
            async for chunk in new_client.call_tool_stream("test", {}):
                new_chunks.append(chunk)
                
            new_duration = asyncio.get_event_loop().time() - new_start
        
        print(f"\n=== PERFORMANCE COMPARISON ===")
        print(f"Old implementation: {len(old_chunks)} chunks in {old_duration:.3f}s")
        print(f"New implementation: {len(new_chunks)} chunks in {new_duration:.3f}s")
        print(f"Streaming improvement: {len(new_chunks) - len(old_chunks)} additional chunks")
        print("==============================\n")
        
        # New implementation should provide better streaming experience
        assert len(new_chunks) > len(old_chunks), "New implementation should provide more chunks"
        assert new_duration > old_duration, "New implementation should show streaming delay"


if __name__ == "__main__":
    # Run the enhanced streaming tests
    pytest.main([__file__, "-v", "-s"])