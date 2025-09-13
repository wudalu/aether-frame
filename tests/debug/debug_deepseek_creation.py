#!/usr/bin/env python3
"""
Debug DeepSeek ADK Agent Creation
Tests the actual ADK agent creation with DeepSeek model to verify integration.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.bootstrap import create_ai_assistant
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, UniversalMessage, AgentConfig, FrameworkType


async def debug_deepseek_agent_creation():
    """Debug the DeepSeek agent creation process."""
    print("=" * 60)
    print("DeepSeek ADK Agent Creation Debug")
    print("=" * 60)
    
    try:
        # Initialize system
        print("\n1. Initializing system...")
        settings = Settings()
        print(f"   Settings loaded: {settings.default_model}")
        
        assistant = await create_ai_assistant(settings)
        print("   ✓ Assistant initialized")
        
        # Create agent config with explicit DeepSeek model
        print("\n2. Creating agent config with DeepSeek model...")
        agent_config = AgentConfig(
            agent_type="conversational_agent",
            framework_type=FrameworkType.ADK,
            model_config={"model": "deepseek-chat"},
            system_prompt="You are a helpful assistant using DeepSeek.",
        )
        print(f"   ✓ Agent config: {agent_config.model_config}")
        
        # Create task request with preferred model in metadata
        task_request = TaskRequest(
            task_id="deepseek_debug",
            task_type="chat",
            description="Debug DeepSeek agent creation",
            messages=[
                UniversalMessage(
                    role="user",
                    content="What model are you using?",
                )
            ],
            metadata={
                "test_type": "debug",
                "preferred_model": "deepseek-chat"  # This is the correct field
            }
        )
        
        print("\n3. Processing request to trigger agent creation...")
        
        # Enable debug mode to see what's happening
        import logging
        logging.basicConfig(level=logging.DEBUG)
        
        result = await assistant.process_request(task_request)
        
        print(f"\n4. Result analysis:")
        print(f"   Status: {result.status}")
        print(f"   Error: {result.error_message}")
        print(f"   Metadata: {result.metadata}")
        
        # Try to access the created agent directly
        print("\n5. Checking agent manager state...")
        agent_manager = assistant.agent_manager
        if hasattr(agent_manager, '_agents'):
            print(f"   Active agents: {list(agent_manager._agents.keys())}")
            for agent_id, agent in agent_manager._agents.items():
                print(f"   Agent {agent_id}: {type(agent)}")
                if hasattr(agent, 'adk_agent') and agent.adk_agent:
                    print(f"     ADK Agent model: {getattr(agent.adk_agent, 'model', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Debug failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("DeepSeek ADK Agent Creation Debug")
    print("This debug session investigates:")
    print("- Agent creation process with DeepSeek model")
    print("- Model configuration flow")
    print("- Actual ADK agent model usage")
    print()
    
    success = asyncio.run(debug_deepseek_agent_creation())
    
    if success:
        print("\n🔍 Debug completed!")
    else:
        print("\n💥 Debug failed!")
    
    sys.exit(0 if success else 1)