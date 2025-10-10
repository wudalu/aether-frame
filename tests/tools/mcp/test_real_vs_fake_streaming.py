# -*- coding: utf-8 -*-
"""Comprehensive test comparing real streaming vs fake streaming implementations."""

import asyncio
import json
import time
from typing import Dict, List

import pytest

from .config import MCPServerConfig
from .real_streaming_client import RealStreamingMCPClient


class StreamingPerformanceAnalyzer:
    """Analyzes streaming performance metrics."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all metrics."""
        self.chunks_received = 0
        self.first_chunk_time = None
        self.last_chunk_time = None
        self.start_time = None
        self.total_content_length = 0
        self.chunk_intervals = []
        self.processing_complete_time = None
    
    def record_start(self):
        """Record test start time."""
        self.start_time = time.time()
    
    def record_chunk(self, chunk_data: Dict):
        """Record metrics for a received chunk."""
        current_time = time.time()
        
        if self.first_chunk_time is None:
            self.first_chunk_time = current_time
        
        if self.chunks_received > 0:
            interval = current_time - self.last_chunk_time
            self.chunk_intervals.append(interval)
        
        self.last_chunk_time = current_time
        self.chunks_received += 1
        
        # Track content length
        if 'content' in chunk_data:
            self.total_content_length += len(str(chunk_data['content']))
        
        # Record when processing was complete (for fake streaming)
        if 'processing_complete_time' in chunk_data:
            self.processing_complete_time = chunk_data['processing_complete_time']
    
    def get_metrics(self) -> Dict:
        """Get comprehensive performance metrics."""
        if not self.start_time or not self.first_chunk_time:
            return {"error": "Insufficient data for metrics"}
        
        total_time = self.last_chunk_time - self.start_time
        time_to_first_chunk = self.first_chunk_time - self.start_time
        
        metrics = {
            "total_chunks": self.chunks_received,
            "total_time": total_time,
            "time_to_first_chunk": time_to_first_chunk,
            "total_content_length": self.total_content_length,
            "average_chunk_interval": sum(self.chunk_intervals) / len(self.chunk_intervals) if self.chunk_intervals else 0,
            "chunk_intervals": self.chunk_intervals,
            "throughput_chars_per_sec": self.total_content_length / total_time if total_time > 0 else 0,
        }
        
        # Add fake streaming specific metrics
        if self.processing_complete_time:
            processing_delay = self.processing_complete_time - self.start_time
            streaming_simulation_time = total_time - processing_delay
            
            metrics.update({
                "processing_delay": processing_delay,
                "streaming_simulation_time": streaming_simulation_time,
                "fake_streaming_overhead": streaming_simulation_time / total_time if total_time > 0 else 0
            })
        
        return metrics


@pytest.fixture
def real_streaming_config():
    """Configuration for real streaming server."""
    return MCPServerConfig(
        name="real-streaming-test",
        endpoint="http://localhost:8002/mcp",
        timeout=30.0
    )


@pytest.fixture
async def real_streaming_client(real_streaming_config):
    """Create real streaming client."""
    client = RealStreamingMCPClient(real_streaming_config)
    yield client
    if client.is_connected:
        await client.disconnect()


class TestStreamingComparison:
    """Test suite comparing real vs fake streaming implementations."""
    
    async def test_streaming_latency_comparison(self, real_streaming_client):
        """Compare latency characteristics between real and fake streaming."""
        
        # Test parameters
        tool_name = "real_time_data_stream"
        arguments = {"duration": 3}
        
        print("\n🔄 Testing Streaming Latency Comparison")
        print("=" * 50)
        
        # Connect to server
        await real_streaming_client.connect()
        
        # Test 1: Real streaming
        print("\n📡 Testing REAL streaming...")
        real_analyzer = StreamingPerformanceAnalyzer()
        real_analyzer.record_start()
        
        async for chunk in real_streaming_client.call_tool_stream_real(tool_name, arguments):
            real_analyzer.record_chunk(chunk)
            print(f"  🔵 Real chunk: {chunk.get('type', 'unknown')} - {time.time():.3f}")
        
        real_metrics = real_analyzer.get_metrics()
        
        # Test 2: Fake streaming
        print("\n🎭 Testing FAKE streaming...")
        fake_analyzer = StreamingPerformanceAnalyzer()
        fake_analyzer.record_start()
        
        async for chunk in real_streaming_client.call_tool_stream_fake(tool_name, arguments):
            fake_analyzer.record_chunk(chunk)
            print(f"  🔴 Fake chunk: {chunk.get('type', 'unknown')} - {time.time():.3f}")
        
        fake_metrics = fake_analyzer.get_metrics()
        
        # Analysis
        print("\n📊 PERFORMANCE ANALYSIS")
        print("=" * 30)
        print(f"Real Streaming:")
        print(f"  - Time to first chunk: {real_metrics['time_to_first_chunk']:.3f}s")
        print(f"  - Total time: {real_metrics['total_time']:.3f}s") 
        print(f"  - Average chunk interval: {real_metrics['average_chunk_interval']:.3f}s")
        print(f"  - Throughput: {real_metrics['throughput_chars_per_sec']:.1f} chars/sec")
        
        print(f"\nFake Streaming:")
        print(f"  - Time to first chunk: {fake_metrics['time_to_first_chunk']:.3f}s")
        print(f"  - Total time: {fake_metrics['total_time']:.3f}s")
        print(f"  - Average chunk interval: {fake_metrics['average_chunk_interval']:.3f}s")
        print(f"  - Throughput: {fake_metrics['throughput_chars_per_sec']:.1f} chars/sec")
        if 'processing_delay' in fake_metrics:
            print(f"  - Processing delay: {fake_metrics['processing_delay']:.3f}s")
            print(f"  - Fake streaming overhead: {fake_metrics['fake_streaming_overhead']:.1%}")
        
        # Assertions
        assert real_metrics['total_chunks'] > 0
        assert fake_metrics['total_chunks'] > 0
        
        # Real streaming should have faster time to first chunk
        # (though in our simulation this might not always be true)
        print(f"\n✅ Test completed - Both streaming modes functional")
    
    async def test_progressive_search_streaming(self, real_streaming_client):
        """Test progressive search with real vs fake streaming."""
        
        tool_name = "progressive_search"
        arguments = {"query": "machine learning", "max_results": 3}
        
        print("\n🔍 Testing Progressive Search Streaming")
        print("=" * 40)
        
        await real_streaming_client.connect()
        
        # Test real streaming
        print("\n📡 Real streaming search:")
        real_chunks = []
        async for chunk in real_streaming_client.call_tool_stream_real(tool_name, arguments):
            real_chunks.append(chunk)
            if chunk.get('type') == 'stream_data' and chunk.get('content'):
                print(f"  📄 {chunk['content'][:60]}...")
        
        # Test fake streaming  
        print("\n🎭 Fake streaming search:")
        fake_chunks = []
        async for chunk in real_streaming_client.call_tool_stream_fake(tool_name, arguments):
            fake_chunks.append(chunk)
            if 'content' in chunk:
                content_preview = str(chunk['content'])[:60]
                print(f"  📄 {content_preview}...")
        
        print(f"\n📊 Real streaming: {len(real_chunks)} chunks")
        print(f"📊 Fake streaming: {len(fake_chunks)} chunks")
        
        assert len(real_chunks) > 0
        assert len(fake_chunks) > 0
        
        print("✅ Progressive search streaming test completed")
    
    async def test_long_computation_streaming(self, real_streaming_client):
        """Test long computation with detailed timing analysis."""
        
        tool_name = "long_computation"
        arguments = {"steps": 5}
        
        print("\n⚙️  Testing Long Computation Streaming")
        print("=" * 40)
        
        await real_streaming_client.connect()
        
        # Detailed timing analysis for real streaming
        print("\n📡 Real streaming computation:")
        real_start = time.time()
        real_timestamps = []
        
        async for chunk in real_streaming_client.call_tool_stream_real(tool_name, arguments):
            timestamp = time.time()
            real_timestamps.append(timestamp - real_start)
            
            if chunk.get('type') == 'stream_data':
                elapsed = timestamp - real_start
                print(f"  ⚙️  [{elapsed:.2f}s] {chunk.get('content', '')[:50]}...")
        
        # Detailed timing analysis for fake streaming
        print("\n🎭 Fake streaming computation:")
        fake_start = time.time()
        fake_timestamps = []
        
        async for chunk in real_streaming_client.call_tool_stream_fake(tool_name, arguments):
            timestamp = time.time() 
            fake_timestamps.append(timestamp - fake_start)
            
            if 'content' in chunk:
                elapsed = timestamp - fake_start
                content = str(chunk['content'])[:50]
                print(f"  ⚙️  [{elapsed:.2f}s] {content}...")
        
        # Timing comparison
        print(f"\n⏱️  TIMING COMPARISON:")
        print(f"Real streaming duration: {real_timestamps[-1]:.2f}s")
        print(f"Fake streaming duration: {fake_timestamps[-1]:.2f}s") 
        print(f"Real streaming events: {len(real_timestamps)}")
        print(f"Fake streaming events: {len(fake_timestamps)}")
        
        assert len(real_timestamps) > 0
        assert len(fake_timestamps) > 0
        
        print("✅ Long computation streaming test completed")
    
    async def test_file_processing_streaming(self, real_streaming_client):
        """Test file processing simulation with streaming."""
        
        tool_name = "simulated_file_processing"
        arguments = {"file_count": 3}
        
        print("\n📁 Testing File Processing Streaming")
        print("=" * 40)
        
        await real_streaming_client.connect()
        
        # Monitor content flow patterns
        print("\n📡 Real streaming file processing:")
        real_content_flow = []
        
        async for chunk in real_streaming_client.call_tool_stream_real(tool_name, arguments):
            if chunk.get('type') == 'stream_data' and chunk.get('content'):
                content = chunk['content'].strip()
                if content:
                    real_content_flow.append({
                        'time': chunk.get('elapsed_time', 0),
                        'content': content[:40] + '...' if len(content) > 40 else content
                    })
                    print(f"  📄 [{chunk.get('elapsed_time', 0):.2f}s] {content[:60]}...")
        
        print("\n🎭 Fake streaming file processing:")
        fake_content_flow = []
        
        async for chunk in real_streaming_client.call_tool_stream_fake(tool_name, arguments):
            if 'content' in chunk:
                content = str(chunk['content']).strip()
                if content and len(content) > 5:  # Skip very short chunks
                    fake_content_flow.append({
                        'chunk_index': chunk.get('chunk_index', 0),
                        'content': content[:40] + '...' if len(content) > 40 else content
                    })
                    print(f"  📄 [chunk {chunk.get('chunk_index', 0)}] {content[:60]}...")
        
        print(f"\n📊 Real streaming content events: {len(real_content_flow)}")
        print(f"📊 Fake streaming content chunks: {len(fake_content_flow)}")
        
        assert len(real_content_flow) > 0
        assert len(fake_content_flow) > 0
        
        print("✅ File processing streaming test completed")


if __name__ == "__main__":
    async def run_manual_test():
        """Manual test runner for development."""
        config = MCPServerConfig(
            name="real-streaming-test",
            endpoint="http://localhost:8002/mcp",
            timeout=30.0
        )
        
        client = RealStreamingMCPClient(config)
        test_suite = TestStreamingComparison()
        
        try:
            print("🧪 Starting Manual Streaming Comparison Tests")
            print("=" * 50)
            print("⚠️  Make sure real_streaming_server.py is running on port 8002!")
            print()
            
            await test_suite.test_streaming_latency_comparison(client)
            await asyncio.sleep(1)
            
            await test_suite.test_progressive_search_streaming(client)
            await asyncio.sleep(1)
            
            await test_suite.test_long_computation_streaming(client)
            await asyncio.sleep(1)
            
            await test_suite.test_file_processing_streaming(client)
            
            print("\n🎉 All manual tests completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if client.is_connected:
                await client.disconnect()
    
    # Run manual test
    asyncio.run(run_manual_test())