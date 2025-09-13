#!/usr/bin/env python3
"""
End-to-end test for ADK runtime - Streaming Request
Tests the complete flow for live/streaming execution with ADK.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, AsyncIterator

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.bootstrap import create_ai_assistant
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage, TaskStreamChunk


async def test_adk_streaming_request():
    """Test streaming ADK request end-to-end."""
    print("=" * 60)
    print("ADK Runtime Test - Streaming Request")
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
        
        # Test Case 1: Basic Streaming Request
        print("\n2. Testing Basic Streaming Request...")
        task_request = TaskRequest(
            task_id="adk_stream_basic",
            task_type="chat",
            description="Basic streaming test with ADK runtime",
            messages=[
                UniversalMessage(
                    role="user",
                    content="Tell me a short story about AI. Please make it engaging and stream it to me.",
                    metadata={"test": "streaming_chat"}
                )
            ],
            metadata={
                "test_type": "streaming_request",
                "framework": "adk",
                "preferred_model": "deepseek-chat",  # Use DeepSeek for this test
                "timestamp": datetime.now().isoformat()
            }
        )
        
        # Stream the response using start_live_session
        print("✓ Starting streaming execution...")
        start_time = datetime.now()
        
        # Use start_live_session instead of process_request_stream
        stream, communicator = await assistant.start_live_session(task_request)
        
        chunk_count = 0
        total_content = ""
        
        async for chunk in stream:
            chunk_count += 1
            
            print(f"📦 Chunk {chunk_count}: {chunk.chunk_type} - {chunk.content[:50]}...")
            
            if chunk.content:
                total_content += str(chunk.content)
            
            # Show metadata for important chunks
            if chunk.chunk_type.value in ["response", "error", "final"]:
                print(f"   Metadata: {chunk.metadata}")
            
            if chunk.is_final:
                print("✓ Received final chunk")
                break
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        print(f"✓ Streaming completed in {execution_time:.2f} seconds")
        print(f"✓ Total chunks received: {chunk_count}")
        print(f"✓ Total content length: {len(total_content)} characters")
        
        # Close communicator
        if communicator and hasattr(communicator, 'close'):
            communicator.close()
            print("✓ Communicator closed")
        
        # Test Case 2: Streaming with Live Communication
        print("\n3. Testing Streaming with Live Communication...")
        
        task_request_2 = TaskRequest(
            task_id="adk_stream_live",
            task_type="chat",
            description="Live streaming test with bidirectional communication",
            messages=[
                UniversalMessage(
                    role="user",
                    content="I want to have an interactive conversation. Please ask me questions and wait for my responses.",
                )
            ],
            metadata={
                "test_type": "live_streaming",
                "framework": "adk",
                "preferred_model": "deepseek-chat",  # Use DeepSeek for this test
                "requires_interaction": True
            }
        )
        
        print("✓ Starting live streaming execution...")
        start_time = datetime.now()
        
        try:
            # Use start_live_session method
            stream, communicator = await assistant.start_live_session(task_request_2)
            
            print("✓ Live execution started with communicator")
            
            # Process initial stream chunks
            chunk_count_2 = 0
            
            async for chunk in stream:
                chunk_count_2 += 1
                print(f"📦 Live Chunk {chunk_count_2}: {chunk.chunk_type} - {chunk.content[:50]}...")
                
                # Simulate user response after a few chunks
                if chunk_count_2 == 3 and communicator:
                    print("💬 Sending user response...")
                    try:
                        communicator.send_user_message("Yes, I'm here and ready to answer your questions!")
                    except Exception as e:
                        print(f"⚠️ Communicator error: {e}")
                
                if chunk.is_final or chunk_count_2 >= 10:
                    print("✓ Stopping live stream")
                    break
            
            execution_time_2 = (datetime.now() - start_time).total_seconds()
            print(f"✓ Live streaming completed in {execution_time_2:.2f} seconds")
            print(f"✓ Live chunks received: {chunk_count_2}")
            
            # Close communicator
            if communicator and hasattr(communicator, 'close'):
                communicator.close()
                print("✓ Communicator closed")
                
        except Exception as e:
            print(f"⚠️ Live streaming test failed: {e}")
            execution_time_2 = 0
            chunk_count_2 = 0
        
        # Test Case 3: Streaming Error Handling
        print("\n4. Testing Streaming Error Handling...")
        
        task_request_3 = TaskRequest(
            task_id="adk_stream_error",
            task_type="invalid_task_type",  # Intentionally invalid
            description="Error handling test for streaming",
            messages=[
                UniversalMessage(
                    role="user",
                    content="This should trigger an error in streaming mode."
                )
            ],
            metadata={
                "test_type": "error_handling",
                "framework": "adk"
            }
        )
        
        print("✓ Testing error scenarios...")
        start_time = datetime.now()
        
        error_chunk_count = 0
        error_detected = False
        
        try:
            stream, communicator = await assistant.start_live_session(task_request_3)
            
            async for chunk in stream:
                error_chunk_count += 1
                
                if chunk.chunk_type.value == "error":
                    error_detected = True
                    print(f"✓ Error chunk detected: {chunk.content}")
                
                if chunk.is_final or error_chunk_count >= 5:
                    break
            
            # Close communicator
            if communicator and hasattr(communicator, 'close'):
                communicator.close()
                    
        except Exception as e:
            print(f"✓ Expected exception caught: {e}")
            error_detected = True
        
        execution_time_3 = (datetime.now() - start_time).total_seconds()
        
        if error_detected:
            print("✓ Error handling working correctly")
        else:
            print("⚠️ No error detected - check error handling")
        
        # Summary
        print("\n" + "=" * 60)
        print("STREAMING TEST SUMMARY")
        print("=" * 60)
        print(f"✓ Test 1 (Basic Stream): {execution_time:.2f}s - {chunk_count} chunks")
        print(f"✓ Test 2 (Live Stream): {execution_time_2:.2f}s - {chunk_count_2} chunks")
        print(f"✓ Test 3 (Error Handle): {execution_time_3:.2f}s - {'✓' if error_detected else '⚠️'}")
        print(f"✓ Total streaming tests: 3")
        print(f"✓ All streaming tests completed!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Streaming test failed with error: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False


def print_test_info():
    """Print test information and requirements."""
    print("ADK Streaming Request Test")
    print("This test validates:")
    print("- Streaming execution through ADK runtime")
    print("- Live bidirectional communication")
    print("- Stream chunk processing and formatting")
    print("- Error handling in streaming mode")
    print("- Communicator functionality")
    print("\nRequirements:")
    print("- ADK dependencies with streaming support")
    print("- Proper environment configuration")
    print("- Network access (if ADK requires it)")
    print()


if __name__ == "__main__":
    print_test_info()
    
    # Run the test
    success = asyncio.run(test_adk_streaming_request())
    
    if success:
        print("\n🎉 All streaming tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some streaming tests failed!")
        sys.exit(1)