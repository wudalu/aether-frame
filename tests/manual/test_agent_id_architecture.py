#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for agent_id + session_id architecture validation.
Tests Case 1 and Case 2 of the new agent_id driven execution.
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


class TestAgentIdArchitecture:
    """Test class for agent_id architecture validation"""

    @pytest.mark.asyncio
    async def test_case_1_agent_id_plus_session_id(self):
        """Test Case 1: agent_id + session_id (continue existing session)"""
        print("🧪 Testing Case 1: agent_id + session_id")
        
        adapter = AdkFrameworkAdapter()
        
        # This case requires an existing agent with an existing session
        # Since we haven't implemented Case 3 yet, we can't actually create 
        # a real agent/session to test with, so we'll test the error paths
        
        task_request = TaskRequest(
            task_id="case1_test",
            task_type="chat", 
            description="Test Case 1",
            messages=[UniversalMessage(role="user", content="Hello")],
            agent_id="fake_agent_id",  # This agent doesn't exist
            session_id="fake_session_id"
        )
        
        strategy = ExecutionStrategy(
            framework_type=FrameworkType.ADK,
            task_complexity="simple",
            execution_config={},
            runtime_options={}
        )
        
        result = await adapter.execute_task(task_request, strategy)
        
        # Should get error because agent doesn't exist
        assert result.status == TaskStatus.ERROR
        assert "Agent fake_agent_id not found" in result.error_message
        print("✅ Case 1: Correctly detected non-existent agent")

    @pytest.mark.asyncio
    async def test_case_2_agent_id_only(self):
        """Test Case 2: agent_id only (create new session for existing agent)"""
        print("🧪 Testing Case 2: agent_id only")
        
        adapter = AdkFrameworkAdapter()
        
        # This case also requires an existing agent, so we'll test error paths
        task_request = TaskRequest(
            task_id="case2_test",
            task_type="chat",
            description="Test Case 2", 
            messages=[UniversalMessage(role="user", content="Hello")],
            agent_id="fake_agent_id"  # session_id is None
        )
        
        strategy = ExecutionStrategy(
            framework_type=FrameworkType.ADK,
            task_complexity="simple", 
            execution_config={},
            runtime_options={}
        )
        
        result = await adapter.execute_task(task_request, strategy)
        
        # Should get error because agent doesn't exist
        assert result.status == TaskStatus.ERROR
        assert "Agent fake_agent_id not found" in result.error_message
        print("✅ Case 2: Correctly detected non-existent agent")

    @pytest.mark.asyncio
    async def test_backward_compatibility(self):
        """Test that existing session_id logic still works"""
        print("🧪 Testing Backward Compatibility: session_id only")
        
        adapter = AdkFrameworkAdapter()
        
        task_request = TaskRequest(
            task_id="compat_test",
            task_type="chat",
            description="Test backward compatibility",
            messages=[UniversalMessage(role="user", content="Hello")],
            session_id="fake_session_id"  # agent_id is None
        )
        
        strategy = ExecutionStrategy(
            framework_type=FrameworkType.ADK,
            task_complexity="simple",
            execution_config={},
            runtime_options={}
        )
        
        result = await adapter.execute_task(task_request, strategy)
        
        # Should get error because session doesn't exist
        assert result.status == TaskStatus.ERROR
        assert "Session fake_session_id not found" in result.error_message
        print("✅ Backward Compatibility: Correctly handled non-existent session")

    @pytest.mark.asyncio
    async def test_case_3_agent_config(self):
        """Test Case 3: agent_config (should still work with existing logic)"""
        print("🧪 Testing Case 3: agent_config (existing logic)")
        
        adapter = AdkFrameworkAdapter()
        
        agent_config = AgentConfig(
            agent_type="test_agent",
            system_prompt="You are a test assistant.",
            model_config={
                "model": "deepseek-chat",
                "temperature": 0.7
            }
        )
        
        task_request = TaskRequest(
            task_id="case3_test",
            task_type="chat",
            description="Test Case 3",
            messages=[UniversalMessage(role="user", content="Hello")],
            agent_config=agent_config
        )
        
        strategy = ExecutionStrategy(
            framework_type=FrameworkType.ADK,
            task_complexity="simple",
            execution_config={},
            runtime_options={}
        )
        
        result = await adapter.execute_task(task_request, strategy)
        
        # Should work and return agent_id and session_id
        assert result.status != TaskStatus.ERROR, f"Case 3 failed: {result.error_message}"
        assert result.agent_id is not None, "agent_id should be returned"
        assert result.session_id is not None, "session_id should be returned"
        
        print(f"✅ Case 3: Successfully created agent {result.agent_id} with session {result.session_id}")
        return result.agent_id, result.session_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])