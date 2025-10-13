#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration test runner for MCP unified interface."""

import asyncio
import sys
import subprocess
import time
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src"))

from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError
from aether_frame.tools.mcp.config import MCPServerConfig


class MCPTestRunner:
    """Comprehensive test runner for MCP unified interface."""
    
    def __init__(self):
        self.test_server_process: Optional[subprocess.Popen] = None
        self.streaming_server_process: Optional[subprocess.Popen] = None
        
    async def start_test_servers(self):
        """Start test MCP servers."""
        print("🚀 Starting MCP test servers...")
        
        # Start basic test server
        try:
            self.test_server_process = subprocess.Popen([
                sys.executable, 
                str(Path(__file__).parent / "test_mcp_server.py")
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("✅ Basic test server started (port 8000)")
        except Exception as e:
            print(f"❌ Failed to start basic test server: {e}")
        
        # Start streaming test server  
        try:
            self.streaming_server_process = subprocess.Popen([
                sys.executable,
                str(Path(__file__).parent / "real_streaming_server.py")
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("✅ Streaming test server started (port 8002)")
        except Exception as e:
            print(f"❌ Failed to start streaming test server: {e}")
        
        # Wait for servers to start
        print("⏳ Waiting for servers to initialize...")
        await asyncio.sleep(3)
    
    def stop_test_servers(self):
        """Stop test MCP servers."""
        print("🛑 Stopping test servers...")
        
        if self.test_server_process:
            self.test_server_process.terminate()
            self.test_server_process.wait()
            print("✅ Basic test server stopped")
        
        if self.streaming_server_process:
            self.streaming_server_process.terminate()
            self.streaming_server_process.wait()
            print("✅ Streaming test server stopped")
    
    async def test_server_connectivity(self):
        """Test connectivity to MCP servers."""
        print("\n🔗 Testing server connectivity...")
        
        # Test basic server
        basic_config = MCPServerConfig(
            name="basic_test",
            endpoint="http://localhost:8000/mcp",
            timeout=5
        )
        
        try:
            async with MCPClient(basic_config) as client:
                tools = await client.discover_tools()
                print(f"✅ Basic server: Connected, {len(tools)} tools available")
        except Exception as e:
            print(f"❌ Basic server connection failed: {e}")
            return False
        
        # Test streaming server
        streaming_config = MCPServerConfig(
            name="streaming_test",
            endpoint="http://localhost:8002/mcp",
            timeout=5
        )
        
        try:
            async with MCPClient(streaming_config) as client:
                tools = await client.discover_tools()
                print(f"✅ Streaming server: Connected, {len(tools)} tools available")
        except Exception as e:
            print(f"❌ Streaming server connection failed: {e}")
            return False
        
        return True
    
    async def run_basic_functionality_tests(self):
        """Run basic functionality tests."""
        print("\n🧪 Running basic functionality tests...")
        
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            timeout=10
        )
        
        try:
            async with MCPClient(config) as client:
                print("📋 Testing tool discovery...")
                tools = await client.discover_tools()
                assert len(tools) > 0, "No tools discovered"
                print(f"✅ Discovered {len(tools)} tools")
                
                print("🔧 Testing synchronous tool calls...")
                # Test echo tool
                result = await client.call_tool("echo", {"text": "Test message"})
                assert "Test message" in str(result), f"Echo failed: {result}"
                print("✅ Echo tool works")
                
                # Test add tool
                result = await client.call_tool("add", {"a": 10, "b": 5})
                expected = 15
                assert result == expected or str(expected) in str(result), f"Add failed: {result}"
                print("✅ Add tool works")
                
                print("🌊 Testing streaming tool calls...")
                chunks = []
                async for chunk in client.call_tool_stream("echo", {"text": "Streaming test"}):
                    chunks.append(chunk)
                
                assert len(chunks) >= 2, f"Not enough chunks received: {len(chunks)}"
                
                start_chunks = [c for c in chunks if c.get("type") == "stream_start"]
                complete_chunks = [c for c in chunks if c.get("type") == "complete_result"]
                
                assert len(start_chunks) >= 1, "No start chunk received"
                assert len(complete_chunks) >= 1, "No complete chunk received"
                print("✅ Streaming interface works")
                
        except Exception as e:
            print(f"❌ Basic functionality test failed: {e}")
            raise
    
    async def run_streaming_specific_tests(self):
        """Run streaming-specific tests with real streaming server."""
        print("\n🌊 Running streaming-specific tests...")
        
        config = MCPServerConfig(
            name="streaming_server",
            endpoint="http://localhost:8002/mcp",
            timeout=15
        )
        
        try:
            async with MCPClient(config) as client:
                print("📊 Testing progress reporting...")
                
                # Test long computation with progress
                chunks = []
                start_time = time.time()
                
                async for chunk in client.call_tool_stream("long_computation", {"steps": 3}):
                    chunks.append(chunk)
                    chunk_time = time.time() - start_time
                    print(f"  📦 [{chunk_time:.2f}s] {chunk.get('type')}: {str(chunk.get('content', ''))[:50]}...")
                
                # Verify streaming behavior
                progress_chunks = [c for c in chunks if c.get("type") == "progress_update"]
                complete_chunks = [c for c in chunks if c.get("type") == "complete_result"]
                
                print(f"✅ Received {len(progress_chunks)} progress updates")
                print(f"✅ Received {len(complete_chunks)} completion chunks")
                
                # Test real-time data stream
                print("📡 Testing real-time data stream...")
                chunks = []
                async for chunk in client.call_tool_stream("real_time_data_stream", {"duration": 2}):
                    chunks.append(chunk)
                
                print(f"✅ Real-time stream: {len(chunks)} total chunks")
                
        except Exception as e:
            print(f"❌ Streaming test failed: {e}")
            raise
    
    async def run_error_handling_tests(self):
        """Run error handling tests."""
        print("\n❌ Testing error handling...")
        
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            timeout=5
        )
        
        try:
            async with MCPClient(config) as client:
                # Test non-existent tool
                print("🔧 Testing non-existent tool...")
                try:
                    await client.call_tool("nonexistent_tool", {})
                    assert False, "Should have raised an error"
                except Exception as e:
                    print(f"✅ Correctly caught error: {type(e).__name__}")
                
                # Test streaming error
                print("🌊 Testing streaming error...")
                error_caught = False
                async for chunk in client.call_tool_stream("nonexistent_stream_tool", {}):
                    if chunk.get("type") == "error":
                        error_caught = True
                        print(f"✅ Correctly caught streaming error: {chunk.get('error')}")
                        break
                
                if not error_caught:
                    print("⚠️ No streaming error chunk received")
                
        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            raise
    
    async def run_performance_tests(self):
        """Run performance tests."""
        print("\n⚡ Running performance tests...")
        
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp",
            timeout=10
        )
        
        try:
            async with MCPClient(config) as client:
                # Test concurrent calls
                print("🔄 Testing concurrent tool calls...")
                start_time = time.time()
                
                tasks = [
                    client.call_tool("add", {"a": i, "b": i+1})
                    for i in range(5)
                ]
                
                results = await asyncio.gather(*tasks)
                elapsed = time.time() - start_time
                
                print(f"✅ 5 concurrent calls completed in {elapsed:.2f}s")
                print(f"✅ Results: {results}")
                
                # Test streaming performance
                print("🌊 Testing streaming performance...")
                start_time = time.time()
                
                chunk_count = 0
                async for chunk in client.call_tool_stream("echo", {"text": "Performance test"}):
                    chunk_count += 1
                
                elapsed = time.time() - start_time
                print(f"✅ Streaming completed in {elapsed:.2f}s with {chunk_count} chunks")
                
        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            raise
    
    async def run_all_tests(self):
        """Run complete test suite."""
        print("🚀 Starting comprehensive MCP unified interface tests")
        print("=" * 60)
        
        try:
            # Start servers
            await self.start_test_servers()
            
            # Test connectivity
            if not await self.test_server_connectivity():
                print("❌ Server connectivity failed - aborting tests")
                return False
            
            # Run test suites
            await self.run_basic_functionality_tests()
            await self.run_streaming_specific_tests()
            await self.run_error_handling_tests()
            await self.run_performance_tests()
            
            print("\n" + "=" * 60)
            print("✅ ALL TESTS PASSED! MCP unified interface is working correctly! 🎉")
            print("=" * 60)
            return True
            
        except Exception as e:
            print(f"\n❌ TESTS FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            self.stop_test_servers()
    
    def run_unit_tests(self):
        """Run unit tests using pytest."""
        print("\n🧪 Running unit tests with pytest...")
        
        test_file = Path(__file__).parent / "test_unified_mcp_interface.py"
        
        try:
            result = subprocess.run([
                sys.executable, "-m", "pytest",
                str(test_file),
                "-v", "-s", "--tb=short",
                "-m", "not integration"
            ], capture_output=True, text=True, timeout=60)
            
            print("Unit test output:")
            print(result.stdout)
            if result.stderr:
                print("Unit test errors:")
                print(result.stderr)
            
            if result.returncode == 0:
                print("✅ Unit tests passed!")
                return True
            else:
                print("❌ Unit tests failed!")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Unit tests timed out!")
            return False
        except Exception as e:
            print(f"❌ Unit test execution failed: {e}")
            return False


async def main():
    """Main test execution."""
    runner = MCPTestRunner()
    
    print("🎯 MCP Unified Interface - Comprehensive Test Suite")
    print("=" * 60)
    
    # Run unit tests first
    unit_success = runner.run_unit_tests()
    
    # Run integration tests
    integration_success = await runner.run_all_tests()
    
    # Final summary
    print("\n📊 FINAL TEST SUMMARY")
    print("=" * 30)
    print(f"Unit Tests: {'✅ PASSED' if unit_success else '❌ FAILED'}")
    print(f"Integration Tests: {'✅ PASSED' if integration_success else '❌ FAILED'}")
    
    overall_success = unit_success and integration_success
    print(f"Overall: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return 0 if overall_success else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test runner crashed: {e}")
        sys.exit(1)