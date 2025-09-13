#!/usr/bin/env python3
"""
Simple test script for bootstrap implementation
"""
import asyncio
import os
import sys

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.bootstrap import (
    create_ai_assistant,
    create_system_components,
    health_check_system,
)
from aether_frame.contracts import TaskRequest


async def test_bootstrap():
    """Test basic bootstrap functionality"""
    print("=== Testing Aether Frame Bootstrap ===\n")

    try:
        # Test 1: System components initialization
        print("1. Testing system components initialization...")
        components = await create_system_components()

        print(f"✓ Framework Registry: {type(components.framework_registry).__name__}")
        print(f"✓ Agent Manager: {type(components.agent_manager).__name__}")
        print(f"✓ Task Router: {type(components.task_router).__name__}")
        print(f"✓ Execution Engine: {type(components.execution_engine).__name__}")
        print(
            f"✓ Tool Service: {type(components.tool_service).__name__ if components.tool_service else 'Disabled'}"
        )

        # Test 2: Health check
        print("\n2. Testing system health check...")
        health = await health_check_system(components)
        print(f"✓ Overall Status: {health['overall_status']}")

        for component, status in health["components"].items():
            print(f"  - {component}: {status.get('status', 'unknown')}")

        # Test 3: AI Assistant creation
        print("\n3. Testing AI Assistant creation...")
        assistant = await create_ai_assistant()
        print(f"✓ AI Assistant created: {type(assistant).__name__}")

        # Test 4: Basic health check
        print("\n4. Testing AI Assistant health...")
        assistant_health = await assistant.health_check()
        print(f"✓ Assistant Status: {assistant_health['status']}")
        print(f"✓ Version: {assistant_health['version']}")

        print("\n=== Bootstrap Test Completed Successfully ===")
        return True

    except Exception as e:
        print(f"\n❌ Test Failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


async def test_task_processing():
    """Test basic task processing"""
    print("\n=== Testing Task Processing ===")

    try:
        # Create assistant
        assistant = await create_ai_assistant()

        # Create simple task request
        task_request = TaskRequest(
            task_id="test_001",
            task_type="chat",
            description="Hello, this is a test message",
            metadata={"test": True},
        )

        print(f"Processing task: {task_request.description}")

        # Process the request
        result = await assistant.process_request(task_request)

        print(f"✓ Task Status: {result.status}")
        print(f"✓ Task ID: {result.task_id}")

        if result.error_message:
            print(f"⚠️  Error Message: {result.error_message}")

        print("=== Task Processing Test Completed ===")
        return True

    except Exception as e:
        print(f"❌ Task Processing Test Failed: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":

    async def main():
        print("Starting bootstrap tests...\n")

        # Test bootstrap functionality
        bootstrap_success = await test_bootstrap()

        if bootstrap_success:
            # Test task processing
            task_success = await test_task_processing()

            if task_success:
                print("\n🎉 All tests passed!")
                return 0

        print("\n💥 Some tests failed!")
        return 1

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
