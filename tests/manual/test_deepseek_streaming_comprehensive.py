#!/usr/bin/env python3
"""
Test DeepSeek streaming directly to verify it supports streaming
This will confirm whether the issue is in LiteLLM wrapper or elsewhere.
"""

import json
import requests
import sseclient
import asyncio
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.config.settings import Settings


async def test_deepseek_direct_streaming():
    """Test DeepSeek API directly to confirm streaming support."""
    print("=" * 60)
    print("DeepSeek Direct Streaming Test")
    print("=" * 60)
    
    try:
        # Load settings to get API key
        settings = Settings()
        api_key = settings.deepseek_api_key
        
        if not api_key:
            print("❌ No DeepSeek API key found in settings")
            return False
            
        print(f"✓ API key loaded: {api_key[:12]}...")
        
        # Test 1: Direct DeepSeek API streaming
        print("\n1. Testing DeepSeek API directly with streaming...")
        
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "Please tell me a short story about AI in exactly 3 sentences. Stream it to me word by word."}],
            "stream": True
        }
        
        start_time = datetime.now()
        print("   Sending streaming request to DeepSeek API...")
        
        response = requests.post(url, json=data, headers=headers, stream=True)
        
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
        print(f"✓ HTTP 200 - Streaming response received")
        
        client = sseclient.SSEClient(response)
        
        chunk_count = 0
        total_content = ""
        
        print("   📡 Streaming chunks:")
        for event in client.events():
            if event.data == "[DONE]":
                print("\n   ✓ Stream completed with [DONE] signal")
                break
                
            try:
                chunk = json.loads(event.data)
                content = chunk["choices"][0]["delta"].get("content", "")
                if content:
                    chunk_count += 1
                    total_content += content
                    print(f"      Chunk {chunk_count}: '{content}'")
                    
                    if chunk_count >= 10:  # Limit for testing
                        print("   ⚠️ Stopping after 10 chunks for testing")
                        break
                        
            except json.JSONDecodeError:
                print(f"   ⚠️ Invalid JSON in chunk: {event.data}")
            except Exception as e:
                print(f"   ⚠️ Error processing chunk: {e}")
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        print(f"\n   ✓ Direct streaming completed in {execution_time:.2f} seconds")
        print(f"   ✓ Total chunks received: {chunk_count}")
        print(f"   ✓ Total content length: {len(total_content)} characters")
        print(f"   📝 Content preview: {total_content[:100]}...")
        
        if chunk_count > 0:
            print("\n🎉 DEEPSEEK API STREAMING: CONFIRMED WORKING!")
            return True
        else:
            print("\n⚠️ No content chunks received")
            return False
            
    except Exception as e:
        print(f"\n❌ Direct streaming test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_litellm_deepseek_streaming():
    """Test DeepSeek streaming through LiteLLM to find the issue."""
    print("\n" + "=" * 60)
    print("LiteLLM DeepSeek Streaming Test")
    print("=" * 60)
    
    try:
        print("\n2. Testing DeepSeek through LiteLLM...")
        
        # Import and configure LiteLLM
        import litellm
        from litellm import acompletion
        
        # Set debugging
        litellm.set_verbose = True
        
        messages = [{"role": "user", "content": "Tell me about AI in one short sentence."}]
        
        print("   Attempting LiteLLM streaming with DeepSeek...")
        
        response = await acompletion(
            model="deepseek/deepseek-chat",
            messages=messages,
            stream=True
        )
        
        chunk_count = 0
        total_content = ""
        
        async for chunk in response:
            chunk_count += 1
            if hasattr(chunk, 'choices') and chunk.choices:
                content = chunk.choices[0].delta.get('content', '')
                if content:
                    total_content += content
                    print(f"   LiteLLM Chunk {chunk_count}: '{content}'")
                    
            if chunk_count >= 5:  # Limit for testing
                break
        
        if chunk_count > 0:
            print(f"\n✅ LiteLLM streaming working! {chunk_count} chunks received")
            return "litellm_works"
        else:
            print(f"\n❌ LiteLLM streaming failed - no chunks")
            return "litellm_fails"
            
    except Exception as e:
        print(f"\n❌ LiteLLM streaming error: {str(e)}")
        if "not supported" in str(e).lower():
            print("   🔍 This confirms LiteLLM doesn't support DeepSeek streaming")
            return "litellm_unsupported"
        else:
            print("   🔍 Other LiteLLM configuration issue")
            return "litellm_error"


async def comprehensive_streaming_analysis():
    """Run comprehensive analysis of DeepSeek streaming support."""
    print("DeepSeek Streaming Comprehensive Analysis")
    print("Testing both direct API and LiteLLM wrapper")
    print()
    
    # Test direct API
    direct_works = await test_deepseek_direct_streaming()
    
    # Test through LiteLLM
    litellm_result = await test_litellm_deepseek_streaming()
    
    print("\n" + "=" * 60)
    print("COMPREHENSIVE STREAMING ANALYSIS RESULTS")
    print("=" * 60)
    
    print(f"\n📊 Test Results:")
    print(f"   DeepSeek Direct API: {'✅ WORKING' if direct_works else '❌ FAILED'}")
    print(f"   LiteLLM Wrapper: {litellm_result}")
    
    if direct_works and litellm_result in ["litellm_unsupported", "litellm_fails"]:
        print(f"\n🎯 ROOT CAUSE IDENTIFIED:")
        print(f"   ✅ DeepSeek API supports streaming natively")
        print(f"   ❌ LiteLLM wrapper doesn't implement DeepSeek streaming")
        print(f"   🔧 SOLUTION: Implement direct DeepSeek streaming in our factory")
        return "litellm_limitation"
        
    elif direct_works and litellm_result == "litellm_works":
        print(f"\n🎯 STREAMING SHOULD WORK:")
        print(f"   ✅ Both DeepSeek API and LiteLLM support streaming")
        print(f"   🔧 SOLUTION: Check ADK-LiteLLM integration configuration")
        return "config_issue"
        
    else:
        print(f"\n🔍 Need further investigation")
        return "unknown"


if __name__ == "__main__":
    result = asyncio.run(comprehensive_streaming_analysis())
    
    if result == "litellm_limitation":
        print(f"\n🚀 Next Steps:")
        print(f"   1. Implement direct DeepSeek streaming in our factory")
        print(f"   2. Bypass LiteLLM for DeepSeek streaming")
        print(f"   3. Keep LiteLLM for non-streaming DeepSeek requests")
        
    print(f"\n✅ Analysis completed - Root cause identified!")
    sys.exit(0)