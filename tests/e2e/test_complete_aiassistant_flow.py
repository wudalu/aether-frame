# -*- coding: utf-8 -*-
"""End-to-End Tests for Complete AIAssistant → TaskRequest → Framework Flow."""

import pytest
from datetime import datetime
from unittest.mock import patch

from src.aether_frame.contracts import (
    AgentConfig,
    FrameworkType,
    TaskRequest,
    TaskStatus,
    UniversalMessage,
)


class TestCompleteAIAssistantFlow:
    """Test complete flow from AIAssistant through ExecutionEngine to FrameworkAdapter."""

    @pytest.mark.asyncio
    async def test_complete_flow_with_bootstrap(self):
        """Test complete flow using bootstrap initialization."""
        
        print("🚀 Testing complete AIAssistant flow with bootstrap...")
        
        # Use real bootstrap to create AIAssistant
        from src.aether_frame.bootstrap import create_ai_assistant
        from src.aether_frame.config.settings import Settings
        
        # Create settings for test
        settings = Settings()
        
        # Create AIAssistant through bootstrap (real initialization)
        ai_assistant = await create_ai_assistant(settings)
        
        try:
            # Test 1: Create new session with DeepSeek
            print("📝 Test 1: Creating new session with DeepSeek config...")
            
            new_session_request = TaskRequest(
                task_id="bootstrap_test_new_session",
                task_type="chat",
                description="Test new session via bootstrap",
                messages=[UniversalMessage(role="user", content="Hello, please help me with programming")],
                agent_config=AgentConfig(
                    agent_type="programming_assistant", 
                    system_prompt="You are a helpful programming assistant specialized in Python and web development.",
                    model_config={
                        "model": "deepseek-chat",  # Use DeepSeek
                        "temperature": 0.2,
                        "max_tokens": 1500
                    },
                    available_tools=["code_analyzer", "documentation_search"],
                    framework_config={
                        "provider": "deepseek",
                        "api_version": "v1",
                        "context_window": 4096
                    }
                )
            )
            
            # Process through complete stack
            result1 = await ai_assistant.process_request(new_session_request)
            
            # Verify session creation
            assert result1 is not None
            assert result1.task_id == "bootstrap_test_new_session"
            session_id = result1.session_id
            agent_id = result1.agent_id
            assert session_id is not None
            assert agent_id is not None
            print(f"✅ Session created: {session_id}")
            
            # Test 2: Continue session
            print("📝 Test 2: Continuing existing session...")
            
            continue_request = TaskRequest(
                task_id="bootstrap_test_continue",
                task_type="chat",
                description="Continue existing session",
                messages=[UniversalMessage(role="user", content="Can you help me debug this Python function?")],
                agent_id=agent_id,  # Use existing agent
                session_id=session_id  # Use existing session
            )
            
            result2 = await ai_assistant.process_request(continue_request)
            
            # Verify session continuation
            assert result2.session_id == session_id
            assert result2.agent_id == agent_id
            assert result2.task_id == "bootstrap_test_continue" 
            print(f"✅ Session continued: {result2.session_id}")
            
            # Test 3: Create another parallel session
            print("📝 Test 3: Creating parallel session...")
            
            parallel_request = TaskRequest(
                task_id="bootstrap_test_parallel",
                task_type="analysis",
                description="Create parallel session",
                messages=[UniversalMessage(role="user", content="I need data analysis help")],
                agent_config=AgentConfig(
                    agent_type="data_analyst",
                    system_prompt="You are a data analysis expert.",
                    model_config={
                        "model": "deepseek-chat",
                        "temperature": 0.1,
                        "max_tokens": 2000
                    },
                    framework_config={
                        "provider": "deepseek",
                        "specialization": "data_analysis"
                    }
                )
            )
            
            result3 = await ai_assistant.process_request(parallel_request)
            
            # Verify parallel session
            assert result3.session_id != session_id  # Different session
            assert result3.agent_id != agent_id  # Different agent
            assert result3.session_id is not None
            assert result3.agent_id is not None
            parallel_session_id = result3.session_id
            parallel_agent_id = result3.agent_id
            print(f"✅ Parallel session: {parallel_session_id}")
            
            # Test 4: Interleave sessions
            print("📝 Test 4: Interleaving session usage...")
            
            # Back to original session
            back_to_original = TaskRequest(
                task_id="bootstrap_test_back_original",
                task_type="chat", 
                description="Back to original session",
                messages=[UniversalMessage(role="user", content="Let's continue with the programming help")],
                agent_id=agent_id,
                session_id=session_id
            )
            
            result4 = await ai_assistant.process_request(back_to_original)
            assert result4.session_id == session_id
            assert result4.agent_id == agent_id
            
            # Continue parallel session
            continue_parallel = TaskRequest(
                task_id="bootstrap_test_continue_parallel",
                task_type="analysis",
                description="Continue parallel session", 
                messages=[UniversalMessage(role="user", content="Show me the analysis results")],
                agent_id=parallel_agent_id,
                session_id=parallel_session_id
            )
            
            result5 = await ai_assistant.process_request(continue_parallel)
            assert result5.session_id == parallel_session_id
            assert result5.agent_id == parallel_agent_id
            
            print(f"✅ Interleaved sessions working correctly")
            print(f"   Original: {session_id}")
            print(f"   Parallel: {parallel_session_id}")
            
            # Test 5: Error handling
            print("📝 Test 5: Testing error handling...")
            
            # Invalid agent_id + session_id combination
            invalid_session_request = TaskRequest(
                task_id="bootstrap_test_invalid",
                task_type="chat",
                description="Invalid agent/session test",
                messages=[UniversalMessage(role="user", content="This should fail")],
                agent_id="invalid_agent_nonexistent",
                session_id="invalid_session_nonexistent"
            )
            
            result6 = await ai_assistant.process_request(invalid_session_request)
            assert result6.status == TaskStatus.ERROR
            print(f"✅ Invalid agent/session error handled: {result6.error_message}")
            
            # Missing both agent_id/session_id and agent_config
            incomplete_request = TaskRequest(
                task_id="bootstrap_test_incomplete",
                task_type="chat",
                description="Incomplete request test",
                messages=[UniversalMessage(role="user", content="This should also fail")]
                # No agent_id, no session_id, no agent_config
            )
            
            result7 = await ai_assistant.process_request(incomplete_request)
            assert result7.status == TaskStatus.ERROR
            print(f"✅ Incomplete request error handled: {result7.error_message}")
            
            print("🎉 All tests passed! Complete flow working correctly.")
            
            return {
                "original_session": session_id,
                "parallel_session": parallel_session_id,
                "test_results": [result1, result2, result3, result4, result5, result6, result7]
            }
            
        finally:
            # Cleanup - shutdown AI Assistant properly
            if hasattr(ai_assistant, 'execution_engine') and hasattr(ai_assistant.execution_engine, 'shutdown'):
                await ai_assistant.execution_engine.shutdown()
            print("🧹 Cleanup completed")

    @pytest.mark.asyncio
    async def test_deepseek_model_configurations(self):
        """Test various DeepSeek model configurations through complete flow."""
        
        print("🧪 Testing DeepSeek model configurations...")
        
        from src.aether_frame.bootstrap import create_ai_assistant
        from src.aether_frame.config.settings import Settings
        
        settings = Settings()
        ai_assistant = await create_ai_assistant(settings)
        
        deepseek_test_cases = [
            {
                "name": "deepseek_chat_standard",
                "config": {
                    "model": "deepseek-chat",
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                "framework_config": {
                    "provider": "deepseek",
                    "version": "v1"
                }
            },
            {
                "name": "deepseek_coder_precise",
                "config": {
                    "model": "deepseek-coder", 
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "stop_sequences": ["```", "END"]
                },
                "framework_config": {
                    "provider": "deepseek",
                    "version": "v1",
                    "coding_mode": True
                }
            },
            {
                "name": "deepseek_chat_creative",
                "config": {
                    "model": "deepseek-chat",
                    "temperature": 0.9,
                    "max_tokens": 1500,
                    "top_p": 0.95
                },
                "framework_config": {
                    "provider": "deepseek",
                    "version": "v1", 
                    "creative_mode": True
                }
            }
        ]
        
        try:
            session_results = {}
            session_agent_mapping = {}
            
            for test_case in deepseek_test_cases:
                print(f"📝 Testing {test_case['name']}...")
                
                request = TaskRequest(
                    task_id=f"deepseek_test_{test_case['name']}",
                    task_type="chat",
                    description=f"Test {test_case['name']} configuration",
                    messages=[UniversalMessage(role="user", content=f"Hello from {test_case['name']}")],
                    agent_config=AgentConfig(
                        agent_type=f"assistant_{test_case['name']}",
                        system_prompt=f"You are an AI assistant using {test_case['name']}.",
                        model_config=test_case["config"],
                        framework_config=test_case["framework_config"]
                    )
                )
                
                result = await ai_assistant.process_request(request)
                
                assert result.session_id is not None
                assert result.agent_id is not None
                session_results[test_case['name']] = result.session_id
                session_agent_mapping[test_case['name']] = result.agent_id
                print(f"✅ {test_case['name']} session: {result.session_id}")
            
            # Verify all sessions are unique
            session_ids = list(session_results.values())
            assert len(set(session_ids)) == len(session_ids)
            print(f"✅ All {len(session_ids)} DeepSeek sessions are unique")
            
            # Test continuing each session using agent_id + session_id
            for name, session_id in session_results.items():
                # Find the corresponding agent_id from the test results
                agent_id = session_agent_mapping[name]
                
                continue_request = TaskRequest(
                    task_id=f"continue_{name}",
                    task_type="chat",
                    description=f"Continue {name} session",
                    messages=[UniversalMessage(role="user", content="Continue our conversation")],
                    agent_id=agent_id,
                    session_id=session_id
                )
                
                continue_result = await ai_assistant.process_request(continue_request)
                assert continue_result.session_id == session_id
                assert continue_result.agent_id == agent_id
                print(f"✅ {name} session continued successfully")
            
            print("🎉 All DeepSeek configurations tested successfully!")
            return session_results
            
        finally:
            if hasattr(ai_assistant, 'execution_engine') and hasattr(ai_assistant.execution_engine, 'shutdown'):
                await ai_assistant.execution_engine.shutdown()

    @pytest.mark.asyncio
    async def test_session_lifecycle_management(self):
        """Test session lifecycle and resource management."""
        
        print("🔄 Testing session lifecycle management...")
        
        from src.aether_frame.bootstrap import create_ai_assistant
        from src.aether_frame.config.settings import Settings
        
        settings = Settings()
        ai_assistant = await create_ai_assistant(settings)
        
        try:
            # Create multiple sessions rapidly
            sessions = []
            agents = []  # Store corresponding agent_ids
            for i in range(5):
                request = TaskRequest(
                    task_id=f"lifecycle_test_{i}",
                    task_type="chat",
                    description=f"Lifecycle test session {i}",
                    messages=[UniversalMessage(role="user", content=f"Session {i} message")],
                    agent_config=AgentConfig(
                        agent_type=f"test_agent_{i}",
                        system_prompt=f"You are test agent {i}.",
                        model_config={"model": "deepseek-chat", "temperature": 0.5},
                        framework_config={"provider": "deepseek", "test_id": i}
                    )
                )
                
                result = await ai_assistant.process_request(request)
                sessions.append(result.session_id)
                agents.append(result.agent_id)  # Store the corresponding agent_id
                print(f"✅ Created session {i}: {result.session_id} with agent {result.agent_id}")
            
            # Verify all sessions are active and usable
            for i, (session_id, agent_id) in enumerate(zip(sessions, agents)):
                test_request = TaskRequest(
                    task_id=f"verify_session_{i}",
                    task_type="chat",
                    description=f"Verify session {i}",
                    messages=[UniversalMessage(role="user", content=f"Verify session {i}")],
                    session_id=session_id,
                    agent_id=agent_id  # Provide both session_id and agent_id
                )
                
                verify_result = await ai_assistant.process_request(test_request)
                assert verify_result.session_id == session_id
                print(f"✅ Session {i} verified active")
            
            print(f"🎉 All {len(sessions)} sessions managed successfully!")
            return sessions
            
        finally:
            if hasattr(ai_assistant, 'execution_engine') and hasattr(ai_assistant.execution_engine, 'shutdown'):
                await ai_assistant.execution_engine.shutdown()


if __name__ == "__main__":
    # Quick test runner
    import asyncio
    
    async def run_quick_bootstrap_test():
        print("🚀 Quick bootstrap test...")
        test_instance = TestCompleteAIAssistantFlow()
        
        try:
            result = await test_instance.test_complete_flow_with_bootstrap()
            print(f"✅ Bootstrap test completed: {len(result['test_results'])} results")
        except Exception as e:
            print(f"❌ Bootstrap test failed: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run_quick_bootstrap_test())