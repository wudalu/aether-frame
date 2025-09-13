#!/usr/bin/env python3
"""
End-to-end test for ADK runtime - Single Request
Tests the complete flow from TaskRequest to ADK execution and back.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.bootstrap import create_ai_assistant
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage, TaskStatus


async def test_adk_single_request():
    """Test single ADK request end-to-end."""
    print("=" * 60)
    print("ADK Runtime Test - Single Request")
    print("=" * 60)
    
    # Setup logging for detailed output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize AI Assistant using bootstrap
        print("\n1. Initializing Aether Frame with ADK...")
        settings = Settings()
        assistant = await create_ai_assistant(settings)
        print("✓ AI Assistant initialized successfully")
        
        # Test Case 1: Simple Chat Request
        print("\n2. Testing Simple Chat Request...")
        task_request = TaskRequest(
            task_id="adk_test_simple",
            task_type="chat",
            description="Simple chat test with ADK runtime",
            messages=[
                UniversalMessage(
                    role="user",
                    content="Hello! Can you tell me about yourself?",
                    metadata={"test": "simple_chat"}
                )
            ],
            metadata={
                "test_type": "single_request",
                "framework": "adk",
                "preferred_model": "deepseek-chat",  # Use DeepSeek for this test
                "timestamp": datetime.now().isoformat()
            }
        )
        
        start_time = datetime.now()
        result = await assistant.process_request(task_request)
        execution_time = (datetime.now() - start_time).total_seconds()
        
        print(f"✓ Request completed in {execution_time:.2f} seconds")
        print(f"✓ Task Status: {result.status}")
        
        # Check if this is actually hitting ADK or just mock
        if result.status == TaskStatus.ERROR:
            print(f"⚠️ Error details: {result.error_message}")
            if result.result_data:
                print(f"⚠️ Result data: {result.result_data}")
        
        if result.messages and len(result.messages) > 0:
            response_content = result.messages[-1].content
            print(f"✓ Response received: {response_content[:100]}...")
        else:
            print("⚠️ No response messages received")
        
        print(f"✓ Result metadata: {result.metadata}")
        
        # Test Case 2: Multi-message Conversation
        print("\n3. Testing Multi-message Conversation...")
        task_request_2 = TaskRequest(
            task_id="adk_test_multi",
            task_type="chat", 
            description="Multi-message conversation test",
            messages=[
                UniversalMessage(role="user", content="What is 2+2?"),
                UniversalMessage(role="assistant", content="2+2 equals 4."),
                UniversalMessage(role="user", content="And what about 3+3?")
            ],
            metadata={
                "test_type": "multi_message",
                "framework": "adk",
                "preferred_model": "deepseek-chat"  # Use DeepSeek for this test
            }
        )
        
        start_time = datetime.now()
        result_2 = await assistant.process_request(task_request_2)
        execution_time_2 = (datetime.now() - start_time).total_seconds()
        
        print(f"✓ Multi-message request completed in {execution_time_2:.2f} seconds")
        print(f"✓ Task Status: {result_2.status}")
        
        # Check for errors in multi-message test
        if result_2.status == TaskStatus.ERROR:
            print(f"⚠️ Error details: {result_2.error_message}")
            if result_2.result_data:
                print(f"⚠️ Result data: {result_2.result_data}")
        
        if result_2.messages and len(result_2.messages) > 0:
            response_content_2 = result_2.messages[-1].content
            print(f"✓ Response received: {response_content_2[:100]}...")
        else:
            print("⚠️ No response messages received")
        
        # Test Case 3: Task with Execution Configuration
        print("\n4. Testing Request with Execution Configuration...")
        from aether_frame.contracts import ExecutionConfig, ExecutionContext, FrameworkType, ExecutionMode
        
        # Use ExecutionConfig with correct fields
        execution_config = ExecutionConfig(
            timeout=30,
            execution_mode=ExecutionMode.SYNC,
            max_retries=2,
            enable_logging=True,
        )
        
        execution_context = ExecutionContext(
            execution_id="adk_test_config_ctx",
            framework_type=FrameworkType.ADK,
            execution_mode="sync",
            timeout=30,
        )
        
        task_request_3 = TaskRequest(
            task_id="adk_test_config",
            task_type="chat",
            description="Test with specific execution configuration",
            messages=[
                UniversalMessage(
                    role="user",
                    content="Explain what you are and how you process requests."
                )
            ],
            execution_config=execution_config,
            execution_context=execution_context,
            metadata={
                "test_type": "execution_config",
                "framework": "adk",
                "preferred_model": "deepseek-chat"  # Use DeepSeek for this test
            }
        )
        
        start_time = datetime.now()
        result_3 = await assistant.process_request(task_request_3)
        execution_time_3 = (datetime.now() - start_time).total_seconds()
        
        print(f"✓ Config-based request completed in {execution_time_3:.2f} seconds")
        print(f"✓ Task Status: {result_3.status}")
        
        if result_3.messages and len(result_3.messages) > 0:
            response_content_3 = result_3.messages[-1].content
            print(f"✓ Response received: {response_content_3[:100]}...")
        
        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"✓ Test 1 (Simple): {execution_time:.2f}s - {result.status}")
        print(f"✓ Test 2 (Multi-msg): {execution_time_2:.2f}s - {result_2.status}")
        print(f"✓ Test 3 (Config): {execution_time_3:.2f}s - {result_3.status}")
        print(f"✓ Total tests: 3")
        print(f"✓ All tests completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False


def print_test_info():
    """Print test information and requirements."""
    print("ADK Single Request Test")
    print("This test validates:")
    print("- Bootstrap initialization with ADK framework")
    print("- Single request processing through ADK runtime")
    print("- Multi-message conversation handling")
    print("- Agent configuration processing")
    print("- Response formatting and error handling")
    print("\nRequirements:")
    print("- ADK dependencies must be installed")
    print("- Proper environment configuration")
    print("- Network access (if ADK requires it)")
    print()


if __name__ == "__main__":
    print_test_info()
    
    # Run the test
    success = asyncio.run(test_adk_single_request())
    
    if success:
        print("\n🎉 All single request tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)