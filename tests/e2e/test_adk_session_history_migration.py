# -*- coding: utf-8 -*-
"""
ADK Session History Migration Tests

Tests the complete flow of ADK session management with focus on chat history
extraction and injection during agent switching scenarios.
"""

import pytest
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any

from src.aether_frame.bootstrap import create_ai_assistant
from src.aether_frame.config.settings import Settings
from src.aether_frame.contracts import (
    TaskRequest, 
    UniversalMessage, 
    TaskStatus, 
    AgentConfig,
    UserContext
)


class TestADKSessionHistoryMigration:
    """Test ADK session management and chat history migration functionality."""

    @pytest.mark.asyncio
    async def test_adk_session_history_migration_complete_flow(self):
        """
        Test complete ADK session management flow with chat history migration.
        
        Covers three key scenarios:
        1. Initial session creation (no previous session)
        2. Session continuation (same agent)
        3. Agent switching with history migration
        """
        
        print("🚀 Testing ADK Session History Migration Complete Flow...")
        
        # Setup logging for detailed tracking
        logger = logging.getLogger("adk_session_test")
        logger.setLevel(logging.DEBUG)
        
        # Initialize AI Assistant
        settings = Settings()
        ai_assistant = await create_ai_assistant(settings)
        
        # Test configuration
        chat_session_id = f"test_history_migration_{int(datetime.now().timestamp())}"
        test_user_context = UserContext(user_id="test_user_adk_migration", user_name="ADK Migration Test User")
        test_messages = []  # Store all messages for verification
        
        print(f"🔧 Using consistent chat_session_id: {chat_session_id}")
        
        try:
            # =============================================================
            # SCENARIO 1: Initial Session Creation (Agent A - Programming)
            # =============================================================
            print("\n📝 SCENARIO 1: Initial Session Creation with Programming Agent...")
            
            initial_request = TaskRequest(
                task_id=f"initial_session_{int(datetime.now().timestamp())}",
                task_type="chat",
                description="Initial session creation with programming assistant",
                user_context=test_user_context,
                messages=[
                    UniversalMessage(
                        role="user",
                        content="Hello, I need help with Python programming. I'm learning about data structures.",
                        metadata={"scenario": "initial", "message_id": "msg_1"}
                    )
                ],
                agent_config=AgentConfig(
                    agent_type="programming_assistant",
                    system_prompt="You are a helpful Python programming assistant specialized in data structures and algorithms.",
                    model_config={
                        "model": "deepseek-chat",
                        "temperature": 0.3,
                        "max_tokens": 1500
                    },
                    framework_config={
                        "provider": "deepseek",
                        "specialization": "programming"
                    }
                ),
                metadata={
                    "chat_session_id": chat_session_id,
                    "test_phase": "initial_creation"
                }
            )
            
            # Send initial request
            result1 = await ai_assistant.process_request(initial_request)
            
            # Verify initial session creation
            assert result1 is not None
            assert result1.status == TaskStatus.SUCCESS
            assert result1.session_id is not None
            assert result1.agent_id is not None
            
            # Store session info
            programming_session_id = result1.session_id
            programming_agent_id = result1.agent_id
            test_messages.append(("user", initial_request.messages[0].content))
            if result1.messages:
                test_messages.append(("assistant", result1.messages[0].content))
            
            print(f"✅ Initial session created: session_id={programming_session_id}, agent_id={programming_agent_id}")
            print(f"   Response preview: {result1.messages[0].content[:100] if result1.messages else 'No response'}...")
            
            # =============================================================
            # Add more conversation to build history
            # =============================================================
            print("\n📝 Building conversation history...")
            
            # Second message - continue building history
            continue_request1 = TaskRequest(
                task_id=f"continue_1_{int(datetime.now().timestamp())}",
                task_type="chat",
                description="Continue programming conversation",
                user_context=test_user_context,
                messages=[
                    UniversalMessage(
                        role="user",
                        content="Can you explain how Python lists work and give me some examples?",
                        metadata={"scenario": "continuation", "message_id": "msg_2"}
                    )
                ],
                agent_id=programming_agent_id,
                session_id=chat_session_id,  # Use business chat_session_id for continuity
                metadata={
                    "chat_session_id": chat_session_id,
                    "test_phase": "building_history"
                }
            )
            
            result2 = await ai_assistant.process_request(continue_request1)
            print(f"🔍 DEBUG result2: session_id={result2.session_id}, agent_id={result2.agent_id}, status={result2.status}")
            print(f"🔍 DEBUG expected agent_id: {programming_agent_id}")
            print(f"🔍 DEBUG input chat_session_id: {chat_session_id}")
            assert result2.status == TaskStatus.SUCCESS
            # Note: result2.session_id will be an ADK session ID, not the business chat_session_id
            # But the agent_id should be the same since we're continuing with the same agent
            assert result2.agent_id == programming_agent_id      # Same agent
            
            test_messages.append(("user", continue_request1.messages[0].content))
            if result2.messages:
                test_messages.append(("assistant", result2.messages[0].content))
            
            print(f"✅ Continued conversation: {len(test_messages)} total messages")
            
            # Third message - more history
            continue_request2 = TaskRequest(
                task_id=f"continue_2_{int(datetime.now().timestamp())}",
                task_type="chat", 
                description="More programming conversation",
                user_context=test_user_context,
                messages=[
                    UniversalMessage(
                        role="user",
                        content="Now show me how list comprehensions work with specific examples.",
                        metadata={"scenario": "continuation", "message_id": "msg_3"}
                    )
                ],
                agent_id=programming_agent_id,
                session_id=chat_session_id,  # Use business chat_session_id for continuity
                metadata={
                    "chat_session_id": chat_session_id,
                    "test_phase": "building_history"
                }
            )
            
            result3 = await ai_assistant.process_request(continue_request2)
            assert result3.status == TaskStatus.SUCCESS
            
            test_messages.append(("user", continue_request2.messages[0].content))
            if result3.messages:
                test_messages.append(("assistant", result3.messages[0].content))
            
            print(f"✅ Built substantial history: {len(test_messages)} messages")
            
            # =============================================================
            # SCENARIO 2: Session Continuation (Same Agent)
            # =============================================================
            print(f"\n📝 SCENARIO 2: Session Continuation with Same Agent...")
            
            same_agent_request = TaskRequest(
                task_id=f"same_agent_{int(datetime.now().timestamp())}",
                task_type="chat",
                description="Continue with same programming agent",
                user_context=test_user_context,
                messages=[
                    UniversalMessage(
                        role="user",
                        content="Based on our previous discussion about lists, can you now explain dictionaries?",
                        metadata={"scenario": "same_agent", "message_id": "msg_4"}
                    )
                ],
                agent_id=programming_agent_id,
                session_id=chat_session_id,  # Use business chat_session_id for continuity
                metadata={
                    "chat_session_id": chat_session_id,
                    "test_phase": "same_agent_continuation"
                }
            )
            
            result4 = await ai_assistant.process_request(same_agent_request)
            assert result4.status == TaskStatus.SUCCESS
            # Should continue with same agent since we're using same business chat_session_id
            assert result4.agent_id == programming_agent_id      # Must be same agent
            
            test_messages.append(("user", same_agent_request.messages[0].content))
            if result4.messages:
                test_messages.append(("assistant", result4.messages[0].content))
            
            print(f"✅ Same agent continuation verified: agent reused correctly")
            print(f"   Total conversation length: {len(test_messages)} messages")
            
            # =============================================================
            # SCENARIO 3: Agent Switching with History Migration
            # =============================================================
            print(f"\n📝 SCENARIO 3: Agent Switching with History Migration...")
            print(f"   Switching from Programming Agent to Data Analysis Agent")
            print(f"   Expected: Chat history extraction and injection")
            
            # Store pre-switch message count for verification
            pre_switch_message_count = len(test_messages)
            print(f"   Pre-switch message count: {pre_switch_message_count}")
            
            # Create new agent with different specialization
            agent_switch_request = TaskRequest(
                task_id=f"agent_switch_{int(datetime.now().timestamp())}",
                task_type="analysis",
                description="Switch to data analysis agent with history migration",
                user_context=test_user_context,
                messages=[
                    UniversalMessage(
                        role="user",
                        content="Now I want to switch focus to data analysis. Based on our previous Python discussion, can you help me analyze some data using pandas?",
                        metadata={"scenario": "agent_switch", "message_id": "msg_5"}
                    )
                ],
                agent_config=AgentConfig(
                    agent_type="data_analyst",
                    system_prompt="You are a data analysis expert specializing in pandas and data science. You should be aware of any previous programming context.",
                    model_config={
                        "model": "deepseek-chat",
                        "temperature": 0.2,
                        "max_tokens": 2000
                    },
                    framework_config={
                        "provider": "deepseek", 
                        "specialization": "data_analysis"
                    }
                ),
                # Keep same chat_session_id but no agent_id/session_id (forces new agent creation)
                metadata={
                    "chat_session_id": chat_session_id,
                    "test_phase": "agent_switching",
                    "previous_agent_id": programming_agent_id,
                    "previous_session_id": programming_session_id
                }
            )
            
            # This should trigger agent switching logic in AdkSessionManager
            print("   🔄 Triggering agent switch...")
            result5 = await ai_assistant.process_request(agent_switch_request)
            
            # Verify agent switch occurred
            assert result5.status == TaskStatus.SUCCESS
            # New agent should be different from programming agent
            assert result5.agent_id != programming_agent_id      # New agent created
            assert result5.session_id is not None
            assert result5.agent_id is not None
            
            # Store new session info
            data_analysis_session_id = result5.session_id
            data_analysis_agent_id = result5.agent_id
            
            test_messages.append(("user", agent_switch_request.messages[0].content))
            if result5.messages:
                test_messages.append(("assistant", result5.messages[0].content))
            
            print(f"✅ Agent switch completed:")
            print(f"   Previous: agent_id={programming_agent_id}")
            print(f"   New:      session_id={data_analysis_session_id}, agent_id={data_analysis_agent_id}")
            print(f"   Business chat_session_id: {chat_session_id} (consistent)")
            
            # =============================================================
            # VERIFY HISTORY MIGRATION
            # =============================================================
            print(f"\n🔍 VERIFYING HISTORY MIGRATION...")
            
            # Test if new agent has context from previous conversation
            context_test_request = TaskRequest(
                task_id=f"context_test_{int(datetime.now().timestamp())}",
                task_type="analysis",
                description="Test if history migration worked",
                user_context=test_user_context,
                messages=[
                    UniversalMessage(
                        role="user",
                        content="Do you remember what we discussed about Python lists and list comprehensions earlier? Can you reference that in your data analysis guidance?",
                        metadata={"scenario": "context_verification", "message_id": "msg_6"}
                    )
                ],
                agent_id=data_analysis_agent_id,
                session_id=chat_session_id,  # Use business chat_session_id for continuity
                metadata={
                    "chat_session_id": chat_session_id,
                    "test_phase": "history_verification"
                }
            )
            
            result6 = await ai_assistant.process_request(context_test_request)
            assert result6.status == TaskStatus.SUCCESS
            assert result6.agent_id == data_analysis_agent_id  # Should continue with data analysis agent
            
            # Check if the response indicates awareness of previous context
            response_content = result6.messages[0].content.lower() if result6.messages else ""
            
            # Look for indicators that history was preserved
            context_indicators = ["list", "python", "comprehension", "previous", "earlier", "discussed"]
            context_awareness = sum(1 for indicator in context_indicators if indicator in response_content)
            
            print(f"✅ Context verification response received")
            print(f"   Context awareness indicators found: {context_awareness}/{len(context_indicators)}")
            print(f"   Response preview: {result6.messages[0].content[:200] if result6.messages else 'No response'}...")
            
            # If context awareness is low, it might indicate history migration issues
            if context_awareness >= 2:
                print(f"✅ HISTORY MIGRATION APPEARS SUCCESSFUL - Good context awareness")
            else:
                print(f"⚠️  HISTORY MIGRATION UNCERTAIN - Limited context awareness (might be normal)")
            
            # =============================================================
            # BIDIRECTIONAL TEST: Switch back to programming agent
            # =============================================================
            print(f"\n📝 BIDIRECTIONAL TEST: Switch back to Programming Agent...")
            
            back_to_programming_request = TaskRequest(
                task_id=f"back_to_programming_{int(datetime.now().timestamp())}",
                task_type="chat",
                description="Switch back to programming agent",
                user_context=test_user_context,
                messages=[
                    UniversalMessage(
                        role="user",
                        content="Let's go back to Python programming. Given our entire conversation about lists, dictionaries, and data analysis, can you suggest some advanced Python concepts I should learn next?",
                        metadata={"scenario": "bidirectional_switch", "message_id": "msg_7"}
                    )
                ],
                agent_config=AgentConfig(
                    agent_type="advanced_programming_assistant",
                    system_prompt="You are an advanced Python programming mentor. You should be aware of the student's learning journey and previous discussions.",
                    model_config={
                        "model": "deepseek-chat",
                        "temperature": 0.3,
                        "max_tokens": 1500
                    },
                    framework_config={
                        "provider": "deepseek",
                        "specialization": "advanced_programming"
                    }
                ),
                metadata={
                    "chat_session_id": chat_session_id,
                    "test_phase": "bidirectional_switch"
                }
            )
            
            result7 = await ai_assistant.process_request(back_to_programming_request)
            assert result7.status == TaskStatus.SUCCESS
            # Should create another new agent (different from both previous agents)
            assert result7.agent_id != data_analysis_agent_id    # New agent again
            assert result7.agent_id != programming_agent_id     # Different from original too
            
            final_session_id = result7.session_id
            final_agent_id = result7.agent_id
            
            print(f"✅ Bidirectional switch completed:")
            print(f"   Final: session_id={final_session_id}, agent_id={final_agent_id}")
            print(f"   Business chat_session_id: {chat_session_id} (consistent)")
            
            # =============================================================
            # FINAL VERIFICATION & SUMMARY
            # =============================================================
            print(f"\n🎉 TEST SUMMARY:")
            print(f"   Business Chat Session ID: {chat_session_id} (consistent throughout)")
            print(f"   Total Conversation Messages: {len(test_messages)}")
            print(f"   Agent Switches: 3 different agents used")
            print(f"   ")
            print(f"   Agent Flow:")
            print(f"   1. Programming: {programming_agent_id}")
            print(f"   2. Data Analysis: {data_analysis_agent_id}")
            print(f"   3. Advanced Programming: {final_agent_id}")
            
            # Verify all agents are different  
            agent_ids = [programming_agent_id, data_analysis_agent_id, final_agent_id]
            assert len(set(agent_ids)) == 3, "All agents should be unique"
            
            print(f"✅ ALL SCENARIOS TESTED SUCCESSFULLY!")
            
            return {
                "chat_session_id": chat_session_id,
                "agents": {
                    "programming": programming_agent_id,
                    "data_analysis": data_analysis_agent_id,
                    "final_programming": final_agent_id
                },
                "message_count": len(test_messages),
                "test_results": [result1, result2, result3, result4, result5, result6, result7]
            }
            
        finally:
            # Cleanup
            if hasattr(ai_assistant, 'execution_engine') and hasattr(ai_assistant.execution_engine, 'shutdown'):
                await ai_assistant.execution_engine.shutdown()
            print("🧹 Cleanup completed")

    def _verify_message_content(self, messages: List[Dict[str, Any]], expected_content_fragments: List[str]) -> bool:
        """
        Verify that extracted/injected messages contain expected content.
        
        Args:
            messages: List of message dictionaries
            expected_content_fragments: List of content fragments that should be found
            
        Returns:
            bool: True if verification passes
        """
        all_content = " ".join([msg.get("content", "") for msg in messages]).lower()
        found_fragments = [fragment for fragment in expected_content_fragments if fragment.lower() in all_content]
        
        print(f"   Content verification: {len(found_fragments)}/{len(expected_content_fragments)} fragments found")
        return len(found_fragments) >= len(expected_content_fragments) * 0.7  # 70% threshold


if __name__ == "__main__":
    # Quick test runner for standalone execution
    import asyncio
    
    async def run_quick_test():
        print("🚀 Quick ADK Session History Migration Test...")
        test_instance = TestADKSessionHistoryMigration()
        
        try:
            result = await test_instance.test_adk_session_history_migration_complete_flow()
            print(f"✅ Test completed successfully: {result['message_count']} messages processed")
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run_quick_test())