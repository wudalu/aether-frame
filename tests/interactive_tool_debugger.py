#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Interactive Tool Debugger for Aether Frame

This script provides a complete debugging environment for tool calls,
supporting various scenarios with interactive input and detailed logging.

Usage:
    python tests/interactive_tool_debugger.py
"""

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aether_frame.tools.service import ToolService
from aether_frame.tools.resolver import ToolResolver, ToolNotFoundError
from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig
from aether_frame.tools.mcp.tool_wrapper import MCPTool
from aether_frame.contracts import ToolRequest, ToolResult
from aether_frame.contracts.responses import ToolStatus
try:
    from aether_frame.contracts.contexts import UniversalTool, UserContext, UserPermissions
except ImportError:
    # Fallback if contracts don't have these yet
    UniversalTool = UserContext = UserPermissions = None


@dataclass
class DebugSession:
    """Debug session information"""
    session_id: str
    start_time: datetime
    scenario: str
    logs: List[Dict[str, Any]]
    
    def add_log(self, level: str, message: str, data: Optional[Dict] = None):
        """Add a log entry"""
        self.logs.append({
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "data": data or {}
        })


class InteractiveToolDebugger:
    """Comprehensive tool debugging interface"""
    
    def __init__(self):
        self.session: Optional[DebugSession] = None
        self.tool_service: Optional[ToolService] = None
        self.tool_resolver: Optional[ToolResolver] = None
        self.mcp_clients: Dict[str, MCPClient] = {}
        self.test_scenarios: Dict[str, dict] = self._load_test_scenarios()
        self.setup_logging()
    
    def _load_test_scenarios(self) -> Dict[str, dict]:
        """Load predefined test scenarios"""
        return {
            "echo_basic": {
                "name": "echo",
                "params": {"text": "Hello from debugger"},
                "description": "Basic echo tool test"
            },
            "echo_streaming": {
                "name": "echo", 
                "params": {"text": "Streaming test message", "delay": 1},
                "description": "Echo tool with streaming support",
                "streaming": True
            },
            "timestamp_test": {
                "name": "timestamp",
                "params": {},
                "description": "Timestamp tool test"
            },
            "mcp_search": {
                "name": "search",
                "params": {"query": "test query", "limit": 5},
                "description": "MCP search tool test"
            },
            "permission_test": {
                "name": "restricted_tool",
                "params": {},
                "description": "Tool requiring special permissions",
                "expect_error": True
            }
        }
    
    def setup_logging(self):
        """Configure detailed logging"""
        log_dir = Path(__file__).parent / "debug_logs"
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"tool_debug_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger("ToolDebugger")
        self.logger.info(f"Debug session started - Log file: {log_file}")
    
    def start_session(self, scenario: str) -> str:
        """Start a new debug session"""
        session_id = str(uuid4())[:8]
        self.session = DebugSession(
            session_id=session_id,
            start_time=datetime.now(),
            scenario=scenario,
            logs=[]
        )
        
        self.session.add_log("INFO", f"Debug session started: {scenario}")
        self.logger.info(f"Session {session_id} started for scenario: {scenario}")
        return session_id
    
    def save_session(self):
        """Save session logs to file"""
        if not self.session:
            return
        
        log_dir = Path(__file__).parent / "debug_logs" 
        log_dir.mkdir(exist_ok=True)
        
        session_file = log_dir / f"session_{self.session.session_id}_{self.session.scenario}.json"
        
        with open(session_file, 'w') as f:
            json.dump(asdict(self.session), f, indent=2, default=str)
        
        self.logger.info(f"Session saved to: {session_file}")
        print(f"\n💾 Session logs saved to: {session_file}")
    
    async def initialize_tool_service(self, config: Optional[Dict] = None):
        """Initialize ToolService with optional configuration"""
        try:
            self.session.add_log("INFO", "Initializing ToolService")
            
            # Default configuration for ToolService.initialize()
            default_config = {
                "enable_mcp": True,
                "mcp_servers": [
                    {
                        "name": "local_server",
                        "endpoint": "http://localhost:8000/mcp",
                        "timeout": 30
                    }
                ]
            }
            
            final_config = config or default_config
            self.session.add_log("DEBUG", "Using configuration", {"config": final_config})
            
            # Create ToolService instance (no config in constructor)
            self.tool_service = ToolService()
            # Pass config to initialize method
            await self.tool_service.initialize(final_config)
            
            # Get available tools
            available_tools = await self.tool_service.list_tools()
            self.session.add_log("INFO", f"ToolService initialized with {len(available_tools)} tools", 
                               {"tools": available_tools})
            
            self.logger.info(f"ToolService initialized successfully with {len(available_tools)} tools")
            return True
            
        except Exception as e:
            self.session.add_log("ERROR", f"Failed to initialize ToolService: {e}")
            self.logger.error(f"ToolService initialization failed: {e}", exc_info=True)
            return False
    
    async def test_mcp_connection(self, server_config: Dict):
        """Test MCP server connection"""
        try:
            self.session.add_log("INFO", "Testing MCP connection", {"config": server_config})
            
            config = MCPServerConfig(**server_config)
            client = MCPClient(config)
            
            # Test connection
            await client.connect()
            self.session.add_log("INFO", "MCP connection established")
            
            # Discover tools
            tools = await client.discover_tools()
            self.session.add_log("INFO", f"Discovered {len(tools)} MCP tools", 
                               {"tools": [tool.name for tool in tools]})
            
            # Store client for later use
            self.mcp_clients[server_config["name"]] = client
            
            return True, tools
            
        except MCPConnectionError as e:
            error_msg = f"MCP connection failed: {e}"
            self.session.add_log("ERROR", error_msg)
            self.logger.error(error_msg)
            return False, []
        except Exception as e:
            error_msg = f"Unexpected error during MCP connection: {e}"
            self.session.add_log("ERROR", error_msg)
            self.logger.error(error_msg, exc_info=True)
            return False, []
    
    async def debug_tool_execution(self, tool_name: str, parameters: Dict, use_streaming: bool = False):
        """Debug tool execution with detailed logging"""
        try:
            execution_id = str(uuid4())[:8]
            self.session.add_log("INFO", f"Starting tool execution [{execution_id}]", {
                "tool_name": tool_name,
                "parameters": parameters,
                "streaming": use_streaming
            })
            
            # Create tool request
            tool_request = ToolRequest(
                tool_name=tool_name,
                parameters=parameters,
                request_id=execution_id,
                session_id=self.session.session_id
            )
            
            start_time = time.time()
            
            if use_streaming:
                return await self._debug_streaming_execution(tool_request, execution_id)
            else:
                return await self._debug_sync_execution(tool_request, execution_id)
                
        except Exception as e:
            error_msg = f"Tool execution failed: {e}"
            self.session.add_log("ERROR", error_msg)
            self.logger.error(error_msg, exc_info=True)
            return False, None
    
    async def _debug_sync_execution(self, tool_request: ToolRequest, execution_id: str):
        """Debug synchronous tool execution"""
        start_time = time.time()
        
        try:
            self.session.add_log("DEBUG", f"Executing tool synchronously [{execution_id}]")
            
            result = await self.tool_service.execute_tool(tool_request)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            self.session.add_log("INFO", f"Tool execution completed [{execution_id}]", {
                "status": result.status.value,
                "execution_time": f"{execution_time:.3f}s",
                "result_data": str(result.result_data)[:200] if result.result_data else None,
                "error": result.error_message
            })
            
            return True, result
            
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            
            self.session.add_log("ERROR", f"Sync execution failed [{execution_id}]", {
                "execution_time": f"{execution_time:.3f}s",
                "error": str(e)
            })
            raise
    
    async def _debug_streaming_execution(self, tool_request: ToolRequest, execution_id: str):
        """Debug streaming tool execution"""
        start_time = time.time()
        chunks_received = 0
        
        try:
            self.session.add_log("DEBUG", f"Executing tool with streaming [{execution_id}]")
            
            # Check if streaming is supported
            if not hasattr(self.tool_service, 'execute_tool_stream'):
                # Fallback: simulate streaming by executing normally and creating chunks
                self.session.add_log("WARNING", "Tool service doesn't support streaming, simulating...")
                
                result = await self.tool_service.execute_tool(tool_request)
                
                # Simulate streaming chunks
                if result.status == ToolStatus.SUCCESS:
                    chunks_received = 1
                    self.session.add_log("DEBUG", f"Simulated stream chunk [{execution_id}]", {
                        "chunk_number": 1,
                        "simulated": True,
                        "result_data": str(result.result_data)[:100] if result.result_data else None
                    })
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                self.session.add_log("INFO", f"Simulated streaming completed [{execution_id}]", {
                    "total_chunks": chunks_received,
                    "execution_time": f"{execution_time:.3f}s",
                    "simulated": True
                })
                
                return True, chunks_received
            
            # Real streaming execution
            async for chunk in self.tool_service.execute_tool_stream(tool_request):
                chunks_received += 1
                chunk_time = time.time() - start_time
                
                self.session.add_log("DEBUG", f"Stream chunk received [{execution_id}]", {
                    "chunk_number": chunks_received,
                    "chunk_type": chunk.chunk_type.value if hasattr(chunk, 'chunk_type') else "unknown",
                    "elapsed_time": f"{chunk_time:.3f}s",
                    "is_final": getattr(chunk, 'is_final', False),
                    "content_preview": str(getattr(chunk, 'content', ''))[:100]
                })
                
                if getattr(chunk, 'is_final', False):
                    break
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            self.session.add_log("INFO", f"Streaming execution completed [{execution_id}]", {
                "total_chunks": chunks_received,
                "execution_time": f"{execution_time:.3f}s"
            })
            
            return True, chunks_received
            
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            
            self.session.add_log("ERROR", f"Streaming execution failed [{execution_id}]", {
                "chunks_received": chunks_received,
                "execution_time": f"{execution_time:.3f}s",
                "error": str(e)
            })
            raise
    
    async def debug_mcp_direct(self, server_name: str, tool_name: str, arguments: Dict, use_streaming: bool = False):
        """Debug direct MCP tool calls"""
        try:
            if server_name not in self.mcp_clients:
                self.session.add_log("ERROR", f"MCP client not found: {server_name}")
                return False, None
            
            client = self.mcp_clients[server_name]
            execution_id = str(uuid4())[:8]
            
            self.session.add_log("INFO", f"Direct MCP call [{execution_id}]", {
                "server": server_name,
                "tool": tool_name,
                "arguments": arguments,
                "streaming": use_streaming
            })
            
            start_time = time.time()
            
            if use_streaming:
                chunks = []
                async for chunk in client.call_tool_stream(tool_name, arguments):
                    chunks.append(chunk)
                    self.session.add_log("DEBUG", f"MCP stream chunk [{execution_id}]", {
                        "chunk_type": chunk.get("type"),
                        "content_preview": str(chunk.get("content", ""))[:100]
                    })
                
                end_time = time.time()
                self.session.add_log("INFO", f"MCP streaming completed [{execution_id}]", {
                    "total_chunks": len(chunks),
                    "execution_time": f"{end_time - start_time:.3f}s"
                })
                
                return True, chunks
            else:
                result = await client.call_tool(tool_name, arguments)
                end_time = time.time()
                
                self.session.add_log("INFO", f"MCP call completed [{execution_id}]", {
                    "execution_time": f"{end_time - start_time:.3f}s",
                    "result_preview": str(result)[:200]
                })
                
                return True, result
                
        except Exception as e:
            self.session.add_log("ERROR", f"Direct MCP call failed: {e}")
            self.logger.error(f"Direct MCP call failed: {e}", exc_info=True)
            return False, None
    
    def print_session_summary(self):
        """Print a summary of the current session"""
        if not self.session:
            print("No active session")
            return
        
        print(f"\n{'='*60}")
        print(f"DEBUG SESSION SUMMARY")
        print(f"{'='*60}")
        print(f"Session ID: {self.session.session_id}")
        print(f"Scenario: {self.session.scenario}")
        print(f"Duration: {datetime.now() - self.session.start_time}")
        print(f"Total Logs: {len(self.session.logs)}")
        
        # Count log levels
        log_levels = {}
        for log in self.session.logs:
            level = log["level"]
            log_levels[level] = log_levels.get(level, 0) + 1
        
        print(f"Log Distribution: {log_levels}")
        
        # Show recent logs
        print(f"\nRecent Logs:")
        for log in self.session.logs[-5:]:
            timestamp = log["timestamp"].split("T")[1][:8]
            print(f"  [{timestamp}] {log['level']:5} {log['message']}")
        
        print(f"{'='*60}")

    async def interactive_menu(self):
        """Main interactive menu"""
        print(f"\n🛠️  Aether Frame Interactive Tool Debugger")
        print(f"{'='*50}")
        
        while True:
            print(f"\nChoose a debugging scenario:")
            print(f"1. 📋 Tool Service Integration Test")
            print(f"2. 🔗 MCP Connection Test")
            print(f"3. 🔧 Tool Execution Debug (Sync)")
            print(f"4. 🌊 Tool Execution Debug (Streaming)")
            print(f"5. 📡 Direct MCP Tool Call")
            print(f"6. 🔄 Comprehensive Scenario Test")
            print(f"7. 📊 Session Summary")
            print(f"8. 💾 Save Session")
            print(f"9. 🚪 Exit")
            
            choice = input(f"\nEnter choice (1-9): ").strip()
            
            try:
                if choice == "1":
                    await self.scenario_tool_service_test()
                elif choice == "2":
                    await self.scenario_mcp_connection_test()
                elif choice == "3":
                    await self.scenario_tool_execution_sync()
                elif choice == "4":
                    await self.scenario_tool_execution_streaming()
                elif choice == "5":
                    await self.scenario_direct_mcp_call()
                elif choice == "6":
                    await self.scenario_comprehensive_test()
                elif choice == "7":
                    self.print_session_summary()
                elif choice == "8":
                    self.save_session()
                elif choice == "9":
                    print(f"👋 Exiting debugger...")
                    if self.session:
                        self.save_session()
                    break
                else:
                    print(f"Invalid choice. Please enter 1-9.")
                    
            except KeyboardInterrupt:
                print(f"\n\n⚠️  Operation interrupted by user")
                continue
            except Exception as e:
                print(f"\n❌ Error: {e}")
                self.logger.error(f"Menu operation failed: {e}", exc_info=True)
    
    async def scenario_tool_service_test(self):
        """Scenario: Test ToolService integration"""
        self.start_session("tool_service_integration")
        
        print(f"\n📋 Tool Service Integration Test")
        print(f"{'='*40}")
        
        # Get configuration
        use_custom = input("Use custom configuration? (y/n): ").lower() == 'y'
        config = None
        
        if use_custom:
            print("Enter MCP server configuration:")
            name = input("Server name [local_server]: ") or "local_server"
            endpoint = input("Endpoint [http://localhost:8000/mcp]: ") or "http://localhost:8000/mcp"
            timeout = int(input("Timeout [30]: ") or 30)
            
            config = {
                "enable_mcp": True,
                "mcp_servers": [{
                    "name": name, 
                    "endpoint": endpoint, 
                    "timeout": timeout
                }]
            }
        
        success = await self.initialize_tool_service(config)
        
        if success:
            print(f"✅ ToolService initialized successfully")
            tools = await self.tool_service.list_tools()
            print(f"📋 Available tools: {tools}")
        else:
            print(f"❌ ToolService initialization failed")
    
    async def scenario_mcp_connection_test(self):
        """Scenario: Test MCP server connection"""
        self.start_session("mcp_connection_test")
        
        print(f"\n🔗 MCP Connection Test")
        print(f"{'='*30}")
        
        # Get server configuration
        name = input("Server name [test_server]: ") or "test_server"
        endpoint = input("Endpoint [http://localhost:8000/mcp]: ") or "http://localhost:8000/mcp"
        timeout = int(input("Timeout [30]: ") or 30)
        
        server_config = {
            "name": name,
            "endpoint": endpoint,
            "timeout": timeout
        }
        
        success, tools = await self.test_mcp_connection(server_config)
        
        if success:
            print(f"✅ MCP connection successful")
            print(f"🔧 Available tools: {[tool.name for tool in tools]}")
        else:
            print(f"❌ MCP connection failed")
    
    async def scenario_tool_execution_sync(self):
        """Scenario: Debug synchronous tool execution"""
        self.start_session("sync_tool_execution")
        
        print(f"\n🔧 Synchronous Tool Execution Debug")
        print(f"{'='*40}")
        
        if not self.tool_service:
            print("⚠️  ToolService not initialized. Running tool service test first...")
            await self.scenario_tool_service_test()
            
        if not self.tool_service:
            print("❌ Cannot proceed without ToolService")
            return
        
        # Get tool execution parameters
        available_tools = await self.tool_service.list_tools()
        print(f"Available tools: {available_tools}")
        
        tool_name = input("Tool name: ").strip()
        
        print("Enter parameters (JSON format, or press Enter for empty):")
        params_input = input("Parameters: ").strip()
        
        try:
            parameters = json.loads(params_input) if params_input else {}
        except json.JSONDecodeError:
            print("Invalid JSON format, using empty parameters")
            parameters = {}
        
        success, result = await self.debug_tool_execution(tool_name, parameters, use_streaming=False)
        
        if success:
            print(f"✅ Tool execution successful")
            print(f"📄 Result: {result}")
        else:
            print(f"❌ Tool execution failed")
    
    async def scenario_tool_execution_streaming(self):
        """Scenario: Debug streaming tool execution"""
        self.start_session("streaming_tool_execution")
        
        print(f"\n🌊 Streaming Tool Execution Debug")
        print(f"{'='*40}")
        
        if not self.tool_service:
            print("⚠️  ToolService not initialized. Running tool service test first...")
            await self.scenario_tool_service_test()
            
        if not self.tool_service:
            print("❌ Cannot proceed without ToolService")
            return
        
        # Get tool execution parameters
        available_tools = await self.tool_service.list_tools()
        print(f"Available tools: {available_tools}")
        
        tool_name = input("Tool name: ").strip()
        
        print("Enter parameters (JSON format, or press Enter for empty):")
        params_input = input("Parameters: ").strip()
        
        try:
            parameters = json.loads(params_input) if params_input else {}
        except json.JSONDecodeError:
            print("Invalid JSON format, using empty parameters")
            parameters = {}
        
        success, chunks = await self.debug_tool_execution(tool_name, parameters, use_streaming=True)
        
        if success:
            print(f"✅ Streaming execution successful")
            print(f"📊 Total chunks received: {chunks}")
        else:
            print(f"❌ Streaming execution failed")
    
    async def scenario_direct_mcp_call(self):
        """Scenario: Direct MCP tool call"""
        self.start_session("direct_mcp_call")
        
        print(f"\n📡 Direct MCP Tool Call")
        print(f"{'='*30}")
        
        if not self.mcp_clients:
            print("⚠️  No MCP clients available. Running connection test first...")
            await self.scenario_mcp_connection_test()
        
        if not self.mcp_clients:
            print("❌ Cannot proceed without MCP clients")
            return
        
        # Select MCP client
        print(f"Available MCP servers: {list(self.mcp_clients.keys())}")
        server_name = input("Server name: ").strip()
        
        if server_name not in self.mcp_clients:
            print(f"❌ Server '{server_name}' not found")
            return
        
        # Get tool information
        tool_name = input("Tool name: ").strip()
        
        print("Enter arguments (JSON format, or press Enter for empty):")
        args_input = input("Arguments: ").strip()
        
        try:
            arguments = json.loads(args_input) if args_input else {}
        except json.JSONDecodeError:
            print("Invalid JSON format, using empty arguments")
            arguments = {}
        
        use_streaming = input("Use streaming? (y/n): ").lower() == 'y'
        
        success, result = await self.debug_mcp_direct(server_name, tool_name, arguments, use_streaming)
        
        if success:
            print(f"✅ Direct MCP call successful")
            print(f"📄 Result: {result}")
        else:
            print(f"❌ Direct MCP call failed")
    
    async def scenario_comprehensive_test(self):
        """Scenario: Comprehensive test of all components"""
        self.start_session("comprehensive_test")
        
        print(f"\n🔄 Comprehensive Scenario Test")
        print(f"{'='*40}")
        
        # Step 1: Initialize ToolService
        print(f"Step 1: Initializing ToolService...")
        success = await self.initialize_tool_service()
        if not success:
            print(f"❌ Comprehensive test failed at ToolService initialization")
            return
        
        # Step 2: Test MCP connections
        print(f"Step 2: Testing MCP connections...")
        server_config = {
            "name": "comprehensive_test",
            "endpoint": "http://localhost:8000/mcp",
            "timeout": 30
        }
        
        success, tools = await self.test_mcp_connection(server_config)
        if not success:
            print(f"❌ Comprehensive test failed at MCP connection")
            return
        
        # Step 3: Test tool executions
        print(f"Step 3: Testing tool executions...")
        
        # Test with echo tool if available
        if "echo" in [tool.name for tool in tools]:
            print(f"Testing echo tool...")
            success, result = await self.debug_tool_execution("echo", {"text": "Comprehensive test"})
            if success:
                print(f"✅ Echo tool test passed")
            else:
                print(f"⚠️  Echo tool test failed")
        
        # Step 4: Test streaming
        print(f"Step 4: Testing streaming execution...")
        if "echo" in [tool.name for tool in tools]:
            success, chunks = await self.debug_tool_execution("echo", {"text": "Streaming test"}, use_streaming=True)
            if success:
                print(f"✅ Streaming test passed ({chunks} chunks)")
            else:
                print(f"⚠️  Streaming test failed")
        
        print(f"\n🎉 Comprehensive test completed!")
        self.print_session_summary()
    
    async def scenario_tool_resolver_test(self):
        """Scenario: Test ToolResolver functionality"""
        self.start_session("tool_resolver_test")
        
        print(f"\n🔍 Tool Resolver Test")
        print(f"{'='*30}")
        
        if not self.tool_resolver:
            print("⚠️  ToolResolver not initialized. Running tool service test first...")
            await self.scenario_tool_service_test()
            
        if not self.tool_resolver:
            print("❌ Cannot proceed without ToolResolver")
            return
        
        # Test different resolution strategies
        test_cases = [
            (["echo"], "Simple name resolution"),
            (["builtin.echo"], "Full name resolution"),
            (["timestamp", "echo"], "Multiple tool resolution"),
            (["search"], "MCP tool simple name"),
            (["nonexistent_tool"], "Non-existent tool error"),
        ]
        
        for tool_names, description in test_cases:
            print(f"\n📝 Testing: {description}")
            print(f"Input: {tool_names}")
            
            try:
                start_time = time.time()
                resolved_tools = await self.tool_resolver.resolve_tools(tool_names)
                end_time = time.time()
                
                self.session.add_log("INFO", f"Tool resolution successful: {description}", {
                    "input_tools": tool_names,
                    "resolved_count": len(resolved_tools),
                    "resolution_time": f"{end_time - start_time:.3f}s",
                    "resolved_tools": [tool.name for tool in resolved_tools]
                })
                
                print(f"✅ Success: Resolved {len(resolved_tools)} tools")
                for tool in resolved_tools:
                    print(f"   - {tool.name} (namespace: {tool.namespace})")
                    
            except ToolNotFoundError as e:
                self.session.add_log("WARNING", f"Expected tool resolution error: {e}")
                print(f"⚠️  Expected error: {e}")
            except Exception as e:
                self.session.add_log("ERROR", f"Unexpected tool resolution error: {e}")
                print(f"❌ Unexpected error: {e}")
        
        # Test with user permissions if available
        if UserContext and UserPermissions:
            print(f"\n🔐 Testing with user permissions...")
            user_context = UserContext(
                user_id="test_user",
                permissions=UserPermissions(permissions=["builtin.*"])
            )
            
            try:
                resolved_tools = await self.tool_resolver.resolve_tools(["echo"], user_context)
                print(f"✅ Permission test passed: {len(resolved_tools)} tools resolved")
            except Exception as e:
                print(f"❌ Permission test failed: {e}")
        else:
            print(f"\n⚠️  User permissions not available for testing")
    
    async def scenario_streaming_analysis(self):
        """Scenario: Analyze streaming performance and behavior"""
        self.start_session("streaming_analysis")
        
        print(f"\n🚦 Streaming Performance Analysis")
        print(f"{'='*40}")
        
        if not self.tool_service:
            await self.scenario_tool_service_test()
            
        if not self.tool_service:
            print("❌ Cannot proceed without ToolService")
            return
        
        # Test different streaming scenarios
        streaming_tests = [
            {
                "name": "echo",
                "params": {"text": "Quick streaming test"},
                "description": "Quick response streaming"
            },
            {
                "name": "echo", 
                "params": {"text": "Delayed streaming test", "delay": 2},
                "description": "Delayed response streaming"
            }
        ]
        
        for test_config in streaming_tests:
            print(f"\n📊 Testing: {test_config['description']}")
            
            # Compare sync vs streaming performance
            print(f"   Running synchronous execution...")
            sync_start = time.time()
            success, sync_result = await self.debug_tool_execution(
                test_config["name"], test_config["params"], use_streaming=False
            )
            sync_time = time.time() - sync_start
            
            print(f"   Running streaming execution...")
            stream_start = time.time()
            success, stream_chunks = await self.debug_tool_execution(
                test_config["name"], test_config["params"], use_streaming=True
            )
            stream_time = time.time() - stream_start
            
            # Analysis
            performance_analysis = {
                "test": test_config["description"],
                "sync_time": f"{sync_time:.3f}s",
                "stream_time": f"{stream_time:.3f}s",
                "time_difference": f"{abs(stream_time - sync_time):.3f}s",
                "streaming_chunks": stream_chunks if success else 0,
                "performance_delta": "faster" if stream_time < sync_time else "slower"
            }
            
            self.session.add_log("INFO", "Streaming performance analysis", performance_analysis)
            
            print(f"   📈 Results:")
            print(f"      Sync: {sync_time:.3f}s")
            print(f"      Stream: {stream_time:.3f}s ({stream_chunks} chunks)")
            print(f"      Streaming is {performance_analysis['performance_delta']}")
    
    async def scenario_error_edge_case_test(self):
        """Scenario: Test error handling and edge cases"""
        self.start_session("error_edge_case_test")
        
        print(f"\n⚠️  Error & Edge Case Testing")
        print(f"{'='*40}")
        
        if not self.tool_service:
            await self.scenario_tool_service_test()
            
        edge_cases = [
            {
                "name": "Test Non-existent Tool",
                "tool": "nonexistent_tool_xyz", 
                "params": {},
                "expect_error": True
            },
            {
                "name": "Test Invalid Parameters",
                "tool": "echo",
                "params": {"invalid_param": "value"},
                "expect_error": False
            },
            {
                "name": "Test Empty Parameters",
                "tool": "echo",
                "params": {},
                "expect_error": False
            },
            {
                "name": "Test Large Input",
                "tool": "echo",
                "params": {"text": "x" * 10000},
                "expect_error": False
            },
            {
                "name": "Test Special Characters",
                "tool": "echo",
                "params": {"text": "🚀 Special chars: ñ, é, 中文, 🔥"},
                "expect_error": False
            }
        ]
        
        passed_tests = 0
        total_tests = len(edge_cases)
        
        for test_case in edge_cases:
            print(f"\n🧪 {test_case['name']}")
            
            try:
                success, result = await self.debug_tool_execution(
                    test_case["tool"], test_case["params"]
                )
                
                if test_case["expect_error"]:
                    if not success:
                        print(f"✅ Expected error occurred (correct behavior)")
                        passed_tests += 1
                    else:
                        print(f"❌ Expected error but got success")
                else:
                    if success:
                        print(f"✅ Test passed successfully")
                        passed_tests += 1
                    else:
                        print(f"❌ Unexpected error occurred")
                        
            except Exception as e:
                if test_case["expect_error"]:
                    print(f"✅ Expected exception: {e}")
                    passed_tests += 1
                else:
                    print(f"❌ Unexpected exception: {e}")
        
        print(f"\n📊 Edge Case Test Results: {passed_tests}/{total_tests} passed")
        self.session.add_log("INFO", "Edge case testing completed", {
            "passed": passed_tests,
            "total": total_tests,
            "success_rate": f"{(passed_tests/total_tests)*100:.1f}%"
        })
    
    async def scenario_predefined_tests(self):
        """Scenario: Run predefined test scenarios"""
        self.start_session("predefined_tests")
        
        print(f"\n📋 Predefined Test Scenarios")
        print(f"{'='*40}")
        
        if not self.tool_service:
            await self.scenario_tool_service_test()
            
        print(f"Available test scenarios:")
        for i, (key, scenario) in enumerate(self.test_scenarios.items(), 1):
            print(f"  {i}. {scenario['description']}")
        
        choice = input(f"\nSelect scenario (1-{len(self.test_scenarios)}) or 'all': ").strip()
        
        if choice.lower() == 'all':
            selected_scenarios = list(self.test_scenarios.items())
        else:
            try:
                idx = int(choice) - 1
                scenario_items = list(self.test_scenarios.items())
                if 0 <= idx < len(scenario_items):
                    selected_scenarios = [scenario_items[idx]]
                else:
                    print("Invalid selection")
                    return
            except ValueError:
                print("Invalid input")
                return
        
        results = []
        for key, scenario in selected_scenarios:
            print(f"\n🧪 Running: {scenario['description']}")
            
            use_streaming = scenario.get("streaming", False)
            expect_error = scenario.get("expect_error", False)
            
            start_time = time.time()
            try:
                success, result = await self.debug_tool_execution(
                    scenario["name"], scenario["params"], use_streaming
                )
                
                execution_time = time.time() - start_time
                
                if expect_error:
                    test_result = "PASS" if not success else "FAIL (expected error)"
                else:
                    test_result = "PASS" if success else "FAIL"
                    
                results.append({
                    "scenario": key,
                    "result": test_result,
                    "time": f"{execution_time:.3f}s"
                })
                
                print(f"   Result: {test_result} ({execution_time:.3f}s)")
                
            except Exception as e:
                execution_time = time.time() - start_time
                test_result = "PASS (expected exception)" if expect_error else f"FAIL ({e})"
                results.append({
                    "scenario": key,
                    "result": test_result,
                    "time": f"{execution_time:.3f}s"
                })
                print(f"   Result: {test_result}")
        
        # Summary
        passed = sum(1 for r in results if "PASS" in r["result"])
        print(f"\n📊 Test Results Summary: {passed}/{len(results)} passed")
        
        self.session.add_log("INFO", "Predefined tests completed", {
            "results": results,
            "passed": passed,
            "total": len(results)
        })
    
    async def scenario_load_testing(self):
        """Scenario: Load testing with concurrent requests"""
        self.start_session("load_testing")
        
        print(f"\n🎯 Load Testing")
        print(f"{'='*20}")
        
        if not self.tool_service:
            await self.scenario_tool_service_test()
            
        # Get load test parameters
        concurrent_requests = int(input("Number of concurrent requests [10]: ") or 10)
        tool_name = input("Tool to test [echo]: ") or "echo"
        
        print(f"\n🚀 Starting load test: {concurrent_requests} concurrent '{tool_name}' calls")
        
        async def single_request(request_id: int):
            """Single request for load testing"""
            try:
                start_time = time.time()
                success, result = await self.debug_tool_execution(
                    tool_name, {"text": f"Load test request {request_id}"}
                )
                end_time = time.time()
                
                return {
                    "request_id": request_id,
                    "success": success,
                    "duration": end_time - start_time,
                    "error": None if success else "Execution failed"
                }
            except Exception as e:
                return {
                    "request_id": request_id,
                    "success": False,
                    "duration": 0,
                    "error": str(e)
                }
        
        # Execute concurrent requests
        start_time = time.time()
        tasks = [single_request(i) for i in range(concurrent_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Analyze results
        successful_requests = sum(1 for r in results if r["success"])
        failed_requests = concurrent_requests - successful_requests
        avg_duration = sum(r["duration"] for r in results if r["success"]) / max(successful_requests, 1)
        requests_per_second = successful_requests / total_time
        
        load_test_results = {
            "total_requests": concurrent_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": f"{(successful_requests/concurrent_requests)*100:.1f}%",
            "total_time": f"{total_time:.3f}s",
            "avg_request_duration": f"{avg_duration:.3f}s",
            "requests_per_second": f"{requests_per_second:.2f}"
        }
        
        print(f"\n📊 Load Test Results:")
        print(f"   Total Requests: {concurrent_requests}")
        print(f"   Successful: {successful_requests} ({load_test_results['success_rate']})")
        print(f"   Failed: {failed_requests}")
        print(f"   Total Time: {load_test_results['total_time']}")
        print(f"   Avg Duration: {load_test_results['avg_request_duration']}")
        print(f"   Requests/sec: {load_test_results['requests_per_second']}")
        
        self.session.add_log("INFO", "Load testing completed", load_test_results)
        
        # Show failures if any
        if failed_requests > 0:
            print(f"\n❌ Failed Requests:")
            for result in results:
                if not result["success"]:
                    print(f"   Request {result['request_id']}: {result['error']}")


async def main():
    """Main entry point"""
    debugger = InteractiveToolDebugger()
    
    # Show startup banner
    print(f"🛠️  Aether Frame Interactive Tool Debugger v2.0")
    print(f"{'='*50}")
    print(f"Enhanced with comprehensive debugging scenarios:")
    print(f"• Tool Resolution Testing")
    print(f"• Streaming Performance Analysis")
    print(f"• Error & Edge Case Testing")
    print(f"• Load Testing & Concurrent Execution")
    print(f"• Predefined Test Scenarios")
    print(f"{'='*50}")
    
    try:
        await debugger.interactive_menu()
    except KeyboardInterrupt:
        print(f"\n\n👋 Debugger interrupted. Goodbye!")
    except Exception as e:
        print(f"\n💥 Debugger crashed: {e}")
        debugger.logger.error(f"Debugger crashed: {e}", exc_info=True)
    finally:
        # Cleanup MCP clients
        for client in debugger.mcp_clients.values():
            try:
                await client.disconnect()
            except:
                pass
        
        # Cleanup tool service
        if debugger.tool_service:
            try:
                await debugger.tool_service.shutdown()
            except:
                pass


if __name__ == "__main__":
    asyncio.run(main())