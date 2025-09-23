# -*- coding: utf-8 -*-
"""End-to-End Tests for Session ID Propagation through AIAssistant."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.aether_frame.contracts import (
    AgentConfig,
    FrameworkType,
    TaskRequest,
    TaskStatus,
    UniversalMessage,
)
from src.aether_frame.execution.ai_assistant import AIAssistant
from src.aether_frame.execution.execution_engine import ExecutionEngine
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter


class TestSessionIdPropagationE2E:
    """End-to-end tests for session ID propagation from AIAssistant to ADK."""

    @pytest.fixture
    async def ai_assistant(self):
        """Create AI Assistant with mocked components for testing."""
        # Mock execution engine
        execution_engine = MagicMock(spec=ExecutionEngine)
        
        # Create real AI Assistant with mocked engine
        assistant = AIAssistant(execution_engine=execution_engine)
        
        # Mock the execute_task method to use real ADK adapter
        adk_adapter = AdkFrameworkAdapter()
        await adk_adapter.initialize()
        
        async def mock_execute_task(task_request):
            # Route to real ADK adapter for session testing
            from src.aether_frame.execution.task_router import ExecutionStrategy
            from src.aether_frame.contracts import TaskComplexity
            
            strategy = ExecutionStrategy(
                framework_type=FrameworkType.ADK,
                task_complexity=TaskComplexity.SIMPLE,
                execution_config={},
                runtime_options={}
            )
            
            return await adk_adapter.execute_task(task_request, strategy)
        
        execution_engine.execute_task = AsyncMock(side_effect=mock_execute_task)
        
        yield assistant
        
        # Cleanup
        await adk_adapter.shutdown()

    @pytest.mark.asyncio
    async def test_new_session_creation_with_deepseek_config(self, ai_assistant):
        """Test creating new session with DeepSeek model configuration."""
        
        # Create TaskRequest with agent_config for new session (DeepSeek)
        task_request = TaskRequest(
            task_id="test_new_session_deepseek",
            task_type="chat",
            description="Test new session creation with DeepSeek",
            messages=[UniversalMessage(role="user", content="Hello, I need help with coding")],
            agent_config=AgentConfig(
                agent_type="coding_assistant",
                system_prompt="You are a helpful coding assistant using DeepSeek.",
                model_config={
                    "model": "deepseek-chat",
                    "temperature": 0.1,
                    "max_tokens": 2000
                },
                available_tools=["code_executor", "file_manager"],
                framework_config={
                    "provider": "deepseek",
                    "api_base": "https://api.deepseek.com",
                    "memory_settings": {"max_context_length": 8192}
                }
            )
        )
        
        # Process through AIAssistant (complete E2E flow)
        result = await ai_assistant.process_request(task_request)
        
        # Verify session creation
        assert result is not None
        assert result.task_id == "test_new_session_deepseek"
        assert result.session_id is not None
        assert result.session_id.startswith("session_")
        assert len(result.session_id) > 8  # session_<8-char-uuid>
        
        print(f"✅ New session created: {result.session_id}")
        return result.session_id

    @pytest.mark.asyncio
    async def test_session_continuation_flow(self, ai_assistant):
        """Test full session continuation flow using existing session_id."""
        
        # Step 1: Create initial session
        initial_request = TaskRequest(
            task_id="test_initial_request",
            task_type="chat",
            description="Initial request to create session",
            messages=[UniversalMessage(role="user", content="Start new conversation")],
            agent_config=AgentConfig(
                agent_type="general_assistant",
                system_prompt="You are a helpful general assistant.",
                model_config={"model": "deepseek-chat", "temperature": 0.3},
                framework_config={"provider": "deepseek"}
            )
        )
        
        initial_result = await ai_assistant.process_request(initial_request)
        
        # Verify initial session creation
        assert initial_result.session_id is not None
        session_id = initial_result.session_id
        print(f"✅ Initial session: {session_id}")
        
        # Step 2: Continue conversation using session_id
        followup_request = TaskRequest(
            task_id="test_followup_request",
            task_type="chat", 
            description="Follow-up message in existing session",
            messages=[UniversalMessage(role="user", content="Continue our conversation")],
            session_id=session_id  # Use existing session - NO agent_config needed
        )
        
        followup_result = await ai_assistant.process_request(followup_request)
        
        # Verify session continuation
        assert followup_result.session_id == session_id
        assert followup_result.task_id == "test_followup_request"
        print(f"✅ Session continued: {followup_result.session_id}")
        
        # Step 3: Another follow-up to ensure persistence
        second_followup = TaskRequest(
            task_id="test_second_followup",
            task_type="chat",
            description="Second follow-up in same session",
            messages=[UniversalMessage(role="user", content="Third message in conversation")],
            session_id=session_id
        )
        
        second_result = await ai_assistant.process_request(second_followup)
        
        # Verify session still continues
        assert second_result.session_id == session_id
        print(f"✅ Session persisted: {second_result.session_id}")
        
        return session_id

    @pytest.mark.asyncio
    async def test_multiple_parallel_sessions(self, ai_assistant):
        """Test creating and managing multiple parallel sessions."""
        
        # Create first session with DeepSeek coding config
        session1_request = TaskRequest(
            task_id="session1_init",
            task_type="coding",
            description="Coding session with DeepSeek",
            messages=[UniversalMessage(role="user", content="Help me write Python code")],
            agent_config=AgentConfig(
                agent_type="coding_specialist",
                system_prompt="You are a Python coding specialist.",
                model_config={"model": "deepseek-coder", "temperature": 0.1},
                available_tools=["code_executor", "python_repl"],
                framework_config={"provider": "deepseek", "focus": "coding"}
            )
        )
        
        # Create second session with different config
        session2_request = TaskRequest(
            task_id="session2_init", 
            task_type="analysis",
            description="Analysis session with DeepSeek",
            messages=[UniversalMessage(role="user", content="Analyze this data")],
            agent_config=AgentConfig(
                agent_type="data_analyst",
                system_prompt="You are a data analysis expert.",
                model_config={"model": "deepseek-chat", "temperature": 0.2},
                available_tools=["data_processor", "chart_generator"],
                framework_config={"provider": "deepseek", "focus": "analysis"}
            )
        )
        
        # Process both sessions
        result1 = await ai_assistant.process_request(session1_request)
        result2 = await ai_assistant.process_request(session2_request)
        
        # Verify separate sessions created
        assert result1.session_id != result2.session_id
        assert result1.session_id is not None
        assert result2.session_id is not None
        
        session1_id = result1.session_id
        session2_id = result2.session_id
        
        print(f"✅ Session 1 (coding): {session1_id}")
        print(f"✅ Session 2 (analysis): {session2_id}")
        
        # Test interleaved usage of both sessions
        session1_followup = TaskRequest(
            task_id="session1_followup",
            task_type="coding",
            description="Continue coding session",
            messages=[UniversalMessage(role="user", content="Add error handling to the code")],
            session_id=session1_id
        )
        
        session2_followup = TaskRequest(
            task_id="session2_followup",
            task_type="analysis", 
            description="Continue analysis session",
            messages=[UniversalMessage(role="user", content="Generate a summary report")],
            session_id=session2_id
        )
        
        # Execute follow-ups
        result1_followup = await ai_assistant.process_request(session1_followup)
        result2_followup = await ai_assistant.process_request(session2_followup)
        
        # Verify session isolation
        assert result1_followup.session_id == session1_id
        assert result2_followup.session_id == session2_id
        
        print(f"✅ Sessions maintained isolation")
        
        return session1_id, session2_id

    @pytest.mark.asyncio
    async def test_session_error_handling(self, ai_assistant):
        """Test error handling with invalid session_id."""
        
        # Try to use non-existent session_id
        invalid_request = TaskRequest(
            task_id="test_invalid_session",
            task_type="chat",
            description="Request with invalid session",
            messages=[UniversalMessage(role="user", content="Hello")],
            session_id="invalid_session_id_12345"  # Non-existent session
        )
        
        result = await ai_assistant.process_request(invalid_request)
        
        # Should return error result
        assert result.status == TaskStatus.ERROR
        assert "not found" in result.error_message.lower()
        print(f"✅ Invalid session handled correctly: {result.error_message}")

    @pytest.mark.asyncio  
    async def test_missing_config_and_session_error(self, ai_assistant):
        """Test error when neither session_id nor agent_config provided."""
        
        incomplete_request = TaskRequest(
            task_id="test_incomplete_request",
            task_type="chat",
            description="Request missing both session_id and agent_config",
            messages=[UniversalMessage(role="user", content="Hello")]
            # No session_id and no agent_config
        )
        
        result = await ai_assistant.process_request(incomplete_request)
        
        # Should return error
        assert result.status == TaskStatus.ERROR
        assert "no session_id or agent_config" in result.error_message.lower()
        print(f"✅ Missing config error handled: {result.error_message}")

    @pytest.mark.asyncio
    async def test_deepseek_specific_configurations(self, ai_assistant):
        """Test various DeepSeek-specific configurations."""
        
        deepseek_configs = [
            {
                "name": "deepseek_coder",
                "config": AgentConfig(
                    agent_type="code_specialist",
                    system_prompt="You are DeepSeek Coder, specialized in programming.",
                    model_config={
                        "model": "deepseek-coder",
                        "temperature": 0.05,
                        "max_tokens": 4000,
                        "stop_sequences": ["```"]
                    },
                    framework_config={
                        "provider": "deepseek",
                        "model_type": "coder",
                        "code_focus": True
                    }
                )
            },
            {
                "name": "deepseek_chat", 
                "config": AgentConfig(
                    agent_type="conversational",
                    system_prompt="You are DeepSeek Chat, a helpful conversational AI.",
                    model_config={
                        "model": "deepseek-chat",
                        "temperature": 0.7,
                        "max_tokens": 2000
                    },
                    framework_config={
                        "provider": "deepseek",
                        "model_type": "chat",
                        "conversation_mode": True
                    }
                )
            }
        ]
        
        session_ids = []
        
        for config_info in deepseek_configs:
            request = TaskRequest(
                task_id=f"test_{config_info['name']}",
                task_type="chat",
                description=f"Test {config_info['name']} configuration",
                messages=[UniversalMessage(role="user", content=f"Hello {config_info['name']}")],
                agent_config=config_info["config"]
            )
            
            result = await ai_assistant.process_request(request)
            
            assert result.session_id is not None
            session_ids.append(result.session_id)
            print(f"✅ {config_info['name']} session: {result.session_id}")
        
        # Verify all sessions are unique
        assert len(set(session_ids)) == len(session_ids)
        print(f"✅ All DeepSeek sessions unique: {len(session_ids)} sessions")
        
        return session_ids

if __name__ == "__main__":
    # Quick standalone test
    import asyncio
    
    async def run_quick_test():
        print("🧪 Running quick E2E session test...")
        
        # Mock minimal components
        from unittest.mock import MagicMock
        execution_engine = MagicMock()
        assistant = AIAssistant(execution_engine=execution_engine)
        
        # Mock return values
        execution_engine.execute_task = AsyncMock(return_value=MagicMock(
            task_id="test",
            session_id="session_12345678",
            status=TaskStatus.SUCCESS
        ))
        
        request = TaskRequest(
            task_id="quick_test",
            task_type="chat", 
            description="Quick test",
            messages=[UniversalMessage(role="user", content="test")],
            agent_config=AgentConfig(
                agent_type="test",
                system_prompt="test"
            )
        )
        
        result = await assistant.process_request(request)
        print(f"✅ Quick test result: {result.session_id}")
    
    asyncio.run(run_quick_test())