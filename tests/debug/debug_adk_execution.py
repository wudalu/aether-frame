#!/usr/bin/env python3
"""
Debug ADK execution to understand why no response messages are returned.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.bootstrap import create_ai_assistant
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage, TaskStatus


async def debug_adk_execution():
    """Debug ADK execution in detail."""
    print("=" * 60)
    print("ADK Runtime Debug Test")
    print("=" * 60)
    
    # Setup detailed logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    try:
        # Initialize AI Assistant
        print("\n1. Initializing AI Assistant...")
        settings = Settings()
        assistant = await create_ai_assistant(settings)
        print("✓ AI Assistant initialized")
        
        # Create a simple test request
        print("\n2. Creating test request...")
        task_request = TaskRequest(
            task_id="debug_test",
            task_type="chat",
            description="Debug test request",
            messages=[
                UniversalMessage(
                    role="user",
                    content="Say 'Hello World' back to me.",
                    metadata={"debug": True}
                )
            ],
            metadata={
                "test_type": "debug",
                "framework": "adk"
            }
        )
        print("✓ Test request created")
        
        # Process the request with detailed logging
        print("\n3. Processing request...")
        start_time = datetime.now()
        result = await assistant.process_request(task_request)
        execution_time = (datetime.now() - start_time).total_seconds()
        
        print(f"\n4. Results:")
        print(f"   Execution time: {execution_time:.3f} seconds")
        print(f"   Task status: {result.status}")
        print(f"   Task ID: {result.task_id}")
        
        if result.error_message:
            print(f"   Error: {result.error_message}")
        
        if result.result_data:
            print(f"   Result data: {result.result_data}")
        
        if result.messages:
            print(f"   Response messages ({len(result.messages)}):")
            for i, msg in enumerate(result.messages):
                print(f"     [{i}] Role: {msg.role}")
                print(f"     [{i}] Content: {msg.content}")
                print(f"     [{i}] Metadata: {msg.metadata}")
        else:
            print("   ⚠️ No response messages!")
        
        if result.metadata:
            print(f"   Result metadata: {result.metadata}")
        
        # Check if this looks like mock execution
        if execution_time < 0.01:
            print("\n⚠️ SUSPICIOUS: Execution time is very short (< 10ms)")
            print("   This suggests mock execution rather than real ADK calls")
        
        if result.status == TaskStatus.SUCCESS and not result.messages:
            print("\n⚠️ SUSPICIOUS: Success status but no messages")
            print("   This suggests successful mock execution")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Debug test failed: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(debug_adk_execution())
    
    if result:
        print(f"\n{'='*60}")
        print("DEBUG SUMMARY")
        print(f"{'='*60}")
        
        if result.status == TaskStatus.SUCCESS:
            if result.messages and len(result.messages) > 0:
                print("✅ SUCCESS: ADK execution appears to be working!")
            else:
                print("🔍 PARTIAL: Execution succeeded but no response content")
                print("   → This indicates mock execution or missing response processing")
        else:
            print("❌ FAILED: ADK execution failed")
    else:
        print("💥 DEBUG TEST FAILED!")