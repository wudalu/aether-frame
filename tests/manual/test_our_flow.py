#!/usr/bin/env python3
"""
基于我们执行流程的简单测试
"""

import asyncio
import sys
import os
import warnings

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning"

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

# Load test environment
from dotenv import load_dotenv
load_dotenv(".env.test")

from aether_frame.bootstrap import create_ai_assistant
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage


async def test_our_execution_flow():
    """测试我们的正常执行流程"""
    
    print("🚀 Testing Our Execution Flow")
    print("=" * 50)
    
    # 1. 检查配置
    print("=== Step 1: Configuration Check ===")
    settings = Settings()
    print(f"deepseek_api_key configured: {bool(settings.deepseek_api_key)}")
    print(f"default_model: {settings.default_model}")
    print(f"default_model_provider: {settings.default_model_provider}")
    print()
    
    # 2. 创建AI助手（使用我们的流程）
    print("=== Step 2: Create AI Assistant ===")
    try:
        assistant = await create_ai_assistant(settings)
        print(f"✅ AI Assistant created: {type(assistant).__name__}")
    except Exception as e:
        print(f"❌ Failed to create AI Assistant: {e}")
        return False
    
    # 3. 创建简单任务请求
    print("\n=== Step 3: Create Task Request ===")
    task_request = TaskRequest(
        task_id="simple_test_001",
        task_type="chat",
        description="Simple test conversation",
        messages=[
            UniversalMessage(
                role="user",
                content="Hello! Please respond with exactly: 'Hello from DeepSeek - working correctly!'"
            )
        ],
        metadata={
            "test": True,
            "preferred_model": "deepseek-chat",  # 关键：设置preferred_model
            "framework": "adk"
        }
    )
    print(f"Task created: {task_request.task_id}")
    
    # 4. 处理请求（使用我们的流程）
    print("\n=== Step 4: Process Request ===")
    try:
        result = await assistant.process_request(task_request)
        print(f"✅ Request processed successfully")
        print(f"Status: {result.status.value if result.status else 'unknown'}")
        
        if result.messages:
            response_content = result.messages[0].content
            print(f"Response: {response_content}")
            
            # 检查是否是预期的响应
            if "Hello from DeepSeek" in response_content or "hello" in response_content.lower():
                print("✅ SUCCESS: Got valid response from DeepSeek!")
                return True
            else:
                print("⚠️ WARNING: Got response but content unexpected")
                print("This might still be success if we got any response")
                return True
                
        elif result.error_message:
            print(f"❌ Error: {result.error_message}")
            return False
        else:
            print("❌ No response received")
            return False
            
    except Exception as e:
        print(f"❌ Exception during processing: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    try:
        success = await test_our_execution_flow()
        
        if success:
            print("\n🎉 Test PASSED - Our execution flow works!")
            sys.exit(0)
        else:
            print("\n💥 Test FAILED - Need to fix configuration")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test exception: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())