# -*- coding: utf-8 -*-
"""Test MCP integration with ToolService."""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src"))

from aether_frame.tools.service import ToolService


async def test_mcp_toolservice_integration():
    """Test complete MCP integration with ToolService."""
    print("🧪 Testing MCP ToolService Integration")
    print("=" * 50)
    print("⚠️ Make sure real_streaming_server.py is running on port 8002!")
    print()
    
    # Create ToolService with MCP configuration
    config = {
        "enable_mcp": True,
        "mcp_servers": [
            {
                "name": "test_streaming_server",
                "endpoint": "http://localhost:8002/mcp",
                "timeout": 30
            }
        ]
    }
    
    tool_service = ToolService()
    
    try:
        # Initialize ToolService (this should load MCP tools)
        print("🔧 Initializing ToolService with MCP configuration...")
        await tool_service.initialize(config)
        print("✅ ToolService initialized successfully")
        print()
        
        # List all tools
        print("📋 Available tools:")
        tools = await tool_service.list_tools()
        for tool_name in tools:
            # Access tool directly from internal _tools dict for inspection
            tool = tool_service._tools.get(tool_name)
            if tool:
                # Safely check for streaming support
                supports_streaming = getattr(tool, 'supports_streaming', False)
                supports_streaming_icon = "🌊" if supports_streaming else "📄"
                description = getattr(tool, 'tool_description', getattr(tool, 'description', 'No description'))
                tool_type = type(tool).__name__
                print(f"  {supports_streaming_icon} {tool_name} ({tool_type}): {description}")
            else:
                print(f"  ❓ {tool_name}: Tool not found in registry")
        
        print(f"\n📊 Total tools loaded: {len(tools)}")
        
        # Find MCP tools
        mcp_tools = [name for name in tools if "test_streaming_server" in name]
        print(f"🔌 MCP tools found: {len(mcp_tools)}")
        
        if not mcp_tools:
            print("❌ No MCP tools found! Check server configuration.")
            return
        
        # Test synchronous tool execution
        print("\n🔧 Testing synchronous tool execution...")
        test_tool_name = mcp_tools[0]  # Use first MCP tool
        print(f"Testing tool: {test_tool_name}")
        
        # Create a test tool request
        from aether_frame.contracts import ToolRequest
        tool_request = ToolRequest(
            tool_name=test_tool_name,
            parameters={"steps": 3}  # Small test
        )
        
        # Execute tool through ToolService
        start_time = asyncio.get_event_loop().time()
        result = await tool_service.execute_tool(tool_request)
        end_time = asyncio.get_event_loop().time()
        
        print(f"📊 Execution result:")
        print(f"   Status: {result.status}")
        print(f"   Duration: {end_time - start_time:.2f}s")
        if result.result_data:
            print(f"   Content: {str(result.result_data)[:100]}...")
        if result.error_message:
            print(f"   Error: {result.error_message}")
        
        # Test streaming tool execution (if the tool supports it)
        tool = tool_service._tools.get(test_tool_name)
        supports_streaming = getattr(tool, 'supports_streaming', False)
        if tool and supports_streaming:
            print("\n🌊 Testing streaming tool execution...")
            
            chunk_count = 0
            start_time = asyncio.get_event_loop().time()
            
            try:
                async for chunk in tool.execute_stream(tool_request):
                    current_time = asyncio.get_event_loop().time()
                    elapsed = current_time - start_time
                    
                    chunk_count += 1
                    chunk_type = chunk.chunk_type
                    is_final = chunk.is_final
                    
                    print(f"   📦 Chunk {chunk_count} [{elapsed:.2f}s]: {chunk_type} - Final: {is_final}")
                    
                    if chunk.content:
                        content_preview = str(chunk.content)[:60]
                        print(f"       Content: {content_preview}...")
                
                total_time = asyncio.get_event_loop().time() - start_time
                print(f"\n📊 Streaming results:")
                print(f"   Total chunks: {chunk_count}")
                print(f"   Total time: {total_time:.2f}s")
                
            except Exception as e:
                print(f"❌ Streaming test failed: {e}")
            
        else:
            print(f"⚠️ Tool {test_tool_name} does not support streaming")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🔌 Integration test completed!")


if __name__ == "__main__":
    asyncio.run(test_mcp_toolservice_integration())