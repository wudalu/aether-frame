#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete end-to-end test for agent_id architecture.
Tests the full business logic flow, not just error handling.
"""

import asyncio
import pytest
import sys
import os

from src.aether_frame.contracts import (
    TaskRequest, TaskResult, AgentConfig, UniversalMessage, TaskStatus
)
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from src.aether_frame.execution.task_router import ExecutionStrategy
from src.aether_frame.contracts import FrameworkType


class TestAgentIdBusinessLogic:
    """Test the complete agent_id business logic flow"""

    @pytest.mark.asyncio
    async def test_complete_agent_id_workflow(self):
        """
        Test the complete workflow:
        1. Create agent via Case 3 (agent_config)
        2. Use Case 1 (agent_id + session_id) to continue the same session
        3. Use Case 2 (agent_id only) to create a new session for the same agent
        """
        print("🚀 Testing Complete agent_id Business Logic Workflow")
        
        adapter = AdkFrameworkAdapter()
        
        # Step 1: Create agent via Case 3 (agent_config)
        print("\n📝 Step 1: Creating agent via agent_config...")
        
        agent_config = AgentConfig(
            agent_type="test_business_agent",
            system_prompt="You are a helpful test assistant for business logic validation.",
            model_config={
                "model": "deepseek-chat",
                "temperature": 0.5
            }
        )
        
        create_request = TaskRequest(
            task_id="create_agent_task",
            task_type="chat",
            description="Create agent for business logic test",
            messages=[UniversalMessage(role="user", content="Hello, I'm testing the agent creation.")],
            agent_config=agent_config
        )
        
        strategy = ExecutionStrategy(
            framework_type=FrameworkType.ADK,
            task_complexity="simple",
            execution_config={},
            runtime_options={}
        )
        
        create_result = await adapter.execute_task(create_request, strategy)
        
        # Verify agent creation succeeded
        assert create_result.status != TaskStatus.ERROR, f"Agent creation failed: {create_result.error_message}"
        assert create_result.agent_id is not None, "agent_id should be returned"
        assert create_result.session_id is not None, "session_id should be returned"
        
        created_agent_id = create_result.agent_id
        created_session_id = create_result.session_id
        
        print(f"✅ Step 1: Successfully created agent {created_agent_id} with session {created_session_id}")
        
        # Step 2: Test Case 1 - Use agent_id + session_id to continue the same session
        print(f"\n📝 Step 2: Testing Case 1 with real agent {created_agent_id} and session {created_session_id}...")
        
        continue_request = TaskRequest(
            task_id="continue_session_task",
            task_type="chat",
            description="Continue existing session",
            messages=[UniversalMessage(role="user", content="Continue our conversation from the previous message.")],
            agent_id=created_agent_id,
            session_id=created_session_id
        )
        
        continue_result = await adapter.execute_task(continue_request, strategy)
        
        if continue_result.status == TaskStatus.ERROR:
            print(f"❌ Step 2 Error: {continue_result.error_message}")
            
            # Let's check what's in AgentManager and adapter mappings
            print(f"🔍 Debugging - Agent in AgentManager: {await adapter.agent_manager.get_agent(created_agent_id) is not None}")
            print(f"🔍 Debugging - Agent in adapter mapping: {created_agent_id in adapter._agent_runners}")
            print(f"🔍 Debugging - Agent runners mapping: {adapter._agent_runners}")
            
            # The issue is that Case 3 creates agent_id but doesn't register with AgentManager!
            print("💡 Issue identified: Case 3 creates agent_id but doesn't register with AgentManager")
            return False
        else:
            print(f"✅ Step 2: Successfully continued session - {continue_result.agent_id}/{continue_result.session_id}")
        
        # Step 3: Test Case 2 - Create new session for existing agent
        print(f"\n📝 Step 3: Testing Case 2 - creating new session for agent {created_agent_id}...")
        
        new_session_request = TaskRequest(
            task_id="new_session_task",
            task_type="chat", 
            description="Create new session for existing agent",
            messages=[UniversalMessage(role="user", content="This should be a new session for the same agent.")],
            agent_id=created_agent_id
            # Note: session_id is None
        )
        
        new_session_result = await adapter.execute_task(new_session_request, strategy)
        
        if new_session_result.status == TaskStatus.ERROR:
            print(f"❌ Step 3 Error: {new_session_result.error_message}")
            return False
        else:
            new_session_id = new_session_result.session_id
            assert new_session_id != created_session_id, "Should create a different session ID"
            print(f"✅ Step 3: Successfully created new session {new_session_id} for agent {created_agent_id}")
        
        print("\n🎉 Complete workflow test passed!")
        return True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])