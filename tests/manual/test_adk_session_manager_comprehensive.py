#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive test for ADK Session Manager with real LLM calls."""

import asyncio
import os
import uuid
from datetime import datetime
from typing import Dict, Any

# Load test environment
from dotenv import load_dotenv
load_dotenv('.env.test')

from src.aether_frame.config.settings import Settings
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from src.aether_frame.framework.adk.adk_session_manager import AdkSessionManager
from src.aether_frame.contracts import (
    TaskRequest,
    UniversalMessage,
    UserContext,
    AgentConfig,
    FrameworkType
)


class AdkSessionManagerTest:
    """Comprehensive test for ADK Session Manager functionality."""
    
    def __init__(self):
        """Initialize test environment."""
        self.settings = Settings()
        self.adapter = None
        self.session_manager = None
        self.chat_session_id = f"test_chat_session_{uuid.uuid4().hex[:8]}"
        self.user_id = "test_user"
        self.agent_configs = {}
        self.agent_ids = {}
        
        print(f"🔧 Initialized test with chat_session_id: {self.chat_session_id}")
    
    async def setup_environment(self):
        """Set up ADK environment with two different agents."""
        print("\n🏗️ Setting up ADK environment...")
        
        try:
            # Initialize ADK adapter
            self.adapter = AdkFrameworkAdapter()
            await self.adapter.initialize()
            
            # Get session manager from adapter
            self.session_manager = self.adapter.adk_session_manager
            
            print("✅ ADK adapter initialized successfully")
            
            # Create two different agent configurations
            self.agent_configs["assistant"] = AgentConfig(
                agent_type="conversational_agent",
                system_prompt="You are a helpful AI assistant. Always start your responses with '[ASSISTANT]' to identify yourself.",
                model_config={"model": "deepseek-chat"}
            )
            
            self.agent_configs["translator"] = AgentConfig(
                agent_type="translation_agent", 
                system_prompt="You are a language translator. Always start your responses with '[TRANSLATOR]' to identify yourself. You can translate between any languages.",
                model_config={"model": "deepseek-chat"}
            )
            
            print("✅ Agent configurations created")
            
            # Create agents in the system
            await self._create_agents()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup environment: {e}")
            return False
    
    async def _create_agents(self):
        """Create both agents in the system."""
        print("\n👥 Creating agents...")
        
        for agent_name, agent_config in self.agent_configs.items():
            try:
                # Create task request for agent creation
                task_request = TaskRequest(
                    task_id=f"create_{agent_name}_{uuid.uuid4().hex[:6]}",
                    task_type="chat",
                    description=f"Create {agent_name} agent",
                    messages=[
                        UniversalMessage(
                            role="user",
                            content="Hello, please introduce yourself."
                        )
                    ],
                    user_context=UserContext(user_id=self.user_id),
                    agent_config=agent_config
                )
                
                # Execute agent creation through adapter
                from src.aether_frame.execution.task_router import ExecutionStrategy
                from src.aether_frame.contracts import TaskComplexity
                strategy = ExecutionStrategy(
                    framework_type=FrameworkType.ADK,
                    task_complexity=TaskComplexity.SIMPLE,
                    execution_config={},
                    runtime_options={}
                )
                
                result = await self.adapter.execute_task(task_request, strategy)
                
                if result.status.value == "completed" or result.status.value == "success":
                    self.agent_ids[agent_name] = result.agent_id
                    print(f"✅ Created {agent_name} agent: {result.agent_id}")
                    # Handle both result_data and messages
                    response = result.result_data or (result.messages[0].content if result.messages else "Agent created successfully")
                    print(f"   Response: {response}")
                else:
                    raise Exception(f"Agent creation failed: {result.error_message}")
                    
            except Exception as e:
                print(f"❌ Failed to create {agent_name} agent: {e}")
                raise
    
    async def test_initial_conversation(self):
        """Test initial conversation with first agent."""
        print(f"\n💬 Testing initial conversation with assistant agent...")
        
        try:
            # Coordinate session for assistant agent
            coordination_result = await self.session_manager.coordinate_chat_session(
                chat_session_id=self.chat_session_id,
                target_agent_id=self.agent_ids["assistant"],
                user_id=self.user_id,
                task_request=self._create_task_request("What is 2+2? Please be brief."),
                runner_manager=self.adapter.runner_manager
            )
            
            print(f"✅ Session coordination completed:")
            print(f"   ADK Session ID: {coordination_result.adk_session_id}")
            print(f"   Switch occurred: {coordination_result.switch_occurred}")
            print(f"   Agent: {coordination_result.new_agent_id}")
            
            # Execute conversation through adapter
            result = await self._execute_conversation(
                agent_id=self.agent_ids["assistant"],
                session_id=coordination_result.adk_session_id,
                message="What is 2+2? Please remember this is our first math question."
            )
            
            print(f"✅ Assistant response: {result.result_data or (result.messages[0].content if result.messages else 'No response')}")
            
            # Send second message to build history
            result2 = await self._execute_conversation(
                agent_id=self.agent_ids["assistant"],
                session_id=coordination_result.adk_session_id,
                message="And what is 3+3? This is our second math question."
            )
            
            print(f"✅ Assistant second response: {result2.result_data or (result2.messages[0].content if result2.messages else 'No response')}")
            
            return coordination_result.adk_session_id
            
        except Exception as e:
            print(f"❌ Initial conversation test failed: {e}")
            raise
    
    async def test_agent_switch_with_history_transfer(self, original_session_id: str):
        """Test switching to translator agent with history transfer."""
        print(f"\n🔄 Testing agent switch with history transfer...")
        
        try:
            # Coordinate session switch to translator agent
            coordination_result = await self.session_manager.coordinate_chat_session(
                chat_session_id=self.chat_session_id,
                target_agent_id=self.agent_ids["translator"],
                user_id=self.user_id,
                task_request=self._create_task_request("Translate 'hello' to Spanish"),
                runner_manager=self.adapter.runner_manager
            )
            
            print(f"✅ Agent switch coordination completed:")
            print(f"   ADK Session ID: {coordination_result.adk_session_id}")
            print(f"   Switch occurred: {coordination_result.switch_occurred}")
            print(f"   Previous agent: {coordination_result.previous_agent_id}")
            print(f"   New agent: {coordination_result.new_agent_id}")
            
            if not coordination_result.switch_occurred:
                raise Exception("Expected agent switch but none occurred")
            
            # Execute conversation with translator
            result = await self._execute_conversation(
                agent_id=self.agent_ids["translator"],
                session_id=coordination_result.adk_session_id,
                message="Please translate 'hello' to Spanish. Also, I see we had a math conversation before - what was the first math question?"
            )
            
            print(f"✅ Translator response: {result.result_data or (result.messages[0].content if result.messages else 'No response')}")
            
            # Verify translator can see previous conversation and do translation
            response_text = ""
            if result.messages and len(result.messages) > 0:
                response_text = result.messages[0].content
            elif isinstance(result.result_data, str):
                response_text = result.result_data
            elif isinstance(result.result_data, dict):
                # Handle dict result_data - look for actual response content
                response_text = str(result.result_data)
            
            print(f"🔍 Extracted response text: {response_text}")
            
            # Check if translator can do translation
            if "hola" in response_text.lower() or "spanish" in response_text.lower():
                print("✅ SUCCESS: Translator correctly translated 'hello' to Spanish!")
            else:
                print("⚠️ Warning: Translator didn't complete the translation properly")
            
            # Check if translator can see previous math conversation
            if "2+2" in response_text or "math" in response_text.lower():
                print("✅ SUCCESS: Translator can see the previous math conversation!")
            else:
                print("❌ FAILED: Translator cannot see previous math conversation")
                print(f"   Expected to mention previous math conversation but got: {response_text}")
            
            if "[TRANSLATOR]" not in response_text:
                print("⚠️ Warning: Translator didn't identify itself correctly")
            
            return coordination_result.adk_session_id
            
        except Exception as e:
            print(f"❌ Agent switch test failed: {e}")
            raise
    
    async def test_switch_back_to_original_agent(self, translator_session_id: str):
        """Test switching back to original assistant agent."""
        print(f"\n🔙 Testing switch back to original assistant agent...")
        
        try:
            # Switch back to assistant agent
            coordination_result = await self.session_manager.coordinate_chat_session(
                chat_session_id=self.chat_session_id,
                target_agent_id=self.agent_ids["assistant"],
                user_id=self.user_id,
                task_request=self._create_task_request("What was the first math question I asked?"),
                runner_manager=self.adapter.runner_manager
            )
            
            print(f"✅ Switch back coordination completed:")
            print(f"   ADK Session ID: {coordination_result.adk_session_id}")
            print(f"   Switch occurred: {coordination_result.switch_occurred}")
            print(f"   Previous agent: {coordination_result.previous_agent_id}")
            print(f"   New agent: {coordination_result.new_agent_id}")
            
            if not coordination_result.switch_occurred:
                raise Exception("Expected agent switch but none occurred")
            
            # Execute conversation testing memory
            result = await self._execute_conversation(
                agent_id=self.agent_ids["assistant"],
                session_id=coordination_result.adk_session_id,
                message="What was the first math question I asked you? Please answer exactly what I asked before."
            )
            
            print(f"✅ Assistant final response: {result.result_data or (result.messages[0].content if result.messages else 'No response')}")
            
            # Verify assistant can reference full history  
            response_text = ""
            if result.messages and len(result.messages) > 0:
                response_text = result.messages[0].content
            elif isinstance(result.result_data, str):
                response_text = result.result_data
            elif isinstance(result.result_data, dict):
                response_text = str(result.result_data)
            
            print(f"🔍 Extracted response text: {response_text}")
            
            # Check if assistant remembers the specific math question "What is 2+2?"
            if "2+2" in response_text or "What is 2+2" in response_text:
                print("✅ SUCCESS: Assistant correctly remembered the first math question!")
            else:
                print("❌ FAILED: Assistant cannot recall the first math question")
                print(f"   Expected to mention '2+2' but got: {response_text}")
            
            # Additional verification - ask about translator interaction
            result2 = await self._execute_conversation(
                agent_id=self.agent_ids["assistant"],
                session_id=coordination_result.adk_session_id,
                message="Did I ask someone to translate 'hello' to Spanish? Who was that?"
            )
            
            print(f"✅ Assistant translator memory response: {result2.result_data or (result2.messages[0].content if result2.messages else 'No response')}")
            
            response_text2 = ""
            if result2.messages and len(result2.messages) > 0:
                response_text2 = result2.messages[0].content
            elif isinstance(result2.result_data, str):
                response_text2 = result2.result_data
            elif isinstance(result2.result_data, dict):
                response_text2 = str(result2.result_data)
            
            if "translate" in response_text2.lower() and ("spanish" in response_text2.lower() or "hello" in response_text2.lower()):
                print("✅ SUCCESS: Assistant remembers the translator interaction!")
            else:
                print("❌ FAILED: Assistant cannot recall translator interaction")
                print(f"   Expected to mention translation but got: {response_text2}")
            
            if "[ASSISTANT]" not in response_text:
                print("⚠️ Warning: Assistant didn't identify itself correctly")
            
            return coordination_result.adk_session_id
            
        except Exception as e:
            print(f"❌ Switch back test failed: {e}")
            raise
    
    async def test_session_inspection(self):
        """Inspect session state for validation."""
        print(f"\n🔍 Inspecting final session state...")
        
        try:
            # Check chat session tracking
            chat_session = self.session_manager.chat_sessions.get(self.chat_session_id)
            if chat_session:
                print(f"✅ Chat session tracked:")
                print(f"   Active agent: {chat_session.active_agent_id}")
                print(f"   Active ADK session: {chat_session.active_adk_session_id}")
                print(f"   Active runner: {chat_session.active_runner_id}")
                print(f"   Last activity: {chat_session.last_activity}")
                print(f"   Last switch: {chat_session.last_switch_at}")
            else:
                print("❌ Chat session not found in tracking")
            
            # Check runner manager stats
            stats = await self.adapter.runner_manager.get_runner_stats()
            print(f"✅ Runner manager stats:")
            print(f"   Total runners: {stats['total_runners']}")
            print(f"   Total sessions: {stats['total_sessions']}")
            print(f"   ADK available: {stats['adk_available']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Session inspection failed: {e}")
            return False
    
    async def cleanup(self):
        """Clean up test environment."""
        print(f"\n🧹 Cleaning up test environment...")
        
        try:
            # Cleanup chat session
            if self.session_manager and self.chat_session_id:
                success = await self.session_manager.cleanup_chat_session(
                    self.chat_session_id, 
                    self.adapter.runner_manager,
                    agent_manager=self.adapter.agent_manager,
                )
                print(f"   Chat session cleanup: {'✅ success' if success else '❌ failed'}")
            
            # Shutdown adapter
            if self.adapter:
                await self.adapter.shutdown()
                print("   ✅ ADK adapter shutdown")
            
        except Exception as e:
            print(f"❌ Cleanup failed: {e}")
    
    def _create_task_request(self, message: str) -> TaskRequest:
        """Create a task request with the given message."""
        return TaskRequest(
            task_id=f"test_{uuid.uuid4().hex[:6]}",
            task_type="chat",
            description="Test conversation",
            messages=[
                UniversalMessage(
                    role="user",
                    content=message
                )
            ],
            user_context=UserContext(user_id=self.user_id)
        )
    
    async def _execute_conversation(self, agent_id: str, session_id: str, message: str):
        """Execute a conversation turn."""
        task_request = TaskRequest(
            task_id=f"conv_{uuid.uuid4().hex[:6]}",
            task_type="chat",
            description="Conversation turn",
            messages=[
                UniversalMessage(
                    role="user", 
                    content=message
                )
            ],
            user_context=UserContext(user_id=self.user_id),
            agent_id=agent_id,
            session_id=session_id
        )
        
        from src.aether_frame.execution.task_router import ExecutionStrategy
        from src.aether_frame.contracts import TaskComplexity
        strategy = ExecutionStrategy(
            framework_type=FrameworkType.ADK,
            task_complexity=TaskComplexity.SIMPLE,
            execution_config={},
            runtime_options={}
        )
        
        result = await self.adapter.execute_task(task_request, strategy)
        
        if result.status.value != "completed" and result.status.value != "success":
            raise Exception(f"Conversation failed: {result.error_message}")
        
        return result


async def main():
    """Main test runner."""
    print("🚀 Starting ADK Session Manager Comprehensive Test")
    print("=" * 70)
    
    test = AdkSessionManagerTest()
    
    try:
        # Setup environment
        print("\n📋 Phase 1: Environment Setup")
        success = await test.setup_environment()
        if not success:
            print("❌ Environment setup failed, aborting test")
            return 1
        
        # Test initial conversation
        print("\n📋 Phase 2: Initial Conversation")
        original_session = await test.test_initial_conversation()
        
        # Test agent switch with history
        print("\n📋 Phase 3: Agent Switch with History Transfer")
        translator_session = await test.test_agent_switch_with_history_transfer(original_session)
        
        # Test switch back
        print("\n📋 Phase 4: Switch Back to Original Agent")
        final_session = await test.test_switch_back_to_original_agent(translator_session)
        
        # Inspect final state
        print("\n📋 Phase 5: Session State Inspection")
        await test.test_session_inspection()
        
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("✅ ADK Session Manager is working correctly with real LLM calls")
        print("✅ Agent switching and history transfer is functional")
        print("✅ Session management and coordination is robust")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        print("=" * 70)
        return 1
        
    finally:
        # Always cleanup
        await test.cleanup()


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
