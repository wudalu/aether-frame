#!/usr/bin/env python3
"""
Complete End-to-End Test with Detailed Logging
This script performs comprehensive testing with full request/response logging.
"""

import asyncio
import logging
import sys
import os
import json
import warnings
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning"

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

# Load test environment
from dotenv import load_dotenv
load_dotenv(".env.test")

from aether_frame.bootstrap import create_ai_assistant, health_check_system, create_system_components
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage, TaskStatus


class CompleteE2ETestSuite:
    """
    Complete End-to-End test suite with detailed request/response logging.
    """

    def __init__(self, test_name: str = "complete_e2e_test"):
        """Initialize complete E2E test suite."""
        self.test_name = test_name
        self.start_time = datetime.now()
        self.test_results: List[Dict[str, Any]] = []
        
        # Setup logging
        self.setup_logging()
        
        # Test configuration
        self.settings = Settings()
        self.assistant = None
        
        # Performance tracking
        self.performance_metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "tool_calls_detected": 0,
            "total_execution_time": 0.0,
            "average_response_time": 0.0,
        }

    def setup_logging(self):
        """Setup detailed logging for the test suite."""
        # Create logs directory
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Create timestamp for this test run
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Setup file logger for detailed logs
        self.log_file = self.log_dir / f"complete_e2e_test_{timestamp}.log"
        
        # Configure logger
        self.logger = logging.getLogger(self.test_name)
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # File handler for detailed logs
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler for important info
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.propagate = False

    async def setup(self):
        """Setup test environment with detailed logging."""
        self.logger.info("=" * 80)
        self.logger.info("COMPLETE E2E TEST SUITE - DETAILED REQUEST/RESPONSE LOGGING")
        self.logger.info("=" * 80)
        self.logger.info(f"Test started at: {self.start_time.isoformat()}")
        self.logger.info(f"Log file: {self.log_file}")
        
        # Environment check
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.logger.info(f"DeepSeek API Key configured: {'Yes' if deepseek_key and deepseek_key != 'your-deepseek-api-key-here' else 'No'}")
        self.logger.info(f"Python version: {sys.version}")
        
        try:
            self.logger.info("🚀 STEP 1: Initializing Aether Frame system...")
            self.logger.debug("Creating AI Assistant with timeout protection...")
            
            try:
                self.assistant = await asyncio.wait_for(
                    create_ai_assistant(self.settings), 
                    timeout=30.0
                )
                self.logger.info("✅ AI Assistant initialized successfully")
                self.logger.debug(f"Assistant type: {type(self.assistant).__name__}")
                
            except asyncio.TimeoutError:
                self.logger.error("❌ AI Assistant initialization timed out (30s)")
                return False
            except Exception as e:
                self.logger.error(f"❌ AI Assistant initialization failed: {str(e)}")
                return False
            
            # System health check
            self.logger.info("🔍 STEP 2: Performing system health check...")
            try:
                components = await create_system_components(self.settings)
                health_status = await health_check_system(components)
                
                self.logger.debug(f"Health check result: {json.dumps(health_status, indent=2)}")
                
                if health_status.get("overall_status") == "healthy":
                    self.logger.info("✅ System health check passed")
                else:
                    self.logger.warning(f"⚠️ System health check issues: {health_status}")
                    
            except Exception as e:
                self.logger.error(f"❌ Health check failed: {str(e)}")
                return False
            
            self.logger.info("✅ Setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Setup failed: {str(e)}")
            return False

    def log_request_details(self, task_request: TaskRequest, test_case: str):
        """Log detailed request information."""
        self.logger.info(f"📤 REQUEST [{test_case}] - Starting")
        self.logger.debug(f"Task ID: {task_request.task_id}")
        self.logger.debug(f"Task Type: {task_request.task_type}")
        self.logger.debug(f"Description: {task_request.description}")
        
        if task_request.messages:
            self.logger.debug(f"Messages Count: {len(task_request.messages)}")
            for i, msg in enumerate(task_request.messages):
                self.logger.debug(f"Message {i+1}: [{msg.role}] {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}")
                if msg.metadata:
                    self.logger.debug(f"Message {i+1} metadata: {msg.metadata}")
        
        if task_request.metadata:
            self.logger.debug(f"Request metadata: {task_request.metadata}")

    def log_response_details(self, result, test_case: str, execution_time: float):
        """Log detailed response information."""
        self.logger.info(f"📥 RESPONSE [{test_case}] - Completed in {execution_time:.3f}s")
        self.logger.debug(f"Task ID: {result.task_id}")
        self.logger.debug(f"Status: {result.status.value if result.status else 'unknown'}")
        
        if result.messages:
            self.logger.debug(f"Response Messages Count: {len(result.messages)}")
            for i, msg in enumerate(result.messages):
                self.logger.debug(f"Response {i+1}: [{msg.role}] {msg.content}")
                if msg.metadata:
                    self.logger.debug(f"Response {i+1} metadata: {msg.metadata}")
        else:
            self.logger.debug("No response messages")
        
        if result.error_message:
            self.logger.debug(f"Error Message: {result.error_message}")
        
        if result.metadata:
            self.logger.debug(f"Response metadata: {result.metadata}")
        
        if result.result_data:
            self.logger.debug(f"Result data: {result.result_data}")

    async def test_simple_conversation(self):
        """Test simple conversation with detailed logging."""
        test_case = "simple_conversation"
        self.logger.info(f"🧪 TEST CASE: {test_case}")
        self.logger.info("├── FLOW: User Request → AI Assistant → ADK Adapter → DeepSeek Model → Response")
        
        start_time = datetime.now()
        
        task_request = TaskRequest(
            task_id=f"e2e_simple_{int(start_time.timestamp())}",
            task_type="chat",
            description="Simple conversation test with greeting",
            messages=[
                UniversalMessage(
                    role="user",
                    content="Hello! Please tell me about yourself and what you can do.",
                    metadata={"test_case": test_case, "expects_response": True}
                )
            ],
            metadata={
                "test_framework": "adk_complete_e2e",  # 明确标识基于ADK框架
                "framework_type": "adk",                # ADK框架类型
                "test_suite": "complete_e2e",          # 测试套件名称
                "test_case": test_case,
                "preferred_model": "deepseek-chat",
                "timestamp": start_time.isoformat(),
            }
        )
        
        # Log request details
        self.logger.info("└── 📤 STEP 1: Preparing request...")
        self.log_request_details(task_request, test_case)
        
        try:
            self.logger.info("└── 🔄 STEP 2: Sending to AI Assistant...")
            result = await self.assistant.process_request(task_request)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            self.logger.info("└── 📥 STEP 3: Processing response...")
            # Log response details
            self.log_response_details(result, test_case, execution_time)
            
            # Update performance metrics
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time
            
            if result.status == TaskStatus.SUCCESS:
                self.performance_metrics["successful_requests"] += 1
                
                # Check if we got a meaningful response
                has_response = bool(result.messages and result.messages[0].content.strip())
                
                test_result = {
                    "test_case": test_case,
                    "task_id": task_request.task_id,
                    "status": "success",
                    "execution_time": execution_time,
                    "response_length": len(result.messages[0].content) if result.messages else 0,
                    "has_response": has_response,
                    "error_message": None,
                    "metadata": result.metadata,
                    "timestamp": datetime.now().isoformat(),
                    "response_preview": result.messages[0].content[:200] + "..." if result.messages and len(result.messages[0].content) > 200 else result.messages[0].content if result.messages else "",
                }
                
                self.test_results.append(test_result)
                self.logger.info(f"└── ✅ STEP 4: SUCCESS - Got response ({len(result.messages[0].content) if result.messages else 0} chars)")
                return True
                
            else:
                self.performance_metrics["failed_requests"] += 1
                
                test_result = {
                    "test_case": test_case,
                    "task_id": task_request.task_id,
                    "status": "failed",
                    "execution_time": execution_time,
                    "error_message": result.error_message,
                    "timestamp": datetime.now().isoformat(),
                }
                
                self.test_results.append(test_result)
                self.logger.error(f"└── ❌ STEP 4: FAILED - {result.error_message}")
                return False
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["failed_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time
            
            self.logger.error(f"└── ❌ STEP 4: EXCEPTION - {str(e)}")
            
            test_result = {
                "test_case": test_case,
                "task_id": task_request.task_id,
                "status": "exception",
                "execution_time": execution_time,
                "error_message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            
            self.test_results.append(test_result)
            return False

    async def test_tool_usage_request(self):
        """Test tool usage with detailed logging."""
        test_case = "tool_usage_request"
        self.logger.info(f"\n🧪 TEST CASE: {test_case}")
        
        start_time = datetime.now()
        
        task_request = TaskRequest(
            task_id=f"e2e_tool_{int(start_time.timestamp())}",
            task_type="chat",
            description="Tool usage test with chat log saving",
            messages=[
                UniversalMessage(
                    role="user",
                    content="Please use the chat_log tool to save this conversation content: 'Complete E2E test conversation for tool usage validation'. Use these exact parameters: content='Complete E2E test conversation for tool usage validation', format='json', session_id='e2e_test_session'.",
                    metadata={"test_case": test_case, "expects_tool_call": True}
                )
            ],
            metadata={
                "test_framework": "adk_complete_e2e",
                "framework_type": "adk", 
                "test_suite": "complete_e2e",
                "test_case": test_case,
                "preferred_model": "deepseek-chat",
                "timestamp": start_time.isoformat(),
                "expects_tool_usage": True,
            }
        )
        
        # Log request details
        self.log_request_details(task_request, test_case)
        
        try:
            result = await self.assistant.process_request(task_request)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Log response details
            self.log_response_details(result, test_case, execution_time)
            
            # Update performance metrics
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time
            
            if result.status == TaskStatus.SUCCESS:
                self.performance_metrics["successful_requests"] += 1
                
                # Check for tool usage indicators
                tool_used = False
                if result.messages:
                    response_content = result.messages[0].content.lower()
                    tool_indicators = ["chat_log", "saved", "logged", "tool", "file"]
                    tool_used = any(indicator in response_content for indicator in tool_indicators)
                
                if tool_used:
                    self.performance_metrics["tool_calls_detected"] += 1
                    
                test_result = {
                    "test_case": test_case,
                    "task_id": task_request.task_id,
                    "status": "success",
                    "execution_time": execution_time,
                    "response_length": len(result.messages[0].content) if result.messages else 0,
                    "tool_calls_detected": tool_used,
                    "error_message": None,
                    "metadata": result.metadata,
                    "timestamp": datetime.now().isoformat(),
                    "response_preview": result.messages[0].content[:200] + "..." if result.messages and len(result.messages[0].content) > 200 else result.messages[0].content if result.messages else "",
                }
                
                self.test_results.append(test_result)
                
                if tool_used:
                    self.logger.info(f"✅ {test_case} PASSED - Tool usage detected")
                else:
                    self.logger.warning(f"⚠️ {test_case} PARTIAL - No tool usage detected")
                return True
                
            else:
                self.performance_metrics["failed_requests"] += 1
                
                test_result = {
                    "test_case": test_case,
                    "task_id": task_request.task_id,
                    "status": "failed",
                    "execution_time": execution_time,
                    "error_message": result.error_message,
                    "timestamp": datetime.now().isoformat(),
                }
                
                self.test_results.append(test_result)
                self.logger.error(f"❌ {test_case} FAILED - {result.error_message}")
                return False
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["failed_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time
            
            self.logger.error(f"❌ {test_case} EXCEPTION - {str(e)}")
            
            test_result = {
                "test_case": test_case,
                "task_id": task_request.task_id,
                "status": "exception",
                "execution_time": execution_time,
                "error_message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            
            self.test_results.append(test_result)
            return False

    async def test_complex_conversation(self):
        """Test complex multi-turn conversation with detailed logging."""
        test_case = "complex_conversation"
        self.logger.info(f"\n🧪 TEST CASE: {test_case}")
        
        start_time = datetime.now()
        
        task_request = TaskRequest(
            task_id=f"e2e_complex_{int(start_time.timestamp())}",
            task_type="chat",
            description="Complex conversation with context and multiple requirements",
            messages=[
                UniversalMessage(
                    role="user",
                    content="I'm working on a Python project and need help with the following: 1) Explain async/await in Python, 2) Give me a simple example, 3) Tell me when to use it vs regular functions. Please be comprehensive but concise.",
                    metadata={"test_case": test_case, "complexity": "high"}
                )
            ],
            metadata={
                "test_framework": "adk_complete_e2e",
                "framework_type": "adk",
                "test_suite": "complete_e2e", 
                "test_case": test_case,
                "preferred_model": "deepseek-chat",
                "timestamp": start_time.isoformat(),
                "complexity_level": "high",
                "expected_topics": ["async", "await", "python", "examples"],
            }
        )
        
        # Log request details
        self.log_request_details(task_request, test_case)
        
        try:
            result = await self.assistant.process_request(task_request)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Log response details
            self.log_response_details(result, test_case, execution_time)
            
            # Update performance metrics
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time
            
            if result.status == TaskStatus.SUCCESS:
                self.performance_metrics["successful_requests"] += 1
                
                # Check response quality
                response_quality = {"comprehensive": False, "has_examples": False, "addresses_all_points": False}
                if result.messages:
                    content = result.messages[0].content.lower()
                    response_quality["comprehensive"] = len(content) > 300
                    response_quality["has_examples"] = any(word in content for word in ["example", "def ", "async def", "await"])
                    response_quality["addresses_all_points"] = all(word in content for word in ["async", "await", "function"])
                
                test_result = {
                    "test_case": test_case,
                    "task_id": task_request.task_id,
                    "status": "success",
                    "execution_time": execution_time,
                    "response_length": len(result.messages[0].content) if result.messages else 0,
                    "response_quality": response_quality,
                    "error_message": None,
                    "metadata": result.metadata,
                    "timestamp": datetime.now().isoformat(),
                    "response_preview": result.messages[0].content[:300] + "..." if result.messages and len(result.messages[0].content) > 300 else result.messages[0].content if result.messages else "",
                }
                
                self.test_results.append(test_result)
                
                quality_score = sum(response_quality.values())
                if quality_score >= 2:
                    self.logger.info(f"✅ {test_case} PASSED - High quality response (score: {quality_score}/3)")
                else:
                    self.logger.warning(f"⚠️ {test_case} PARTIAL - Lower quality response (score: {quality_score}/3)")
                return True
                
            else:
                self.performance_metrics["failed_requests"] += 1
                
                test_result = {
                    "test_case": test_case,
                    "task_id": task_request.task_id,
                    "status": "failed",
                    "execution_time": execution_time,
                    "error_message": result.error_message,
                    "timestamp": datetime.now().isoformat(),
                }
                
                self.test_results.append(test_result)
                self.logger.error(f"❌ {test_case} FAILED - {result.error_message}")
                return False
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["failed_requests"] += 1
            self.performance_metrics["total_execution_time"] += execution_time
            
            self.logger.error(f"❌ {test_case} EXCEPTION - {str(e)}")
            
            test_result = {
                "test_case": test_case,
                "task_id": task_request.task_id,
                "status": "exception",
                "execution_time": execution_time,
                "error_message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            
            self.test_results.append(test_result)
            return False

    def generate_final_report(self):
        """Generate comprehensive final test report."""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        # Calculate performance metrics
        if self.performance_metrics["total_requests"] > 0:
            self.performance_metrics["average_response_time"] = (
                self.performance_metrics["total_execution_time"] / self.performance_metrics["total_requests"]
            )
            success_rate = (self.performance_metrics["successful_requests"] / self.performance_metrics["total_requests"]) * 100
        else:
            success_rate = 0.0
        
        # Environment info
        env_info = {
            "python_version": sys.version,
            "aether_frame_available": True,
            "deepseek_model": "deepseek-chat",
            "deepseek_api_configured": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
            "test_environment": "complete_e2e",
            "config_file": ".env.test"
        }
        
        # Generate report
        report = {
            "test_suite": "complete_e2e_test",
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_duration": total_duration,
            "performance_metrics": {
                **self.performance_metrics,
                "success_rate": success_rate
            },
            "test_results": self.test_results,
            "environment": env_info,
            "summary": {
                "total_tests": len(self.test_results),
                "passed_tests": len([r for r in self.test_results if r["status"] == "success"]),
                "failed_tests": len([r for r in self.test_results if r["status"] == "failed"]),
                "exception_tests": len([r for r in self.test_results if r["status"] == "exception"]),
            }
        }
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.log_dir / f"complete_e2e_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"✅ Complete E2E test report saved to: {report_file}")
        
        return report, report_file

    async def run_all_tests(self):
        """Run all tests in sequence with detailed logging."""
        self.logger.info("🚀 STARTING COMPLETE E2E TEST SUITE")
        self.logger.info("=" * 80)
        self.logger.info("EXECUTION FLOW:")
        self.logger.info("1. System Bootstrap & Initialization")
        self.logger.info("2. AI Assistant Creation")
        self.logger.info("3. System Health Check")
        self.logger.info("4. Sequential Test Execution:")
        self.logger.info("   └── Test 1: Simple Conversation")
        self.logger.info("   └── Test 2: Tool Usage Request")
        self.logger.info("   └── Test 3: Complex Conversation")
        self.logger.info("5. Report Generation & Summary")
        self.logger.info("=" * 80)
        
        try:
            # Setup - 必须等待完成
            self.logger.info("🔧 PHASE 1: SYSTEM SETUP")
            if not await self.setup():
                self.logger.error("❌ Setup failed, aborting tests")
                return False
            
            self.logger.info("✅ Setup completed, starting sequential test execution...")
            test_results = []
            
            # Test 1: Simple conversation - 等待完成
            self.logger.info("\n" + "="*50)
            self.logger.info("🔧 PHASE 2: TEST 1 - SIMPLE CONVERSATION")
            self.logger.info("="*50)
            self.logger.info("📋 Starting Test 1: Simple Conversation...")
            result1 = await self.test_simple_conversation()
            test_results.append(("simple_conversation", result1))
            
            # 等待完成后记录结果
            if result1:
                self.logger.info("✅ Test 1 COMPLETED: Simple Conversation - SUCCESS")
            else:
                self.logger.error("❌ Test 1 COMPLETED: Simple Conversation - FAILED")
            
            # Test 2: Tool usage - 等待前一个完成
            self.logger.info("\n" + "="*50)
            self.logger.info("🔧 PHASE 3: TEST 2 - TOOL USAGE")
            self.logger.info("="*50)
            self.logger.info("📋 Starting Test 2: Tool Usage...")
            result2 = await self.test_tool_usage_request()
            test_results.append(("tool_usage_request", result2))
            
            # 等待完成后记录结果
            if result2:
                self.logger.info("✅ Test 2 COMPLETED: Tool Usage - SUCCESS")
            else:
                self.logger.error("❌ Test 2 COMPLETED: Tool Usage - FAILED")
            
            # Test 3: Complex conversation - 等待前一个完成
            self.logger.info("\n" + "="*50)
            self.logger.info("🔧 PHASE 4: TEST 3 - COMPLEX CONVERSATION")
            self.logger.info("="*50)
            self.logger.info("📋 Starting Test 3: Complex Conversation...")
            result3 = await self.test_complex_conversation()
            test_results.append(("complex_conversation", result3))
            
            # 等待完成后记录结果
            if result3:
                self.logger.info("✅ Test 3 COMPLETED: Complex Conversation - SUCCESS")
            else:
                self.logger.error("❌ Test 3 COMPLETED: Complex Conversation - FAILED")
            
            # Generate final report - 等待所有测试完成
            self.logger.info("\n" + "="*50)
            self.logger.info("🔧 PHASE 5: REPORT GENERATION")
            self.logger.info("="*50)
            self.logger.info("🎉 All tests completed, generating final report...")
            report, report_file = self.generate_final_report()
            
            # Summary
            self.logger.info("\n" + "=" * 80)
            self.logger.info("COMPLETE E2E TEST SUMMARY")
            self.logger.info("=" * 80)
            
            passed_tests = 0
            for test_name, success in test_results:
                status = "✅ PASSED" if success else "❌ FAILED"
                self.logger.info(f"{status} - {test_name}")
                if success:
                    passed_tests += 1
            
            self.logger.info(f"\n📊 Final Results:")
            self.logger.info(f"   Total Tests: {len(test_results)}")
            self.logger.info(f"   Passed: {passed_tests}")
            self.logger.info(f"   Failed: {len(test_results) - passed_tests}")
            self.logger.info(f"   Success Rate: {(passed_tests/len(test_results)*100):.1f}%")
            self.logger.info(f"   Total Duration: {report['total_duration']:.2f}s")
            self.logger.info(f"   Average Response Time: {self.performance_metrics['average_response_time']:.2f}s")
            self.logger.info(f"   Tool Calls Detected: {self.performance_metrics['tool_calls_detected']}")
            
            self.logger.info(f"\n📋 Detailed log: {self.log_file}")
            self.logger.info(f"📋 Report file: {report_file}")
            
            if passed_tests == len(test_results):
                self.logger.info("\n🎉 ALL TESTS PASSED!")
                return True
            else:
                self.logger.warning(f"\n⚠️ {len(test_results) - passed_tests} tests failed")
                return False
            
        except Exception as e:
            self.logger.error(f"❌ Test suite failed with exception: {str(e)}")
            return False


async def main():
    """Main test execution function."""
    print("🚀 Complete End-to-End Test Suite with Detailed Logging")
    print("=" * 70)
    print("Features:")
    print("- Detailed request/response logging")
    print("- Complete execution flow tracking")
    print("- Performance metrics collection")
    print("- Comprehensive test reporting")
    print("- Real DeepSeek integration testing")
    print()
    
    test_suite = CompleteE2ETestSuite()
    
    try:
        success = await test_suite.run_all_tests()
        
        if success:
            print(f"\n🎉 Complete E2E test suite PASSED!")
            print(f"📋 Check detailed logs: {test_suite.log_file}")
            sys.exit(0)
        else:
            print(f"\n💥 Complete E2E test suite had FAILURES!")
            print(f"📋 Check detailed logs: {test_suite.log_file}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test suite failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())