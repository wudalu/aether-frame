#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script to verify MCPClient works with real MCP server."""

import asyncio
import sys
from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig

async def test_mcp_client():
    """Test MCPClient with real FastMCP server."""
    
    # Configure connection to our test server
    config = MCPServerConfig(
        name="test_server",
        endpoint="http://127.0.0.1:8000/mcp",  # FastMCP default endpoint
        timeout=10
    )
    
    print("🧪 Testing MCPClient with real FastMCP server")
    print(f"📡 Connecting to: {config.endpoint}")
    print(f"⏰ Timeout: {config.timeout}s")
    print()
    
    try:
        # Test connection and basic functionality
        async with MCPClient(config) as client:
            print("✅ Connection established!")
            print(f"🔗 Connected: {client.is_connected}")
            print()
            
            # Test 1: Discover tools
            print("🔍 Step 1: Discovering available tools...")
            try:
                tools = await client.discover_tools()
                print(f"✅ Found {len(tools)} tools:")
                for tool in tools:
                    print(f"   - {tool.name}: {tool.description}")
                print()
            except Exception as e:
                print(f"❌ Tool discovery failed: {e}")
                return False
            
            # Test 2: Call echo tool
            print("📢 Step 2: Testing echo tool...")
            try:
                result = await client.call_tool("echo", {"text": "Hello from MCPClient!"})
                print(f"✅ Echo result: {result}")
                print()
            except Exception as e:
                print(f"❌ Echo tool failed: {e}")
            
            # Test 3: Call add tool
            print("➕ Step 3: Testing add tool...")
            try:
                result = await client.call_tool("add", {"a": 15, "b": 27})
                print(f"✅ Add result: 15 + 27 = {result}")
                print()
            except Exception as e:
                print(f"❌ Add tool failed: {e}")
            
            # Test 4: Call timestamp tool
            print("⏰ Step 4: Testing timestamp tool...")
            try:
                result = await client.call_tool("get_timestamp", {})
                print(f"✅ Timestamp: {result}")
                print()
            except Exception as e:
                print(f"❌ Timestamp tool failed: {e}")
            
            # Test 5: Call calculate tool
            print("🧮 Step 5: Testing calculate tool...")
            try:
                result = await client.call_tool("calculate", {
                    "a": 10, 
                    "b": 5, 
                    "operation": "multiply"
                })
                print(f"✅ Calculate result: 10 * 5 = {result}")
                print()
            except Exception as e:
                print(f"❌ Calculate tool failed: {e}")
            
            # Test 6: Test streaming (placeholder)
            print("🌊 Step 6: Testing streaming functionality...")
            try:
                async for chunk in client.call_tool_stream("echo", {"text": "Streaming test"}):
                    print(f"✅ Stream chunk: {chunk}")
                print()
            except Exception as e:
                print(f"❌ Streaming failed: {e}")
            
            # Test ping
            print("🏓 Step 7: Testing ping...")
            try:
                ping_result = await client.ping()
                print(f"✅ Ping result: {ping_result}")
                print()
            except Exception as e:
                print(f"❌ Ping failed: {e}")
            
        print("🎉 All tests completed!")
        return True
        
    except MCPConnectionError as e:
        print(f"❌ Connection failed: {e}")
        print("💡 Make sure the test server is running: python test_mcp_server.py")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

async def main():
    """Main test function."""
    print("=" * 60)
    print("🚀 MCPClient Integration Test")
    print("=" * 60)
    print()
    
    success = await test_mcp_client()
    
    print()
    print("=" * 60)
    if success:
        print("✅ ALL TESTS PASSED! MCPClient works with real MCP server! 🎉")
    else:
        print("❌ TESTS FAILED! Check the error messages above.")
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test crashed: {e}")
        sys.exit(1)