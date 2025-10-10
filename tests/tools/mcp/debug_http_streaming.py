# -*- coding: utf-8 -*-
"""HTTP-level investigation of MCP streaming behavior."""

import asyncio
import aiohttp
import json
import time


async def test_raw_http_streaming():
    """Test direct HTTP call to see if server streams."""
    
    print("🌐 Raw HTTP Streaming Investigation")
    print("=" * 40)
    
    endpoint = "http://localhost:8002/mcp"
    
    # MCP tool call request
    mcp_request = {
        "jsonrpc": "2.0",
        "id": "test",
        "method": "tools/call",
        "params": {
            "name": "real_time_data_stream",
            "arguments": {"duration": 3}
        }
    }
    
    print("📡 Testing with Accept: text/event-stream")
    
    start_time = time.time()
    chunk_count = 0
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            endpoint,
            json=mcp_request,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream, application/json'
            }
        ) as response:
            
            print(f"Status: {response.status}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            
            if 'text/event-stream' in response.headers.get('content-type', ''):
                print("✅ Server returned SSE stream!")
                
                async for chunk in response.content:
                    chunk_count += 1
                    elapsed = time.time() - start_time
                    chunk_text = chunk.decode('utf-8', errors='ignore')
                    
                    print(f"[{elapsed:.3f}s] Chunk {chunk_count}: {len(chunk_text)} bytes")
                    if chunk_text.strip():
                        print(f"   Content: {chunk_text[:50]}...")
                    
                    # Check for SSE format
                    if chunk_text.startswith('data:'):
                        print("   📡 SSE formatted data!")
                        
            else:
                print("❌ Server returned regular JSON")
                result = await response.text()
                elapsed = time.time() - start_time
                print(f"[{elapsed:.3f}s] Got complete result: {len(result)} chars")


async def test_mcp_initialization():
    """Test MCP initialization to understand the protocol."""
    
    print("\n🔌 MCP Protocol Investigation")
    print("=" * 35)
    
    endpoint = "http://localhost:8002/mcp"
    
    init_request = {
        "jsonrpc": "2.0",
        "id": "init",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "debug-client", "version": "1.0.0"}
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            endpoint,
            json=init_request,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream, application/json'
            }
        ) as response:
            
            print(f"Initialize Status: {response.status}")
            print(f"Initialize Content-Type: {response.headers.get('content-type')}")
            
            result = await response.text()
            print(f"Initialize Response: {result[:100]}...")


async def main():
    """Run HTTP-level investigation."""
    await test_mcp_initialization()
    await test_raw_http_streaming()


if __name__ == "__main__":
    asyncio.run(main())