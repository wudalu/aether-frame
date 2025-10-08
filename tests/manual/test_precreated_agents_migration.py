#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-created Agents History Migration Test

Test approach:
1. Create Agent A and get its agent_id
2. Create Agent B and get its agent_id  
3. Chat with Agent A using chat_session_id
4. Chat with Agent B using the SAME chat_session_id - this should trigger history migration
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

async def test_precreated_agents_history_migration():
    """Test history migration between pre-created agents."""
    
    print("🔍 Pre-created Agents History Migration Test")
    print("=" * 50)
    
    # Setup
    settings = Settings()
    ai_assistant = await create_ai_assistant(settings)
    
    chat_session_id = "shared_chat_session"
    user_context = UserContext(user_id="test_user", user_name="Test User")
    
    try:
        # === STEP 1: Create Agent A (Content Creator) ===
        print("\n📝 STEP 1: Create Agent A (Content Creator)")
        
        create_agent_a = TaskRequest(
            task_id="create_agent_a",
            task_type="setup",
            description="Create content creator agent",
            user_context=user_context,
            messages=[
                UniversalMessage(
                    role="user",
                    content="Hello, I'm setting up a content creator agent.",
                )
            ],
            agent_config=AgentConfig(
                agent_type="content_creator",
                system_prompt="You are Agent A, a creative content creator. Always mention you are Agent A in responses.",
                model_config={"model": "deepseek-chat", "temperature": 0.1},
                framework_config={"provider": "deepseek"}
            )
        )
        
        result_a_create = await ai_assistant.process_request(create_agent_a)
        assert result_a_create.status == TaskStatus.SUCCESS
        
        agent_a_id = result_a_create.agent_id
        agent_a_session = result_a_create.session_id
        print(f"✅ Agent A created: {agent_a_id}, session: {agent_a_session}")
        
        # === STEP 2: Create Agent B (Translator) ===
        print("\n📝 STEP 2: Create Agent B (Translator)")
        
        create_agent_b = TaskRequest(
            task_id="create_agent_b",
            task_type="setup",
            description="Create translator agent",
            user_context=user_context,
            messages=[
                UniversalMessage(
                    role="user",
                    content="Hello, I'm setting up a translator agent.",
                )
            ],
            agent_config=AgentConfig(
                agent_type="translator",
                system_prompt="You are Agent B, a professional translator. Always mention you are Agent B in responses.",
                model_config={"model": "deepseek-chat", "temperature": 0.1},
                framework_config={"provider": "deepseek"}
            )
        )
        
        result_b_create = await ai_assistant.process_request(create_agent_b)
        assert result_b_create.status == TaskStatus.SUCCESS
        
        agent_b_id = result_b_create.agent_id
        agent_b_session = result_b_create.session_id
        print(f"✅ Agent B created: {agent_b_id}, session: {agent_b_session}")
        
        # === STEP 3: Chat with Agent A using shared chat_session_id ===
        print(f"\n📝 STEP 3: Chat with Agent A using shared chat_session_id: {chat_session_id}")
        
        chat_with_a = TaskRequest(
            task_id="chat_with_a",
            task_type="chat",
            description="Create content with Agent A",
            user_context=user_context,
            messages=[
                UniversalMessage(
                    role="user",
                    content="Please write exactly this sentence: 'The red dragon flies over the mountain.' Remember this sentence exactly.",
                )
            ],
            agent_id=agent_a_id,
            session_id=chat_session_id,  # Use shared chat session ID
        )
        
        result_a_chat = await ai_assistant.process_request(chat_with_a)
        assert result_a_chat.status == TaskStatus.SUCCESS
        
        agent_a_content = result_a_chat.messages[0].content
        print(f"✅ Agent A response: {agent_a_content}")
        
        # === STEP 4: Chat with Agent B using the SAME chat_session_id ===
        print(f"\n📝 STEP 4: Chat with Agent B using SAME chat_session_id: {chat_session_id}")
        print("🔍 This should trigger Session Manager coordination and history migration...")
        
        chat_with_b = TaskRequest(
            task_id="chat_with_b",
            task_type="translation",
            description="Translate with Agent B",
            user_context=user_context,
            messages=[
                UniversalMessage(
                    role="user",
                    content="Please translate the sentence I asked you to remember into Spanish. What was that exact sentence?",
                )
            ],
            agent_id=agent_b_id,
            session_id=chat_session_id,  # Same shared chat session ID
        )
        
        result_b_chat = await ai_assistant.process_request(chat_with_b)
        assert result_b_chat.status == TaskStatus.SUCCESS
        
        agent_b_response = result_b_chat.messages[0].content
        print(f"✅ Agent B response: {agent_b_response}")
        
        # === STEP 5: Analysis ===
        print(f"\n📊 ANALYSIS:")
        
        # Check for key content
        target_sentence = "The red dragon flies over the mountain"
        has_target_sentence = target_sentence.lower() in agent_b_response.lower()
        
        # Check for Spanish translation
        spanish_words = ["el", "la", "dragón", "rojo", "vuela", "sobre", "montaña", "monte"]
        found_spanish = [word for word in spanish_words if word.lower() in agent_b_response.lower()]
        
        # Check memory references
        memory_words = ["sentence", "remember", "asked", "translate"]
        found_memory = [word for word in memory_words if word.lower() in agent_b_response.lower()]
        
        print(f"   Target sentence found: {'✅ YES' if has_target_sentence else '❌ NO'}")
        print(f"   Spanish words found: {len(found_spanish)} ({found_spanish[:3]}...)")
        print(f"   Memory indicators: {len(found_memory)} ({found_memory})")
        
        # Final assessment
        if has_target_sentence and len(found_spanish) >= 2:
            print(f"\n🎉 EXCELLENT: History migration working perfectly!")
            print(f"   Agent B accessed the exact content and translated it.")
            success = "excellent"
        elif has_target_sentence or len(found_spanish) >= 2:
            print(f"\n✅ GOOD: History migration appears to be working!")
            print(f"   Agent B shows evidence of accessing previous content.")
            success = "good"
        elif len(found_memory) >= 2:
            print(f"\n⚠️  PARTIAL: Some memory context but missing exact content.")
            success = "partial"
        else:
            print(f"\n❌ POOR: No evidence of history migration.")
            success = "poor"
            
        return {
            "success": success,
            "agents": {
                "agent_a": {"id": agent_a_id, "session": agent_a_session},
                "agent_b": {"id": agent_b_id, "session": agent_b_session}
            },
            "shared_chat_session": chat_session_id,
            "target_sentence_found": has_target_sentence,
            "spanish_words_count": len(found_spanish),
            "memory_indicators_count": len(found_memory),
            "responses": {
                "agent_a": agent_a_content,
                "agent_b": agent_b_response
            }
        }
        
    finally:
        # Cleanup
        if hasattr(ai_assistant, 'execution_engine') and hasattr(ai_assistant.execution_engine, 'shutdown'):
            await ai_assistant.execution_engine.shutdown()
        print("\n🧹 Cleanup completed")

if __name__ == "__main__":
    asyncio.run(test_precreated_agents_history_migration())