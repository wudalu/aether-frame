# -*- coding: utf-8 -*-
"""Debug version to investigate Streamable HTTP transport streaming behavior."""

import asyncio
import time
from typing import Any, Dict

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src"))

from aether_frame.tools.mcp.config import MCPServerConfig
from aether_frame.tools.mcp.client import MCPClient


class StreamingInvestigator:
    """Investigate if transport layer actually does streaming."""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.client = MCPClient(config)
    
    async def test_transport_streaming(self):
        """Test if transport layer handles streaming."""
        print("🔍 Investigating Streamable HTTP Transport Streaming Behavior")
        print("=" * 60)
        
        await self.client.connect()
        
        # Test 1: Monitor call timing
        print("\n📊 Test 1: Timing Analysis")
        print("-" * 30)
        
        tool_name = "real_time_data_stream"
        arguments = {"duration": 3}
        
        start_time = time.time()
        print(f"[{0:.3f}s] Starting tool call...")
        
        # Monitor if we get intermediate data
        call_start = time.time()
        result = await self.client.call_tool(tool_name, arguments)
        call_end = time.time()
        
        print(f"[{call_end - start_time:.3f}s] Tool call completed")
        print(f"Call duration: {call_end - call_start:.3f}s")
        print(f"Result type: {type(result)}")
        print(f"Result length: {len(str(result))} characters")
        
        # Test 2: Check if we can intercept streaming
        print("\n🔍 Test 2: Direct Transport Investigation")
        print("-" * 40)
        
        # Access internal session for investigation
        session = self.client._session
        print(f"Session type: {type(session)}")
        print(f"Session streams: {hasattr(session, 'read_stream')}")
        
        # Test 3: Multiple rapid calls
        print("\n⚡ Test 3: Rapid Call Sequence")
        print("-" * 30)
        
        for i in range(3):
            start = time.time()
            result = await self.client.call_tool("real_time_data_stream", {"duration": 1})
            end = time.time()
            print(f"Call {i+1}: {end - start:.3f}s - Got {len(str(result))} chars")
        
        await self.client.disconnect()
    
    async def test_streaming_expectations(self):
        """Test what we expect from real streaming."""
        print("\n🌊 Expected Streaming Behavior Analysis")
        print("=" * 40)
        
        await self.client.connect()
        
        # If streaming worked, we should see:
        # 1. Partial results coming in over time
        # 2. Progressive data availability
        # 3. Non-blocking incremental updates
        
        tool_name = "real_time_data_stream"
        arguments = {"duration": 3}
        
        print("Starting long-running tool call...")
        print("(In real streaming, we should see intermediate results)")
        
        start_time = time.time()
        
        # This should take ~3 seconds if streaming
        # But we should get data progressively
        result = await self.client.call_tool(tool_name, arguments)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\nActual behavior:")
        print(f"- Total time: {duration:.3f}s")
        print(f"- Result received: {'incrementally' if duration < 1 else 'all at once'}")
        print(f"- Result size: {len(str(result))} chars")
        
        # Parse the result to see server-side timing
        result_lines = str(result).split('\n')
        server_times = []
        for line in result_lines:
            if 'Real-time data point' in line and 's]' in line:
                # Extract server timestamp
                import re
                match = re.search(r'\[(\d+\.\d+)s\]', line)
                if match:
                    server_times.append(float(match.group(1)))
        
        if server_times:
            print(f"\nServer-side timing analysis:")
            print(f"- Server processing times: {server_times}")
            print(f"- Server total time: {max(server_times):.1f}s")
            print(f"- Client received all data in: {duration:.3f}s")
            
            if duration < max(server_times) + 0.5:
                print("✅ Transport might be doing streaming (fast delivery)")
            else:
                print("❌ Transport likely NOT streaming (slow delivery)")
        
        await self.client.disconnect()


async def main():
    """Run streaming investigation."""
    config = MCPServerConfig(
        name="streaming-investigation",
        endpoint="http://localhost:8002/mcp",
        timeout=30
    )
    
    investigator = StreamingInvestigator(config)
    
    try:
        await investigator.test_transport_streaming()
        await investigator.test_streaming_expectations()
    except Exception as e:
        print(f"❌ Investigation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🕵️ MCP Streamable HTTP Transport Investigation")
    print("⚠️  Make sure the streaming server is running on port 8002!")
    print()
    
    asyncio.run(main())