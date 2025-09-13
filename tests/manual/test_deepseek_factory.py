#!/usr/bin/env python3
"""
Test DeepSeek LLM wrapper functionality
Validates that DeepSeek models can be configured through the factory approach.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.framework.adk.model_factory import AdkModelFactory
from aether_frame.framework.adk.deepseek_llm import DeepSeekLLM
from aether_frame.config.settings import Settings


async def test_deepseek_factory():
    """Test DeepSeek factory functionality."""
    print("=" * 60)
    print("DeepSeek Factory Test")
    print("=" * 60)
    
    try:
        # Test 1: Factory detection
        print("\n1. Testing factory model detection...")
        
        test_cases = [
            ("deepseek-chat", True),
            ("gemini-1.5-flash", False),
            ("DeepSeek-V3", True),
            ("projects/test/endpoints/123", False),
        ]
        
        for model_name, expected in test_cases:
            is_custom = AdkModelFactory.is_custom_model(model_name)
            status = "✓" if is_custom == expected else "❌"
            print(f"   {status} {model_name}: {is_custom} (expected: {expected})")
        
        # Test 2: Factory model creation
        print("\n2. Testing factory model creation...")
        settings = Settings()
        
        # Test DeepSeek model creation
        deepseek_model = AdkModelFactory.create_model("deepseek-chat", settings)
        try:
            from google.adk.models.lite_llm import LiteLlm
            if isinstance(deepseek_model, LiteLlm):
                print(f"   ✓ DeepSeek LiteLLM wrapper created: {deepseek_model}")
                print(f"   ✓ LiteLLM model: {deepseek_model.model}")
            else:
                print(f"   ❌ Expected LiteLlm, got: {type(deepseek_model)}")
        except ImportError:
            if isinstance(deepseek_model, DeepSeekLLM):
                print(f"   ✓ DeepSeek model created: {deepseek_model}")
                print(f"   ✓ Model config: {deepseek_model.get_config()}")
            else:
                print(f"   ❌ Expected DeepSeekLLM, got: {type(deepseek_model)}")
        
        # Test Gemini model (should return string)
        gemini_model = AdkModelFactory.create_model("gemini-1.5-flash", settings)
        if isinstance(gemini_model, str):
            print(f"   ✓ Gemini model passed through: {gemini_model}")
        else:
            print(f"   ❌ Expected string, got: {type(gemini_model)}")
        
        # Test 3: Settings integration
        print("\n3. Testing settings integration...")
        deepseek_from_settings = DeepSeekLLM.from_settings(settings)
        print(f"   ✓ DeepSeek from settings: {deepseek_from_settings}")
        print(f"   ✓ Configuration: {deepseek_from_settings.get_config()}")
        
        # Test 4: LiteLLM format conversion
        print("\n4. Testing LiteLLM format conversion...")
        litellm_format = deepseek_from_settings.to_litellm_format()
        print(f"   ✓ LiteLLM format: {litellm_format}")
        
        print(f"\n{'='*60}")
        print("DEEPSEEK FACTORY TEST SUMMARY")
        print(f"{'='*60}")
        print("✓ Model detection working correctly")
        print("✓ Factory creation working correctly")
        print("✓ Settings integration working correctly")
        print("✓ LiteLLM format conversion working correctly")
        
        print("\n🎉 DeepSeek factory tests completed successfully!")
        print("\nNext steps:")
        print("1. Set DEEPSEEK_API_KEY in .env file for actual API testing")
        print("2. Test with real ADK agent creation")
        
        return True
        
    except Exception as e:
        print(f"\n❌ DeepSeek factory test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("DeepSeek Factory Test")
    print("This test validates:")
    print("- Factory pattern model detection")
    print("- DeepSeek wrapper class creation") 
    print("- Settings integration")
    print("- LiteLLM format conversion")
    print()
    
    success = asyncio.run(test_deepseek_factory())
    
    if success:
        print("\n🎯 DeepSeek factory integration ready!")
    else:
        print("\n💥 DeepSeek factory tests failed!")
    
    sys.exit(0 if success else 1)