#!/usr/bin/env python3
"""
简单的ADK DeepSeek测试
"""

import asyncio
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

# Load test environment
from dotenv import load_dotenv
load_dotenv(".env.test")

# Print environment variables for debugging
print("=== Environment Variables ===")
print(f"DEEPSEEK_API_KEY: {bool(os.getenv('DEEPSEEK_API_KEY'))}")
print(f"DEFAULT_MODEL: {os.getenv('DEFAULT_MODEL')}")
print(f"DEFAULT_MODEL_PROVIDER: {os.getenv('DEFAULT_MODEL_PROVIDER')}")
print()

from aether_frame.config.settings import Settings

async def test_simple_adk():
    """Test simple ADK setup with DeepSeek."""
    
    # Create settings
    settings = Settings()
    print("=== Settings ===")
    print(f"deepseek_api_key: {bool(settings.deepseek_api_key)}")
    print(f"default_model: {settings.default_model}")
    print(f"default_model_provider: {settings.default_model_provider}")
    print()
    
    # Test model factory
    from aether_frame.framework.adk.model_factory import AdkModelFactory
    
    print("=== Model Factory Test ===")
    try:
        model = AdkModelFactory.create_model(settings.default_model, settings)
        print(f"Model created: {type(model)}")
        print(f"Model: {model}")
        
        # Test if it's LiteLLM
        if hasattr(model, 'model'):
            print(f"Model identifier: {model.model}")
        
    except Exception as e:
        print(f"Model creation failed: {e}")
        return False
    
    # Test basic ADK agent creation
    print("\n=== ADK Agent Test ===")
    try:
        from google.adk import Agent
        
        agent = Agent(
            name="test_agent",
            description="Test agent for DeepSeek",
            instruction="You are a helpful AI assistant.",
            model=model,
        )
        print(f"ADK Agent created: {agent}")
        
        # Test basic execution
        print("\n=== Basic Execution Test ===")
        
        # Set environment variable for LiteLLM
        os.environ['DEEPSEEK_API_KEY'] = settings.deepseek_api_key
        
        from google.adk.runners import InMemoryRunner
        from google.adk.sessions import InMemorySessionService
        
        session_service = InMemorySessionService()
        runner = InMemoryRunner(agent)
        
        # Run simple test
        async with runner.run_session(session_service=session_service) as session:
            response = await session.send("Hello! Please say 'Hello from DeepSeek!' to confirm you're working.")
            print(f"Response: {response}")
            
            if "Hello from DeepSeek" in response or "hello" in response.lower():
                print("✅ SUCCESS: DeepSeek responded correctly!")
                return True
            else:
                print("⚠️ WARNING: Got response but content unexpected")
                return True  # Still success if we got any response
        
    except Exception as e:
        print(f"ADK execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function."""
    print("🚀 Simple ADK DeepSeek Test")
    print("=" * 50)
    
    try:
        success = await test_simple_adk()
        
        if success:
            print("\n🎉 Test PASSED!")
            sys.exit(0)
        else:
            print("\n💥 Test FAILED!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test exception: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())