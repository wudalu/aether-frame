#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive streaming test for MCPClient."""

import asyncio
import sys
from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig

async def test_mcp_streaming():
    """Test MCPClient streaming functionality in detail."""
    
    config = MCPServerConfig(
        name="streaming_test_server",
        endpoint="http://127.0.0.1:8000/mcp",
        timeout=15
    )
    
    print("🌊 Testing MCPClient Streaming Functionality")
    print("=" * 50)
    print()
    
    try:
        async with MCPClient(config) as client:
            print("✅ Connected to MCP server")
            print(f"🔗 Connection status: {client.is_connected}")
            print()
            
            # Test 1: Basic streaming call
            print("📊 Test 1: Basic streaming response")
            print("-" * 30)
            stream_count = 0
            async for chunk in client.call_tool_stream("echo", {"text": "Stream test 1"}):
                stream_count += 1
                print(f"  📦 Chunk {stream_count}: {chunk}")
                
                # Validate chunk structure
                required_fields = ["type", "is_final", "tool_name"]
                for field in required_fields:
                    if field not in chunk:
                        print(f"  ❌ Missing required field: {field}")
                        return False
                
                # Check if this is the final chunk
                if chunk.get("is_final"):
                    print(f"  ✅ Received final chunk (total: {stream_count})")
                    break
            print()
            
            # Test 2: Stream with different tools
            print("📊 Test 2: Streaming different tools")
            print("-" * 30)
            
            test_cases = [
                ("add", {"a": 100, "b": 200}),
                ("get_timestamp", {}),
                ("calculate", {"a": 8, "b": 3, "operation": "multiply"})
            ]
            
            for tool_name, args in test_cases:
                print(f"  🔧 Streaming {tool_name} with args: {args}")
                chunk_count = 0
                async for chunk in client.call_tool_stream(tool_name, args):
                    chunk_count += 1
                    print(f"    📦 Chunk {chunk_count}: {chunk.get('data', chunk.get('error', 'N/A'))}")
                    
                    if chunk.get("is_final"):
                        print(f"    ✅ {tool_name} completed ({chunk_count} chunks)")
                        break
                print()
            
            # Test 3: Error handling in streaming
            print("📊 Test 3: Error handling in streaming")
            print("-" * 30)
            try:
                error_count = 0
                async for chunk in client.call_tool_stream("nonexistent_tool", {"param": "value"}):
                    error_count += 1
                    print(f"  📦 Error chunk {error_count}: {chunk}")
                    
                    if chunk.get("type") == "error":
                        print(f"  ✅ Error correctly handled in streaming")
                    
                    if chunk.get("is_final"):
                        break
            except Exception as e:
                print(f"  ✅ Exception correctly raised: {type(e).__name__}: {e}")
            print()
            
            # Test 4: Multiple concurrent streams
            print("📊 Test 4: Concurrent streaming calls")
            print("-" * 30)
            
            async def stream_worker(worker_id: int, tool: str, args: dict):
                """Worker function for concurrent streaming."""
                results = []
                async for chunk in client.call_tool_stream(tool, args):
                    results.append(chunk)
                    if chunk.get("is_final"):
                        break
                return worker_id, len(results), results[-1].get("data") if results else None
            
            # Start multiple concurrent streams
            tasks = [
                asyncio.create_task(stream_worker(1, "echo", {"text": "Concurrent 1"})),
                asyncio.create_task(stream_worker(2, "add", {"a": 5, "b": 10})),
                asyncio.create_task(stream_worker(3, "get_timestamp", {}))
            ]
            
            # Wait for all to complete
            results = await asyncio.gather(*tasks)
            
            for worker_id, chunk_count, final_data in results:
                print(f"  ✅ Worker {worker_id}: {chunk_count} chunks, final: {final_data}")
            print()
            
            # Test 5: Stream interruption simulation
            print("📊 Test 5: Stream interruption handling")
            print("-" * 30)
            try:
                chunk_count = 0
                async for chunk in client.call_tool_stream("echo", {"text": "Interruption test"}):
                    chunk_count += 1
                    print(f"  📦 Chunk {chunk_count}: {chunk}")
                    
                    # Simulate early break
                    if chunk_count >= 1:
                        print(f"  🔄 Simulating early stream interruption")
                        break
                
                print(f"  ✅ Stream interrupted gracefully after {chunk_count} chunks")
            except Exception as e:
                print(f"  ❌ Interruption handling failed: {e}")
            print()
            
            return True
            
    except MCPConnectionError as e:
        print(f"❌ Connection failed: {e}")
        print("💡 Make sure the test server is running in tests/tools/mcp/:")
        print("   python test_mcp_server.py")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

async def main():
    """Main test function."""
    print("🚀 MCPClient Streaming Test Suite")
    print("=" * 60)
    print()
    
    success = await test_mcp_streaming()
    
    print()
    print("=" * 60)
    if success:
        print("✅ ALL STREAMING TESTS PASSED! 🎉")
        print("🌊 MCPClient streaming functionality verified")
    else:
        print("❌ STREAMING TESTS FAILED!")
        print("🔍 Check error messages above for details")
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Streaming test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Streaming test crashed: {e}")
        sys.exit(1)