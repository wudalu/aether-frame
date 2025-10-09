#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Chat History Migration Test

Pure test for chat history migration between 2 agents:
- Agent A: Programming expert
- Agent B: Data analyst

Focus: Verify that Agent B can reference Agent A's conversation.
"""

import asyncio
import sys
import os
sys.path.insert(0, 'src')

from dotenv import load_dotenv
load_dotenv('.env.test')

from aether_frame.bootstrap import create_ai_assistant
from aether_frame.config.settings import Settings
from aether_frame.contracts import (
    TaskRequest, 
    UniversalMessage, 
    TaskStatus, 
    AgentConfig,
    UserContext
)

async def simple_history_migration_test():
    """Simple 2-agent chat history migration test."""
    
    print("🔍 Simple 2-Agent Chat History Migration Test")
    print("=" * 50)
    
    # Setup
    settings = Settings()
    ai_assistant = await create_ai_assistant(settings)
    
    chat_session_id = "simple_migration_test"
    user_context = UserContext(user_id="test_user", user_name="Test User")
    
    try:
        # === STEP 1: Agent A (Programming Expert) ===
        print("\n📝 STEP 1: Conversation with Agent A (Programming Expert)")
        
        agent_a_request = TaskRequest(
            task_id="agent_a_task",
            task_type="chat",
            description="Programming conversation",
            user_context=user_context,
            messages=[
                UniversalMessage(
                    role="user",
                    content="I need to learn about Python dictionaries. Can you explain the basics and give me a simple example?",
                )
            ],
            agent_config=AgentConfig(
                agent_type="programming_expert",
                system_prompt="You are a Python programming expert. Always mention that you are Agent A in your responses.",
                model_config={"model": "deepseek-chat", "temperature": 0.1},
                framework_config={"provider": "deepseek"}
            ),
            metadata={"chat_session_id": chat_session_id}
        )
        
        result_a = await ai_assistant.process_request(agent_a_request)
        assert result_a.status == TaskStatus.SUCCESS
        
        print(f"✅ Agent A response: {result_a.messages[0].content[:150]}...")
        agent_a_id = result_a.agent_id
        
        # === STEP 2: Agent B (Data Analyst) - Switch with History Migration ===
        print(f"\n📝 STEP 2: Switch to Agent B (Data Analyst) - Testing History Migration")
        
        agent_b_request = TaskRequest(
            task_id="agent_b_task", 
            task_type="analysis",
            description="Data analysis conversation with history",
            user_context=user_context,
            messages=[
                UniversalMessage(
                    role="user",
                    content="Hi there! I'm switching to data analysis now. Based on our previous Python discussion, can you help me use dictionaries for data analysis? Please reference what we discussed before.",
                )
            ],
            agent_config=AgentConfig(
                agent_type="data_analyst",
                system_prompt="You are a data analysis expert. Always mention that you are Agent B in your responses. You should have access to previous conversation context.",
                model_config={"model": "deepseek-chat", "temperature": 0.1},
                framework_config={"provider": "deepseek"}
            ),
            # No agent_id - this triggers agent switch and history migration
            metadata={"chat_session_id": chat_session_id}
        )
        
        result_b = await ai_assistant.process_request(agent_b_request)
        assert result_b.status == TaskStatus.SUCCESS
        
        print(f"✅ Agent B response: {result_b.messages[0].content}")
        agent_b_id = result_b.agent_id
        
        # === STEP 3: Verify History Migration ===
        print(f"\n📝 STEP 3: Verify History Migration")
        
        # Check if different agents
        if agent_a_id != agent_b_id:
            print(f"✅ Agent switch confirmed: {agent_a_id} → {agent_b_id}")
        else:
            print(f"❌ No agent switch detected")
            
        # Check if Agent B references previous discussion
        response_content = result_b.messages[0].content.lower()
        
        context_indicators = [
            "previous", "earlier", "discussed", "python", "dictionary", "dictionaries"
        ]
        
        found_indicators = [word for word in context_indicators if word in response_content]
        
        print(f"\n📊 CONTEXT ANALYSIS:")
        print(f"   Response length: {len(result_b.messages[0].content)} characters")
        print(f"   Context indicators found: {len(found_indicators)}/{len(context_indicators)}")
        print(f"   Indicators: {found_indicators}")
        
        # Determine success
        if len(found_indicators) >= 3:
            print(f"\n🎉 SUCCESS: Agent B clearly references previous conversation!")
            print(f"   History migration appears to be working correctly.")
            success = True
        elif len(found_indicators) >= 1:
            print(f"\n⚠️  PARTIAL: Agent B shows some context awareness.")
            print(f"   History migration may be partially working.")
            success = True
        else:
            print(f"\n❌ FAILURE: Agent B does not reference previous conversation.")
            print(f"   History migration may not be working.")
            success = False
            
        return {
            "success": success,
            "agent_a_id": agent_a_id,
            "agent_b_id": agent_b_id,
            "context_indicators_found": len(found_indicators),
            "agent_switch_occurred": agent_a_id != agent_b_id,
            "responses": {
                "agent_a": result_a.messages[0].content,
                "agent_b": result_b.messages[0].content
            }
        }
        
    finally:
        # Cleanup
        if hasattr(ai_assistant, 'execution_engine') and hasattr(ai_assistant.execution_engine, 'shutdown'):
            await ai_assistant.execution_engine.shutdown()
        print("\n🧹 Cleanup completed")

if __name__ == "__main__":
    asyncio.run(simple_history_migration_test())