# -*- coding: utf-8 -*-
"""Test the new notification-based MCP streaming implementation."""
import asyncio
import sys
import time
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src"))

from aether_frame.tools.mcp.client import MCPClient
from aether_frame.tools.mcp.config import MCPServerConfig


async def test_notification_streaming():
    """Test real notification-based streaming."""
    print("🧪 Testing Notification-Based MCP Streaming")
    print("=" * 50)
    print("⚠️ Make sure real_streaming_server.py is running on port 8002!")
    print()
    
    # Configure client for the streaming server
    config = MCPServerConfig(
        name="notification-streaming-test",
        endpoint="http://localhost:8002/mcp",
        timeout=30
    )
    
    client = MCPClient(config)
    
    try:
        # Connect with notification handler
        print("🔌 Connecting to MCP server with notification handler...")
        await client.connect()
        print(f"✅ Connected: {client.is_connected}")
        print(f"📡 Supports streaming: {client.supports_streaming}")
        print()
        
        # Discover tools
        print("🔍 Discovering tools...")
        tools = await client.discover_tools()
        print(f"📋 Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        print()
        
        if not tools:
            print("❌ No tools found! Check server configuration.")
            return
        
        # Test real streaming call
        print("🌊 Testing REAL streaming call...")
        print("⏱️ Monitoring for real-time progress notifications...")
        start_time = time.time()
        
        events_received = []
        
        # Use a tool that should generate progress events
        async for event in client.call_tool_stream("long_computation", {"steps": 5}):
            current_time = time.time()
            elapsed = current_time - start_time
            
            events_received.append(event)
            event_type = event.get("type", "unknown")
            
            if event_type == "stream_start":
                print(f"🚀 [{elapsed:.2f}s] Stream started for {event.get('tool_name')}")
                print(f"    Progress token: {event.get('progress_token')}")
                
            elif event_type == "progress_update":
                progress = event.get("progress", 0)
                total = event.get("total", 1)
                message = event.get("message", "")
                print(f"📊 [{elapsed:.2f}s] Progress: {progress}/{total} - {message}")
                
            elif event_type == "complete_result":
                print(f"✅ [{elapsed:.2f}s] Final result received")
                print(f"    Content: {str(event.get('content', ''))[:100]}...")
                print(f"    Total time: {event.get('total_time', 0):.2f}s")
                
            elif event_type == "error":
                print(f"❌ [{elapsed:.2f}s] Error: {event.get('error')}")
        
        total_time = time.time() - start_time
        print()
        print("📊 Streaming Test Results:")
        print(f"   Total events: {len(events_received)}")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Event types: {set(e.get('type') for e in events_received)}")
        
        # Analyze if we got real streaming
        progress_events = [e for e in events_received if e.get("type") == "progress_update"]
        
        if progress_events:
            print(f"✅ Real streaming DETECTED! Received {len(progress_events)} progress events")
            for i, event in enumerate(progress_events):
                event_time = event.get("timestamp", 0)
                relative_time = event_time - start_time if start_time else 0
                print(f"    Event {i+1}: {relative_time:.2f}s - {event.get('message', '')}")
        else:
            print("⚠️ No progress events received - this might be simulated streaming")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.disconnect()
        print("🔌 Disconnected from server")


if __name__ == "__main__":
    asyncio.run(test_notification_streaming())