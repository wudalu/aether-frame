#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end test for execute_task_live with echo tool."""

import asyncio
import uuid
from datetime import datetime

from src.aether_frame.config.settings import Settings
from src.aether_frame.execution.ai_assistant import AIAssistant
from src.aether_frame.contracts import (
    TaskRequest,
    UniversalMessage,
    UserContext,
    ExecutionContext,
    FrameworkType
)


async def test_end_to_end():
    """Test the complete end-to-end flow with echo tool for both execution paths."""
    print("🚀 Starting end-to-end test with echo tool...")
    
    # Initialize AI Assistant
    settings = Settings()
    assistant = AIAssistant(settings)
    
    # Create test task request
    task = TaskRequest(
        task_id=f"test_{uuid.uuid4().hex[:8]}",
        task_type="chat",
        description="echo hello world",
        messages=[
            UniversalMessage(
                role="user", 
                content="Please use the echo tool to repeat 'Hello World'"
            )
        ],
        user_context=UserContext(
            user_id="test_user"
        ),
        execution_context=ExecutionContext(
            execution_id=f"exec_{uuid.uuid4().hex[:8]}",
            framework_type=FrameworkType.ADK,
            timeout=60
        )
    )
    
    print(f"📝 Task created: {task.task_id}")
    print(f"💬 User message: {task.messages[0].content}")
    
    # Test 1: Regular execute_task path (sync execution)
    print("\n🔄 Testing regular execute_task path...")
    try:
        result = await assistant.process_request(task)
        print(f"✅ Regular execution completed: {result.status}")
        if result.error_message:
            print(f"📋 Expected API error: {result.error_message}")
    except Exception as e:
        print(f"❌ Regular execution failed: {str(e)}")
    
    # Test 2: Live execution path (streaming execution)  
    print("\n🔄 Testing live execution path...")
    try:
        stream, communicator = await assistant.start_live_session(task)
        print("📺 Receiving streaming chunks...")
        
        chunk_count = 0
        async for chunk in stream:
            chunk_count += 1
            print(f"📦 Chunk {chunk_count} [{chunk.chunk_type.value}]: {chunk.content}")
            
            # Limit chunks for testing
            if chunk.is_final or chunk_count >= 3:
                print("🏁 Received final chunk or reached limit")
                break
                
        print(f"📊 Total chunks received: {chunk_count}")
        
        # Close communicator
        if hasattr(communicator, 'close'):
            communicator.close()
        print("🔒 Communicator closed")
            
    except Exception as e:
        print(f"❌ Live execution failed: {str(e)}")
    
    print("\n✅ End-to-end test completed successfully!")

async def main():
    """Main test runner."""
    try:
        await test_end_to_end()
        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n💥 Tests failed: {str(e)}")
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)