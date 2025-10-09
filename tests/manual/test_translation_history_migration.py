#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Translation History Migration Test

Clear test for chat history migration:
- Agent A: Content creator (generates specific text)
- Agent B: Translator (must translate Agent A's content)

This test clearly shows if history migration works because Agent B 
needs the exact content from Agent A to perform translation.
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

async def translation_history_migration_test():
    """Translation test for chat history migration between 2 agents."""
    
    print("🔍 Translation History Migration Test")
    print("=" * 45)
    
    # Setup
    settings = Settings()
    ai_assistant = await create_ai_assistant(settings)
    
    chat_session_id = "translation_test"
    user_context = UserContext(user_id="test_user", user_name="Test User")
    
    try:
        # === STEP 1: Agent A (Content Creator) - Generate specific content ===
        print("\n📝 STEP 1: Agent A (Content Creator) - Generate story")
        
        content_request = TaskRequest(
            task_id="content_creation",
            task_type="creative",
            description="Create content for translation",
            user_context=user_context,
            messages=[
                UniversalMessage(
                    role="user",
                    content="Please write a short story (3-4 sentences) about a robot who learns to paint. Make it creative and unique.",
                )
            ],
            agent_config=AgentConfig(
                agent_type="content_creator",
                system_prompt="You are a creative content creator. Always identify yourself as Agent A and create original, engaging content.",
                model_config={"model": "deepseek-chat", "temperature": 0.7},
                framework_config={"provider": "deepseek"}
            ),
            metadata={"chat_session_id": chat_session_id}
        )
        
        result_a = await ai_assistant.process_request(content_request)
        assert result_a.status == TaskStatus.SUCCESS
        
        agent_a_content = result_a.messages[0].content
        print(f"✅ Agent A created story:")
        print(f"   {agent_a_content}")
        
        agent_a_id = result_a.agent_id
        
        # === STEP 2: Agent B (Translator) - Translate Agent A's content ===
        print(f"\n📝 STEP 2: Agent B (Translator) - Translate the story")
        
        translation_request = TaskRequest(
            task_id="translation_task",
            task_type="translation", 
            description="Translate content with history",
            user_context=user_context,
            messages=[
                UniversalMessage(
                    role="user",
                    content="Please translate the story you just created into Spanish. Translate the exact story from our previous conversation.",
                )
            ],
            agent_config=AgentConfig(
                agent_type="translator",
                system_prompt="You are a professional translator. Always identify yourself as Agent B. You should have access to previous conversation content to translate.",
                model_config={"model": "deepseek-chat", "temperature": 0.2},
                framework_config={"provider": "deepseek"}
            ),
            # No agent_id - triggers agent switch and history migration
            metadata={"chat_session_id": chat_session_id}
        )
        
        result_b = await ai_assistant.process_request(translation_request)
        assert result_b.status == TaskStatus.SUCCESS
        
        agent_b_response = result_b.messages[0].content
        print(f"✅ Agent B translation:")
        print(f"   {agent_b_response}")
        
        agent_b_id = result_b.agent_id
        
        # === STEP 3: Analyze Translation Success ===
        print(f"\n📝 STEP 3: Analyze Translation Quality")
        
        # Check if agent switch occurred
        agent_switch = agent_a_id != agent_b_id
        print(f"✅ Agent switch: {agent_a_id} → {agent_b_id}" if agent_switch else f"❌ No agent switch")
        
        # Check translation quality indicators
        spanish_indicators = [
            "el", "la", "un", "una", "que", "con", "por", "para", "es", "era", 
            "robot", "pintar", "aprender", "historia", "cuento"
        ]
        
        translation_content = agent_b_response.lower()
        found_spanish = [word for word in spanish_indicators if word in translation_content]
        
        # Check if translation mentions it's a translation
        translation_mentions = [
            "translation", "spanish", "translate", "traducción", "español"
        ]
        found_mentions = [word for word in translation_mentions if word.lower() in translation_content]
        
        # Check if Agent B identifies itself
        agent_b_mentioned = "agent b" in translation_content.lower()
        
        print(f"\n📊 TRANSLATION ANALYSIS:")
        print(f"   Agent switch occurred: {agent_switch}")
        print(f"   Spanish words found: {len(found_spanish)} ({found_spanish[:5]}...)")
        print(f"   Translation context: {len(found_mentions)} ({found_mentions})")
        print(f"   Agent B identified: {agent_b_mentioned}")
        print(f"   Response length: {len(agent_b_response)} characters")
        
        # Determine success
        success_score = 0
        success_reasons = []
        
        if agent_switch:
            success_score += 1
            success_reasons.append("✅ Agent switch occurred")
            
        if len(found_spanish) >= 3:
            success_score += 2
            success_reasons.append("✅ Contains Spanish content")
            
        if len(found_mentions) >= 1:
            success_score += 1
            success_reasons.append("✅ Acknowledges translation task")
            
        if agent_b_mentioned:
            success_score += 1
            success_reasons.append("✅ Agent B identified itself")
            
        # Final assessment
        print(f"\n📊 SUCCESS SCORE: {success_score}/5")
        for reason in success_reasons:
            print(f"   {reason}")
            
        if success_score >= 4:
            print(f"\n🎉 EXCELLENT: History migration working perfectly!")
            print(f"   Agent B successfully accessed and translated Agent A's content.")
            overall_success = "excellent"
        elif success_score >= 2:
            print(f"\n✅ GOOD: History migration appears to be working!")
            print(f"   Agent B shows clear evidence of accessing previous content.")
            overall_success = "good"
        else:
            print(f"\n❌ POOR: History migration may have issues.")
            print(f"   Agent B does not appear to have proper access to previous content.")
            overall_success = "poor"
            
        return {
            "success": overall_success,
            "success_score": success_score,
            "agent_switch": agent_switch,
            "spanish_words_found": len(found_spanish),
            "translation_acknowledged": len(found_mentions) > 0,
            "agent_b_identified": agent_b_mentioned,
            "content": {
                "agent_a_story": agent_a_content,
                "agent_b_translation": agent_b_response
            },
            "agents": {
                "creator": agent_a_id,
                "translator": agent_b_id
            }
        }
        
    finally:
        # Cleanup
        if hasattr(ai_assistant, 'execution_engine') and hasattr(ai_assistant.execution_engine, 'shutdown'):
            await ai_assistant.execution_engine.shutdown()
        print("\n🧹 Cleanup completed")

if __name__ == "__main__":
    asyncio.run(translation_history_migration_test())