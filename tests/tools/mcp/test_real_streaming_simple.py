# -*- coding: utf-8 -*-
"""Simple test to verify real streaming works end-to-end."""

import asyncio
import sys
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src"))

from aether_frame.tools.mcp.config import MCPServerConfig
from aether_frame.tools.mcp.client import MCPClient


async def test_basic_streaming():
    """Test basic streaming functionality."""
    
    config = MCPServerConfig(
        name="real-streaming-test",
        endpoint="http://localhost:8002/mcp",
        timeout=30
    )
    
    client = MCPClient(config)
    
    try:
        print("🔗 Connecting to streaming server...")
        await client.connect()
        print("✅ Connected successfully!")
        
        # Test tool discovery
        print("\n🔍 Discovering tools...")
        tools = await client.discover_tools()
        print(f"✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        
        # Test real streaming
        print("\n🌊 Testing real streaming...")
        tool_name = "real_time_data_stream"
        arguments = {"duration": 3}
        
        chunk_count = 0
        start_time = time.time()
        
        async for chunk in client.call_tool_stream(tool_name, arguments):
            chunk_count += 1
            elapsed = time.time() - start_time
            
            chunk_type = chunk.get('type', 'unknown')
            content = chunk.get('content', '')
            
            print(f"[{elapsed:.2f}s] Chunk {chunk_count}: {chunk_type}")
            if content:
                print(f"  Content: {content[:60]}...")
        
        print(f"\n✅ Streaming completed! Received {chunk_count} chunks")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client.is_connected:
            await client.disconnect()
            print("🔌 Disconnected from server")


if __name__ == "__main__":
    print("🧪 Testing Real Streaming Implementation")
    print("=" * 40)
    print("⚠️  Make sure real_streaming_server.py is running on port 8002!")
    print()
    
    asyncio.run(test_basic_streaming())