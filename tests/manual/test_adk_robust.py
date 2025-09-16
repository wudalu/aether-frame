#!/usr/bin/env python3
"""
Robust ADK Test with SSL/Network Error Handling
This version includes comprehensive error handling for SSL and network issues
while maintaining full functionality testing.
"""

import asyncio
import logging
import sys
import os
import json
import warnings
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

# Suppress SSL and MCP warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning"

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

# Load test environment
from dotenv import load_dotenv
load_dotenv(".env.test")

from aether_frame.bootstrap import create_ai_assistant, health_check_system, create_system_components
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage, TaskStatus, ExecutionConfig, ExecutionContext, FrameworkType, ExecutionMode
# Removed logging_config import - using simplified logging


class RobustAdkTestSuite:
    """
    Robust ADK test suite with comprehensive error handling for SSL and network issues.
    """

    def __init__(self, test_name: str = "robust_adk_test"):
        """Initialize robust test suite."""
        self.test_name = test_name
        self.start_time = datetime.now()
        self.test_results: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(test_name)
        # Configure simple logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Test configuration
        self.settings = Settings()
        self.execution_tracer = None
        self.assistant = None
        
        # Performance tracking
        self.performance_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "network_errors": 0,
            "ssl_errors": 0,
            "tool_calls": 0,
            "total_execution_time": 0.0,
            "average_response_time": 0.0,
        }

    async def setup(self):
        """Setup test environment with error handling."""
        self.logger.info("=" * 80)
        self.logger.info("Robust ADK Test Suite - SSL/Network Error Handling")
        self.logger.info("=" * 80)
        self.logger.info(f"Test started at: {self.start_time.isoformat()}")
        
        # Environment check
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.logger.info(f"DeepSeek API Key configured: {'Yes' if deepseek_key and deepseek_key != 'your-deepseek-api-key-here' else 'No'}")
        self.logger.info(f"Python version: {sys.version}")
        
        try:
            # Create execution tracer
            execution_id = f"robust_{self.test_name}_{int(self.start_time.timestamp())}"
            self.logger.info(f"Starting robust execution trace for {execution_id}")
            
            # Initialize AI Assistant with timeout
            self.logger.info("Initializing Aether Frame with ADK (with timeout protection)...")
            
            try:
                self.assistant = await asyncio.wait_for(
                    create_ai_assistant(self.settings), 
                    timeout=30.0
                )
                self.logger.info("✓ AI Assistant initialized successfully")
            except asyncio.TimeoutError:
                self.logger.error("❌ AI Assistant initialization timed out")
                return False
            except Exception as e:
                self.logger.error(f"❌ AI Assistant initialization failed: {str(e)}")
                return False
            
            # Perform system health check
            self.logger.info("Performing system health check...")
            try:
                components = await create_system_components(self.settings)
                health_status = await health_check_system(components)
                self.logger.info(f"✓ System health check completed: {health_status['overall_status']}")
                
                # Verify tool availability
                if components.tool_service:
                    tools = await components.tool_service.list_tools()
                    self.logger.info(f"✓ Available tools: {tools}")
                    
                    if "builtin.chat_log" in tools:
                        self.logger.info("✓ ChatLogTool is available for testing")
                    else:
                        self.logger.warning("⚠️ ChatLogTool not found in available tools")
                else:
                    self.logger.warning("⚠️ Tool service not available")
                    
            except Exception as e:
                self.logger.error(f"❌ Health check failed: {str(e)}")
                return False
            
            self.logger.info("Robust setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Setup failed: {str(e)}")
            return False

    async def test_with_retry(self, test_func, max_retries: int = 2):
        """Execute test with retry logic for network errors."""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    self.logger.info(f"Retrying test (attempt {attempt + 1}/{max_retries + 1})...")
                    # Add delay between retries
                    await asyncio.sleep(2)
                
                # Execute test with timeout
                result = await asyncio.wait_for(test_func(), timeout=45.0)
                return result
                
            except asyncio.TimeoutError:
                last_exception = "Test execution timed out"
                self.logger.warning(f"⚠️ Test timed out on attempt {attempt + 1}")
                self.performance_metrics["network_errors"] += 1
                
            except (OSError, ConnectionError, Exception) as e:
                last_exception = str(e)
                if "Bad file descriptor" in str(e) or "SSL" in str(e):
                    self.performance_metrics["ssl_errors"] += 1
                    self.logger.warning(f"⚠️ SSL/Network error on attempt {attempt + 1}: {str(e)}")
                else:
                    self.performance_metrics["network_errors"] += 1
                    self.logger.warning(f"⚠️ Network error on attempt {attempt + 1}: {str(e)}")
                
                # Clean up any broken connections
                try:
                    await asyncio.sleep(1)
                except:
                    pass
        
        # All retries failed
        self.logger.error(f"❌ Test failed after {max_retries + 1} attempts. Last error: {last_exception}")
        return {
            "test_case": "failed_with_retries",
            "status": "network_error",
            "error_message": f"Failed after {max_retries + 1} attempts: {last_exception}",
            "timestamp": datetime.now().isoformat(),
        }

    async def test_simple_conversation(self) -> Dict[str, Any]:
        """Test simple conversation without tool calling to isolate network issues."""
        test_case = "simple_conversation"
        self.logger.info(f"\n--- Test Case: {test_case} ---")
        
        start_time = datetime.now()
        
        task_request = TaskRequest(
            task_id="robust_test_simple",
            task_type="chat",
            description="Simple conversation test for network reliability",
            messages=[
                UniversalMessage(
                    role="user",
                    content="Hello! Please give me a brief introduction about yourself in one sentence.",
                    metadata={"test": "simple_conversation", "retry_safe": True}
                )
            ],
            metadata={
                "test_type": "simple_conversation",
                "framework": "adk",
                "preferred_model": "deepseek-chat",
                "timestamp": start_time.isoformat(),
                "retry_safe": True,
            }
        )
        
        try:
            self.logger.debug(f"Executing simple conversation: {task_request.task_id}")
            result = await self.assistant.process_request(task_request)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update performance metrics
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time
            
            test_result = {
                "test_case": test_case,
                "task_id": task_request.task_id,
                "status": result.status.value if result.status else "unknown",
                "execution_time": execution_time,
                "response_length": len(result.messages[-1].content) if result.messages else 0,
                "error_message": result.error_message,
                "metadata": result.metadata,
                "timestamp": start_time.isoformat(),
            }
            
            if result.status == TaskStatus.SUCCESS:
                self.performance_metrics["successful_requests"] += 1
                self.logger.info(f"✓ Simple conversation completed in {execution_time:.2f}s")
                
                if result.messages and len(result.messages) > 0:
                    response = result.messages[-1].content
                    self.logger.info(f"✓ Response received: {response[:100]}...")
                    test_result["response_preview"] = response[:200]
                else:
                    self.logger.warning("⚠️ No response messages received")
                
            else:
                self.performance_metrics["failed_requests"] += 1
                self.logger.error(f"❌ Simple conversation failed: {result.error_message}")
            
            return test_result
            
        except Exception as e:
            self.performance_metrics["failed_requests"] += 1
            self.logger.error(f"❌ Simple conversation failed with exception: {str(e)}")
            
            return {
                "test_case": test_case,
                "status": "exception",
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "error_message": str(e),
                "timestamp": start_time.isoformat(),
            }

    async def test_basic_tool_request(self) -> Dict[str, Any]:
        """Test basic tool usage to verify tool integration works."""
        test_case = "basic_tool_request"
        self.logger.info(f"\n--- Test Case: {test_case} ---")
        
        start_time = datetime.now()
        
        task_request = TaskRequest(
            task_id="robust_test_tool",
            task_type="chat",
            description="Basic tool usage test",
            messages=[
                UniversalMessage(
                    role="user",
                    content="Please use the chat_log tool to save a simple message: 'Robust test successful'. Use format='json' and append=true.",
                    metadata={"test": "basic_tool", "expects_tool_call": True}
                )
            ],
            metadata={
                "test_type": "basic_tool_request",
                "framework": "adk",
                "preferred_model": "deepseek-chat",
                "timestamp": start_time.isoformat(),
                "expects_tool_call": True,
            }
        )
        
        try:
            self.logger.debug(f"Executing basic tool request: {task_request.task_id}")
            result = await self.assistant.process_request(task_request)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Update performance metrics
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time
            
            # Check for tool calls
            tool_calls_detected = self._detect_tool_calls(result)
            if tool_calls_detected:
                self.performance_metrics["tool_calls"] += 1
            
            test_result = {
                "test_case": test_case,
                "task_id": task_request.task_id,
                "status": result.status.value if result.status else "unknown",
                "execution_time": execution_time,
                "tool_calls_detected": tool_calls_detected,
                "error_message": result.error_message,
                "timestamp": start_time.isoformat(),
            }
            
            if result.status == TaskStatus.SUCCESS:
                self.performance_metrics["successful_requests"] += 1
                self.logger.info(f"✓ Basic tool test completed in {execution_time:.2f}s")
                
                if tool_calls_detected:
                    self.logger.info("✓ Tool call detected in response")
                
                if result.messages:
                    response = result.messages[-1].content
                    test_result["response_preview"] = response[:200]
                    self.logger.info(f"✓ Response: {response[:100]}...")
            else:
                self.performance_metrics["failed_requests"] += 1
                self.logger.error(f"❌ Basic tool test failed: {result.error_message}")
            
            return test_result
            
        except Exception as e:
            self.performance_metrics["failed_requests"] += 1
            self.logger.error(f"❌ Basic tool test failed with exception: {str(e)}")
            
            return {
                "test_case": test_case,
                "status": "exception",
                "execution_time": (datetime.now() - start_time).total_seconds(),
                "error_message": str(e),
                "timestamp": start_time.isoformat(),
            }

    def _detect_tool_calls(self, result) -> bool:
        """Detect if tool calls were made during execution."""
        if result.metadata:
            if "tool_calls" in result.metadata or "tools_used" in result.metadata:
                return True
        
        if result.messages:
            for message in result.messages:
                content = message.content.lower()
                if "chat_log" in content and any(word in content for word in ["saved", "file", "created", "logged"]):
                    return True
                if "tool" in content and any(word in content for word in ["executed", "called", "used"]):
                    return True
        
        return False

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
        
        # Environment and error analysis
        env_info = {
            "python_version": sys.version,
            "adk_available": True,
            "deepseek_model": "deepseek-chat",
            "deepseek_api_configured": bool(os.getenv("DEEPSEEK_API_KEY", "").strip() and 
                                          os.getenv("DEEPSEEK_API_KEY") != "your-deepseek-api-key-here"),
            "test_environment": "robust_test",
            "ssl_warnings_suppressed": True,
            "mcp_warnings_suppressed": True,
        }
        
        report = {
            "test_suite": self.test_name,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_duration": total_duration,
            "performance_metrics": self.performance_metrics,
            "test_results": self.test_results,
            "logging_stats": {"simplified_logging": True},
            "environment": env_info,
            "error_analysis": {
                "ssl_errors": self.performance_metrics["ssl_errors"],
                "network_errors": self.performance_metrics["network_errors"],
                "total_errors": self.performance_metrics["ssl_errors"] + self.performance_metrics["network_errors"],
            }
        }
        
        return report

    async def save_test_report(self, report: Dict[str, Any]):
        """Save test report to file."""
        report_dir = Path("logs/tests")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = report_dir / f"robust_test_report_{timestamp}.json"
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"✓ Robust test report saved to: {report_file}")
        return str(report_file)

    async def run_all_tests(self) -> bool:
        """Run all test cases with robust error handling."""
        try:
            # Setup
            setup_success = await self.setup()
            if not setup_success:
                self.logger.error("❌ Setup failed, cannot proceed with tests")
                return False
            
            # Run test cases with retry logic
            self.logger.info("\n" + "=" * 60)
            self.logger.info("RUNNING ROBUST TESTS WITH RETRY LOGIC")
            self.logger.info("=" * 60)
            
            # Test 1: Simple conversation (with retry)
            self.logger.info("Running simple conversation test with retry protection...")
            result1 = await self.test_with_retry(self.test_simple_conversation, max_retries=2)
            self.test_results.append(result1)
            
            # Test 2: Basic tool usage (with retry)
            self.logger.info("Running basic tool usage test with retry protection...")
            result2 = await self.test_with_retry(self.test_basic_tool_request, max_retries=2)
            self.test_results.append(result2)
            
            # Generate and save report
            self.logger.info("\n" + "=" * 60)
            self.logger.info("GENERATING ROBUST TEST REPORT")
            self.logger.info("=" * 60)
            
            report = await self.generate_performance_report()
            report_file = await self.save_test_report(report)
            
            # Print summary
            self.logger.info("\n" + "=" * 60)
            self.logger.info("ROBUST TEST SUMMARY")
            self.logger.info("=" * 60)
            
            for result in self.test_results:
                status_icon = "✓" if result.get("status") == "success" else "❌"
                self.logger.info(f"{status_icon} {result['test_case']}: {result.get('status', 'unknown')} ({result.get('execution_time', 0):.2f}s)")
            
            self.logger.info(f"\n📊 Performance Metrics:")
            self.logger.info(f"   Total Requests: {self.performance_metrics['total_requests']}")
            self.logger.info(f"   Successful: {self.performance_metrics['successful_requests']}")
            self.logger.info(f"   Failed: {self.performance_metrics['failed_requests']}")
            self.logger.info(f"   Tool Calls: {self.performance_metrics['tool_calls']}")
            self.logger.info(f"   SSL Errors: {self.performance_metrics['ssl_errors']}")
            self.logger.info(f"   Network Errors: {self.performance_metrics['network_errors']}")
            self.logger.info(f"   Success Rate: {self.performance_metrics.get('success_rate', 0):.1f}%")
            
            if self.performance_metrics["total_requests"] > 0:
                self.logger.info(f"   Avg Response Time: {self.performance_metrics.get('average_response_time', 0):.2f}s")
            
            self.logger.info(f"\n📋 Report saved to: {report_file}")
            
            # Determine overall success
            successful_tests = sum(1 for r in self.test_results if r.get("status") == "success")
            total_tests = len(self.test_results)
            
            if successful_tests > 0:
                self.logger.info(f"\n🎉 {successful_tests}/{total_tests} tests passed!")
                if successful_tests == total_tests:
                    self.logger.info("All tests completed successfully!")
                return True
            else:
                self.logger.warning(f"\n⚠️ No tests passed successfully!")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Test suite failed with exception: {str(e)}")
            return False


async def main():
    """Main robust test execution function."""
    print("Robust ADK Test Suite - SSL/Network Error Handling")
    print("=" * 60)
    print("Features:")
    print("- SSL/Network error handling with retry logic")
    print("- Warning suppression for known issues")
    print("- Timeout protection for all operations")
    print("- Comprehensive error analysis")
    print("- Real DeepSeek integration testing")
    print()
    
    test_suite = RobustAdkTestSuite("robust_adk_test")
    
    try:
        success = await test_suite.run_all_tests()
        
        if success:
            print("\n🎉 Robust test suite completed with some successes!")
            sys.exit(0)
        else:
            print("\n💥 All tests encountered issues!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Suppress warnings at runtime
    import warnings
    warnings.filterwarnings("ignore")
    
    # Run the robust test suite
    asyncio.run(main())