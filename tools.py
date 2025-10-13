#!/usr/bin/env python3
"""
Tool management script for Aether Frame.
Provides MCP server management and tool testing capabilities.
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
import time


class ToolManager:
    """Tool management utilities for Aether Frame."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.src_dir = self.project_root / "src"
        # Add src to Python path for imports
        sys.path.insert(0, str(self.src_dir))
        
    async def list_tools(self, filter_pattern: Optional[str] = None) -> int:
        """List all available tools."""
        try:
            from aether_frame.tools.service import ToolService
            from aether_frame.config import Config
            
            print("🔧 Discovering available tools...")
            
            # Initialize tool service
            config = Config()
            tool_service = ToolService(config)
            await tool_service.initialize()
            
            # Get all tools
            tools = await tool_service.list_tools()
            
            if filter_pattern:
                tools = [tool for tool in tools if filter_pattern.lower() in tool.lower()]
                print(f"\n📋 Available tools (filtered by '{filter_pattern}'):")
            else:
                print(f"\n📋 Available tools ({len(tools)} total):")
            
            if not tools:
                print("   No tools found.")
                return 0
                
            # Group by namespace
            grouped_tools = {}
            for tool_name in sorted(tools):
                if '.' in tool_name:
                    namespace, name = tool_name.split('.', 1)
                    if namespace not in grouped_tools:
                        grouped_tools[namespace] = []
                    grouped_tools[namespace].append(name)
                else:
                    if 'builtin' not in grouped_tools:
                        grouped_tools['builtin'] = []
                    grouped_tools['builtin'].append(tool_name)
            
            # Display grouped tools
            for namespace in sorted(grouped_tools.keys()):
                print(f"\n  {namespace}:")
                for tool_name in sorted(grouped_tools[namespace]):
                    full_name = f"{namespace}.{tool_name}" if namespace != 'builtin' else tool_name
                    print(f"    • {tool_name} ({full_name})")
            
            print(f"\n✅ Found {len(tools)} tools across {len(grouped_tools)} namespaces")
            return 0
            
        except Exception as e:
            print(f"❌ Error listing tools: {e}")
            return 1
    
    async def test_tool(self, tool_name: str, params: Optional[str] = None) -> int:
        """Test a specific tool."""
        try:
            from aether_frame.tools.service import ToolService
            from aether_frame.tools.contracts import ToolRequest
            from aether_frame.config import Config
            
            print(f"🧪 Testing tool: {tool_name}")
            
            # Parse parameters
            parameters = {}
            if params:
                try:
                    parameters = json.loads(params)
                    print(f"📥 Parameters: {json.dumps(parameters, indent=2)}")
                except json.JSONDecodeError:
                    print(f"❌ Invalid JSON parameters: {params}")
                    return 1
            
            # Initialize tool service
            config = Config()
            tool_service = ToolService(config)
            await tool_service.initialize()
            
            # Check if tool exists
            available_tools = await tool_service.list_tools()
            if tool_name not in available_tools:
                print(f"❌ Tool '{tool_name}' not found.")
                print(f"Available tools: {', '.join(sorted(available_tools))}")
                return 1
            
            # Create tool request
            tool_request = ToolRequest(
                tool_name=tool_name,
                parameters=parameters,
                session_id=f"test_session_{int(time.time())}"
            )
            
            print(f"⚡ Executing tool...")
            start_time = time.time()
            
            # Execute tool
            result = await tool_service.execute_tool(tool_request)
            
            execution_time = time.time() - start_time
            
            # Display results
            print(f"\n📊 Execution Results:")
            print(f"   ⏱️  Duration: {execution_time:.3f}s")
            print(f"   ✅ Success: {result.success}")
            
            if result.success:
                print(f"   📤 Result: {json.dumps(result.result_data, indent=2)}")
            else:
                print(f"   ❌ Error: {result.error_message}")
                if result.error_details:
                    print(f"   🔍 Details: {json.dumps(result.error_details, indent=2)}")
            
            return 0 if result.success else 1
            
        except Exception as e:
            print(f"❌ Error testing tool: {e}")
            return 1
    
    async def test_streaming(self, tool_name: str, params: Optional[str] = None) -> int:
        """Test streaming functionality of a tool."""
        try:
            from aether_frame.tools.service import ToolService
            from aether_frame.tools.contracts import ToolRequest
            from aether_frame.config import Config
            
            print(f"🌊 Testing streaming for tool: {tool_name}")
            
            # Parse parameters
            parameters = {}
            if params:
                try:
                    parameters = json.loads(params)
                    print(f"📥 Parameters: {json.dumps(parameters, indent=2)}")
                except json.JSONDecodeError:
                    print(f"❌ Invalid JSON parameters: {params}")
                    return 1
            
            # Initialize tool service
            config = Config()
            tool_service = ToolService(config)
            await tool_service.initialize()
            
            # Get tool instance
            tool = tool_service._tools.get(tool_name)
            if not tool:
                print(f"❌ Tool '{tool_name}' not found.")
                return 1
            
            if not tool.supports_streaming:
                print(f"⚠️  Tool '{tool_name}' does not support streaming.")
                print("Testing synchronous execution instead...")
                return await self.test_tool(tool_name, params)
            
            # Create tool request
            tool_request = ToolRequest(
                tool_name=tool_name,
                parameters=parameters,
                session_id=f"stream_test_{int(time.time())}"
            )
            
            print(f"🌊 Starting streaming execution...")
            start_time = time.time()
            chunk_count = 0
            
            # Execute streaming
            async for chunk in tool_service.execute_tool_stream(tool_request):
                chunk_count += 1
                elapsed = time.time() - start_time
                
                print(f"📦 Chunk {chunk_count} ({elapsed:.3f}s):")
                print(f"   Type: {chunk.chunk_type}")
                print(f"   Content: {chunk.content[:100]}{'...' if len(chunk.content) > 100 else ''}")
                print(f"   Final: {chunk.is_final}")
                
                if chunk.metadata:
                    print(f"   Metadata: {json.dumps(chunk.metadata, indent=4)}")
                
                if chunk.is_final:
                    break
            
            total_time = time.time() - start_time
            print(f"\n✅ Streaming completed:")
            print(f"   📦 Total chunks: {chunk_count}")
            print(f"   ⏱️  Total time: {total_time:.3f}s")
            print(f"   📊 Avg time/chunk: {total_time/chunk_count:.3f}s")
            
            return 0
            
        except Exception as e:
            print(f"❌ Error testing streaming: {e}")
            return 1
    
    async def test_mcp_server(self, server_name: str) -> int:
        """Test connectivity to a specific MCP server."""
        try:
            from aether_frame.tools.mcp.client import MCPClient
            from aether_frame.tools.mcp.config import MCPServerConfig
            from aether_frame.config import Config
            
            print(f"🔌 Testing MCP server: {server_name}")
            
            # Load configuration
            config = Config()
            mcp_servers = config.get("tool_service", {}).get("mcp_servers", [])
            
            # Find server config
            server_config = None
            for server in mcp_servers:
                if server.get("name") == server_name:
                    server_config = server
                    break
            
            if not server_config:
                print(f"❌ MCP server '{server_name}' not found in configuration.")
                print(f"Available servers: {[s.get('name') for s in mcp_servers]}")
                return 1
            
            print(f"📋 Server config: {json.dumps(server_config, indent=2)}")
            
            # Create MCP client
            mcp_config = MCPServerConfig(**server_config)
            client = MCPClient(mcp_config)
            
            print(f"🔗 Connecting to {mcp_config.endpoint}...")
            start_time = time.time()
            
            try:
                await client.connect()
                connect_time = time.time() - start_time
                print(f"✅ Connected successfully ({connect_time:.3f}s)")
                
                # Test tool discovery
                print(f"🔍 Discovering tools...")
                discovery_start = time.time()
                tools = await client.discover_tools()
                discovery_time = time.time() - discovery_start
                
                print(f"✅ Tool discovery completed ({discovery_time:.3f}s)")
                print(f"📋 Found {len(tools)} tools:")
                
                for tool in tools:
                    print(f"   • {tool.name}: {tool.description}")
                
                await client.disconnect()
                print(f"🔌 Disconnected successfully")
                
                return 0
                
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                return 1
            
        except Exception as e:
            print(f"❌ Error testing MCP server: {e}")
            return 1
    
    async def debug_mcp_discovery(self, server_name: str) -> int:
        """Debug MCP tool discovery process."""
        try:
            from aether_frame.tools.mcp.client import MCPClient
            from aether_frame.tools.mcp.config import MCPServerConfig
            from aether_frame.config import Config
            
            print(f"🐛 Debugging MCP discovery for: {server_name}")
            
            # Load configuration
            config = Config()
            mcp_servers = config.get("tool_service", {}).get("mcp_servers", [])
            
            # Find server config
            server_config = None
            for server in mcp_servers:
                if server.get("name") == server_name:
                    server_config = server
                    break
            
            if not server_config:
                print(f"❌ MCP server '{server_name}' not found in configuration.")
                return 1
            
            # Create MCP client with debug mode
            mcp_config = MCPServerConfig(**server_config)
            client = MCPClient(mcp_config)
            
            print(f"🔗 Connecting with debug information...")
            
            try:
                await client.connect()
                print(f"✅ Connection established")
                
                # Debug tool discovery
                print(f"\n🔍 Starting tool discovery debug...")
                
                # Get raw server capabilities
                print(f"📋 Checking server capabilities...")
                
                # Discover tools with detailed output
                tools = await client.discover_tools()
                
                print(f"\n📊 Discovery Results:")
                print(f"   Total tools found: {len(tools)}")
                
                for i, tool in enumerate(tools, 1):
                    print(f"\n   Tool {i}: {tool.name}")
                    print(f"      Description: {tool.description}")
                    print(f"      Parameters: {json.dumps(tool.parameters_schema, indent=6)}")
                
                await client.disconnect()
                return 0
                
            except Exception as e:
                print(f"❌ Debug session failed: {e}")
                import traceback
                traceback.print_exc()
                return 1
            
        except Exception as e:
            print(f"❌ Error in debug session: {e}")
            return 1
    
    def help(self):
        """Show available commands."""
        print("🔧 Tool Management Commands:")
        print("  list-tools [filter]           List all available tools")
        print("  test-tool <tool> [params]     Test a specific tool")
        print("  test-streaming <tool> [params] Test streaming functionality")
        print("  test-mcp-server <server>      Test MCP server connectivity")
        print("  debug-mcp-discovery <server>  Debug MCP tool discovery")
        print("")
        print("Examples:")
        print('  python tools.py list-tools')
        print('  python tools.py list-tools mcp')
        print('  python tools.py test-tool builtin.echo \'{"message": "hello"}\'')
        print('  python tools.py test-streaming mcp_server.search \'{"query": "test"}\'')
        print('  python tools.py test-mcp-server local_server')
        print('  python tools.py debug-mcp-discovery research_tools')


async def async_main():
    """Async main entry point."""
    parser = argparse.ArgumentParser(
        description="Tool management for Aether Frame",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        default="help",
        help="Command to run"
    )
    
    parser.add_argument(
        "target",
        nargs="?",
        help="Target (tool name, server name, or filter)"
    )
    
    parser.add_argument(
        "params",
        nargs="?",
        help="Parameters (JSON string for tool testing)"
    )
    
    args = parser.parse_args()
    
    tool_manager = ToolManager()
    
    try:
        if args.command == "help":
            tool_manager.help()
            return 0
        elif args.command == "list-tools":
            return await tool_manager.list_tools(args.target)
        elif args.command == "test-tool":
            if not args.target:
                print("❌ Tool name required for test-tool command")
                return 1
            return await tool_manager.test_tool(args.target, args.params)
        elif args.command == "test-streaming":
            if not args.target:
                print("❌ Tool name required for test-streaming command")
                return 1
            return await tool_manager.test_streaming(args.target, args.params)
        elif args.command == "test-mcp-server":
            if not args.target:
                print("❌ Server name required for test-mcp-server command")
                return 1
            return await tool_manager.test_mcp_server(args.target)
        elif args.command == "debug-mcp-discovery":
            if not args.target:
                print("❌ Server name required for debug-mcp-discovery command")
                return 1
            return await tool_manager.debug_mcp_discovery(args.target)
        else:
            print(f"❌ Unknown command: {args.command}")
            tool_manager.help()
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main entry point."""
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())