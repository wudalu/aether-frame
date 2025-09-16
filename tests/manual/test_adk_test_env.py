#!/usr/bin/env python3
"""
Enhanced End-to-end test for ADK runtime with tool integration - Test Environment Version
Tests the complete flow from TaskRequest to ADK execution, tool calling, and back.
Includes comprehensive logging and real LLM integration with DeepSeek.
This version loads configuration from .env.test file.
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

# Load test environment
from dotenv import load_dotenv
load_dotenv(".env.test")  # Load test-specific configuration

from aether_frame.bootstrap import create_ai_assistant, health_check_system, create_system_components
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage, TaskStatus, ExecutionConfig, ExecutionContext, FrameworkType, ExecutionMode
from aether_frame.common.logging_config import setup_test_logging, get_logging_config


class AdkTestEnvironmentSuite:
    """
    Test suite for ADK runtime with real DeepSeek integration using .env.test configuration.
    
    Features:
    - Real LLM integration (DeepSeek with API key from .env.test)
    - Tool calling verification (ChatLogTool)
    - Performance benchmarking
    - Comprehensive logging
    - Error handling and recovery
    """

    def __init__(self, test_name: str = "adk_test_env_e2e"):
        """Initialize test suite with test environment configuration."""
        self.test_name = test_name
        self.start_time = datetime.now()
        self.test_results: List[Dict[str, Any]] = []
        self.logger = setup_test_logging(test_name, level="DEBUG")
        self.logging_config = get_logging_config()
        
        # Test configuration - use Settings which will load from .env.test
        self.settings = Settings()
        self.execution_tracer = None
        self.assistant = None
        
        # Performance tracking
        self.performance_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "tool_calls": 0,
            "total_execution_time": 0.0,
            "average_response_time": 0.0,
        }

    async def setup(self):
        """Setup test environment and components."""
        self.logger.info("=" * 80)
        self.logger.info("ADK Test Environment End-to-End Suite")
        self.logger.info("=" * 80)
        self.logger.info(f"Test started at: {self.start_time.isoformat()}")
        
        # Log environment info
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.logger.info(f"DeepSeek API Key configured: {'Yes' if deepseek_key and deepseek_key != 'your-deepseek-api-key-here' else 'No'}")
        self.logger.info(f"Default model: {os.getenv('DEFAULT_MODEL', 'not-set')}")
        
        try:
            # Create execution tracer
            execution_id = f"test_{self.test_name}_{int(self.start_time.timestamp())}"
            self.execution_tracer = self.logging_config.create_execution_tracer(execution_id)
            self.execution_tracer.info(f"Starting execution trace for {execution_id}")
            
            # Initialize AI Assistant using bootstrap
            self.logger.info("Initializing Aether Frame with ADK...")
            self.assistant = await create_ai_assistant(self.settings)
            self.logger.info("✓ AI Assistant initialized successfully")
            
            # Perform system health check
            self.logger.info("Performing system health check...")
            components = await create_system_components(self.settings)
            health_status = await health_check_system(components)
            self.logger.info(f"✓ System health check completed: {health_status['overall_status']}")
            
            # Log component status
            for component, status in health_status.get("components", {}).items():
                self.logger.debug(f"Component {component}: {status}")
            
            # Verify tool availability
            if components.tool_service:
                tools = await components.tool_service.list_tools()
                self.logger.info(f"✓ Available tools: {tools}")
                
                # Verify ChatLogTool is available
                if "builtin.chat_log" in tools:
                    self.logger.info("✓ ChatLogTool is available for testing")
                else:
                    self.logger.warning("⚠️ ChatLogTool not found in available tools")
            else:
                self.logger.warning("⚠️ Tool service not available")
            
            self.execution_tracer.info("Setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Setup failed: {str(e)}")
            self.execution_tracer.error(f"Setup failed: {str(e)}")
            return False

    async def test_simple_chat_with_tool_request(self) -> Dict[str, Any]:
        """Test Case 1: Simple chat request that asks for tool usage."""
        test_case = "simple_chat_with_tool_request"
        self.logger.info(f"\n--- Test Case 1: {test_case} ---")
        self.execution_tracer.info(f"Starting test case: {test_case}")
        
        start_time = datetime.now()
        
        task_request = TaskRequest(
            task_id="adk_test_simple_tool",
            task_type="chat",
            description="Simple chat test with tool usage request",
            messages=[
                UniversalMessage(
                    role="user",
                    content="Hello! Please introduce yourself briefly and then use the chat_log tool to save our conversation to a file. Use these parameters: content='Hello from Aether Frame test!', format='json', append=true",
                    metadata={"test": "simple_chat_tool", "expects_tool_call": True}
                )
            ],
            metadata={
                "test_type": "simple_tool_request",
                "framework": "adk",
                "preferred_model": "deepseek-chat",
                "timestamp": start_time.isoformat(),
                "expects_tool_call": True,
            }
        )
        
        try:
            self.execution_tracer.debug(f"Executing task: {task_request.task_id}")
            result = await self.assistant.process_request(task_request)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update performance metrics
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time
            
            # Analyze result
            test_result = {
                "test_case": test_case,
                "task_id": task_request.task_id,
                "status": result.status.value if result.status else "unknown",
                "execution_time": execution_time,
                "response_length": len(result.messages[-1].content) if result.messages else 0,
                "tool_calls_detected": self._detect_tool_calls(result),
                "error_message": result.error_message,
                "metadata": result.metadata,
                "timestamp": start_time.isoformat(),
            }
            
            if result.status == TaskStatus.SUCCESS:
                self.performance_metrics["successful_requests"] += 1
                self.logger.info(f"✓ Test completed successfully in {execution_time:.2f}s")
                
                if result.messages and len(result.messages) > 0:
                    response = result.messages[-1].content
                    self.logger.info(f"✓ Response received: {response[:150]}...")
                    test_result["response_preview"] = response[:300]
                    
                    # Check for tool usage in response
                    if self._detect_tool_calls(result):
                        self.performance_metrics["tool_calls"] += 1
                        self.logger.info("✓ Tool call detected in response")
                else:
                    self.logger.warning("⚠️ No response messages received")
                
            else:
                self.performance_metrics["failed_requests"] += 1
                self.logger.error(f"❌ Test failed: {result.error_message}")
            
            self.execution_tracer.info(f"Test case {test_case} completed with status: {result.status}")
            return test_result
            
        except Exception as e:
            self.performance_metrics["failed_requests"] += 1
            self.logger.error(f"❌ Test case {test_case} failed with exception: {str(e)}")
            self.execution_tracer.error(f"Test case {test_case} exception: {str(e)}")
            
            return {
                "test_case": test_case,
                "status": "exception",
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "error_message": str(e),
                "timestamp": start_time.isoformat(),
            }

    async def test_conversation_with_math_and_tool(self) -> Dict[str, Any]:
        """Test Case 2: Math conversation with tool logging."""
        test_case = "conversation_with_math_and_tool"
        self.logger.info(f"\n--- Test Case 2: {test_case} ---")
        self.execution_tracer.info(f"Starting test case: {test_case}")
        
        start_time = datetime.now()
        
        # Create session ID for this test
        session_id = f"test_session_{int(start_time.timestamp())}"
        
        task_request = TaskRequest(
            task_id="adk_test_math_tool",
            task_type="chat",
            description="Math conversation with tool logging",
            messages=[
                UniversalMessage(role="user", content="What is 15 + 27?"),
                UniversalMessage(role="assistant", content="15 + 27 = 42."),
                UniversalMessage(
                    role="user", 
                    content=f"Great! Now please save this math conversation to a log file using the chat_log tool. Use session_id='{session_id}', format='json', and content='Math conversation: 15 + 27 = 42'"
                )
            ],
            metadata={
                "test_type": "math_conversation_tool",
                "framework": "adk",
                "preferred_model": "deepseek-chat",
                "session_id": session_id,
                "timestamp": start_time.isoformat(),
            }
        )
        
        try:
            self.execution_tracer.debug(f"Executing math + tool test: {task_request.task_id}")
            result = await self.assistant.process_request(task_request)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update performance metrics
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time
            
            # Check for tool calls
            tool_calls_detected = self._detect_tool_calls(result)
            if tool_calls_detected:
                self.performance_metrics["tool_calls"] += 1
            
            # Verify file was created
            log_file_created = self._verify_log_file_creation(session_id)
            
            test_result = {
                "test_case": test_case,
                "task_id": task_request.task_id,
                "status": result.status.value if result.status else "unknown",
                "execution_time": execution_time,
                "tool_calls_detected": tool_calls_detected,
                "log_file_created": log_file_created,
                "session_id": session_id,
                "error_message": result.error_message,
                "timestamp": start_time.isoformat(),
            }
            
            if result.status == TaskStatus.SUCCESS:
                self.performance_metrics["successful_requests"] += 1
                self.logger.info(f"✓ Math + tool test completed in {execution_time:.2f}s")
                
                if log_file_created:
                    self.logger.info("✓ Log file was created successfully")
                else:
                    self.logger.warning("⚠️ Log file was not found")
                
                if result.messages:
                    response = result.messages[-1].content
                    test_result["response_preview"] = response[:300]
                    self.logger.info(f"✓ Response: {response[:150]}...")
            else:
                self.performance_metrics["failed_requests"] += 1
                self.logger.error(f"❌ Math + tool test failed: {result.error_message}")
            
            self.execution_tracer.info(f"Math + tool test completed: success={result.status == TaskStatus.SUCCESS}, file_created={log_file_created}")
            return test_result
            
        except Exception as e:
            self.performance_metrics["failed_requests"] += 1
            self.logger.error(f"❌ Math + tool test failed with exception: {str(e)}")
            self.execution_tracer.error(f"Math + tool test exception: {str(e)}")
            
            return {
                "test_case": test_case,
                "status": "exception",
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "error_message": str(e),
                "timestamp": start_time.isoformat(),
            }

    def _detect_tool_calls(self, result) -> bool:
        """Detect if tool calls were made during execution."""
        # Check result metadata for tool indicators
        if result.metadata:
            if "tool_calls" in result.metadata:
                return True
            if "tools_used" in result.metadata:
                return True
        
        # Check response content for tool call indicators
        if result.messages:
            for message in result.messages:
                content = message.content.lower()
                if "chat_log" in content and any(word in content for word in ["saved", "file", "created", "logged"]):
                    return True
                if "tool" in content and any(word in content for word in ["executed", "called", "used"]):
                    return True
        
        return False

    def _verify_log_file_creation(self, session_id: str) -> bool:
        """Verify that a log file was created for the session."""
        logs_dir = Path("logs")
        session_logs_dir = logs_dir / "sessions"
        
        if not session_logs_dir.exists():
            return False
        
        # Look for files containing the session_id
        pattern = f"session_{session_id}_*.json"
        matching_files = list(session_logs_dir.glob(pattern))
        
        return len(matching_files) > 0

    async def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        # Calculate performance metrics
        if self.performance_metrics["total_requests"] > 0:
            self.performance_metrics["average_response_time"] = (
                self.performance_metrics["total_execution_time"] / 
                self.performance_metrics["total_requests"]
            )
            self.performance_metrics["success_rate"] = (
                self.performance_metrics["successful_requests"] / 
                self.performance_metrics["total_requests"] * 100
            )
        
        # Environment info
        env_info = {
            "python_version": sys.version,
            "adk_available": True,
            "deepseek_model": "deepseek-chat",
            "deepseek_api_configured": bool(os.getenv("DEEPSEEK_API_KEY", "").strip() and 
                                          os.getenv("DEEPSEEK_API_KEY") != "your-deepseek-api-key-here"),
            "test_environment": "test",
            "config_file": ".env.test"
        }
        
        report = {
            "test_suite": self.test_name,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_duration": total_duration,
            "performance_metrics": self.performance_metrics,
            "test_results": self.test_results,
            "logging_stats": self.logging_config.get_log_stats(),
            "environment": env_info
        }
        
        return report

    async def save_test_report(self, report: Dict[str, Any]):
        """Save test report to file."""
        report_dir = Path("logs/tests")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"test_report_{self.test_name}_{timestamp}.json"
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"✓ Test report saved to: {report_file}")
        return str(report_file)

    async def run_all_tests(self) -> bool:
        """Run all test cases and generate report."""
        try:
            # Setup
            setup_success = await self.setup()
            if not setup_success:
                return False
            
            # Run test cases
            self.logger.info("\n" + "=" * 60)
            self.logger.info("RUNNING TEST CASES WITH REAL DEEPSEEK INTEGRATION")
            self.logger.info("=" * 60)
            
            test_methods = [
                self.test_simple_chat_with_tool_request,
                self.test_conversation_with_math_and_tool,
            ]
            
            for test_method in test_methods:
                try:
                    result = await test_method()
                    self.test_results.append(result)
                except Exception as e:
                    self.logger.error(f"❌ Test method {test_method.__name__} failed: {str(e)}")
                    self.test_results.append({
                        "test_case": test_method.__name__,
                        "status": "exception",
                        "error_message": str(e),
                        "timestamp": datetime.now().isoformat(),
                    })
            
            # Generate and save report
            self.logger.info("\n" + "=" * 60)
            self.logger.info("GENERATING TEST REPORT")
            self.logger.info("=" * 60)
            
            report = await self.generate_performance_report()
            report_file = await self.save_test_report(report)
            
            # Print summary
            self.logger.info("\n" + "=" * 60)
            self.logger.info("TEST SUMMARY")
            self.logger.info("=" * 60)
            
            for result in self.test_results:
                status_icon = "✓" if result["status"] == "SUCCESS" else "❌"
                self.logger.info(f"{status_icon} {result['test_case']}: {result['status']} ({result.get('execution_time', 0):.2f}s)")
            
            self.logger.info(f"\n📊 Performance Metrics:")
            self.logger.info(f"   Total Requests: {self.performance_metrics['total_requests']}")
            self.logger.info(f"   Successful: {self.performance_metrics['successful_requests']}")
            self.logger.info(f"   Failed: {self.performance_metrics['failed_requests']}")
            self.logger.info(f"   Tool Calls: {self.performance_metrics['tool_calls']}")
            self.logger.info(f"   Success Rate: {self.performance_metrics.get('success_rate', 0):.1f}%")
            self.logger.info(f"   Avg Response Time: {self.performance_metrics.get('average_response_time', 0):.2f}s")
            
            self.logger.info(f"\n📋 Report saved to: {report_file}")
            
            # Determine overall success
            total_tests = len(self.test_results)
            successful_tests = sum(1 for r in self.test_results if r["status"] == "SUCCESS")
            
            if successful_tests == total_tests:
                self.logger.info("\n🎉 All tests passed successfully!")
                return True
            else:
                self.logger.warning(f"\n⚠️ {total_tests - successful_tests} out of {total_tests} tests failed!")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Test suite failed with exception: {str(e)}")
            if self.execution_tracer:
                self.execution_tracer.error(f"Test suite exception: {str(e)}")
            return False


async def main():
    """Main test execution function."""
    test_suite = AdkTestEnvironmentSuite("adk_test_env_e2e")
    
    try:
        success = await test_suite.run_all_tests()
        
        if success:
            print("\n🎉 All test environment tests passed!")
            sys.exit(0)
        else:
            print("\n💥 Some tests failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    print("ADK Test Environment Suite with Real DeepSeek Integration")
    print("=" * 60)
    print("Features:")
    print("- Uses .env.test configuration")
    print("- Real DeepSeek LLM integration")
    print("- Tool calling verification (ChatLogTool)")
    print("- Comprehensive logging and tracing")
    print("- Performance benchmarking")
    print("- Structured test reporting")
    print()
    
    # Run the test suite
    asyncio.run(main())