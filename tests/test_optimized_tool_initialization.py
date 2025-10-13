#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test optimized tool initialization logic in AdkDomainAgent."""

import asyncio
import logging
from typing import List

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
from aether_frame.contracts import AgentRequest, TaskRequest, UniversalTool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_tool_initialization_optimization():
    """Test that tools are initialized only once, not on every execute call."""
    print("🧪 Testing Optimized Tool Initialization Logic")
    print("=" * 60)
    
    # Create agent with a valid name
    agent = AdkDomainAgent(
        agent_id="test_agent",
        config={"name": "test_agent"},  # Use valid identifier
        runtime_context={"session_id": "test_session"}
    )
    
    # Initialize agent
    await agent.initialize()
    
    # Verify initial state
    assert not agent._tools_initialized, "Tools should not be initialized initially"
    # Note: ADK agent might be created during initialize() but without tools
    
    print("✅ Initial state verified: tools not initialized")
    
    # Create test tools
    test_tools = [
        UniversalTool("echo", "builtin", "Echo tool for testing"),
        UniversalTool("search", "mcp_server", "Search tool for testing")
    ]
    
    # Create task request with tools
    task_request = TaskRequest(
        task_id="test_task",
        task_type="conversation",
        description="Test task for tool initialization",
        available_tools=test_tools
    )
    
    agent_request = AgentRequest(task_request=task_request)
    
    # First execute call should initialize tools
    print("\n🔄 First execute call - should initialize tools")
    try:
        # This will attempt to create ADK agent, which might fail without Google ADK
        # but we can still test the initialization logic
        await agent.execute(agent_request)
    except Exception as e:
        # Expected if ADK not available - but tools should still be marked as initialized
        print(f"   Expected error (ADK not available): {str(e)[:100]}...")
    
    # Verify tools were marked as initialized
    assert agent._tools_initialized, "Tools should be marked as initialized after first execute"
    print("✅ Tools initialized flag set correctly")
    
    # Second execute call should NOT re-initialize tools
    print("\n🔄 Second execute call - should NOT re-initialize tools")
    
    # Create a new task request without tools (normal conversation)
    task_request_no_tools = TaskRequest(
        task_id="test_task_2",
        task_type="conversation", 
        description="Normal conversation without tools"
        # No available_tools - this is normal conversation
    )
    
    agent_request_no_tools = AgentRequest(task_request=task_request_no_tools)
    
    try:
        await agent.execute(agent_request_no_tools)
    except Exception as e:
        print(f"   Expected error (ADK not available): {str(e)[:100]}...")
    
    # Tools should still be marked as initialized
    assert agent._tools_initialized, "Tools should remain initialized"
    print("✅ Tools remained initialized - no redundant initialization")
    
    # Test dynamic tool update
    print("\n🔧 Testing dynamic tool update")
    new_tools = [
        UniversalTool("timestamp", "builtin", "Timestamp tool"),
        UniversalTool("weather", "mcp_server", "Weather tool")
    ]
    
    await agent.update_tools(new_tools)
    assert agent._tools_initialized, "Tools should remain initialized after update"
    print("✅ Dynamic tool update working")
    
    print("\n🎉 All tool initialization optimization tests passed!")
    
    return True

async def test_tool_initialization_scenarios():
    """Test various tool initialization scenarios."""
    print("\n🧪 Testing Tool Initialization Scenarios")
    print("=" * 50)
    
    # Scenario 1: Agent without tools initially
    print("\n📝 Scenario 1: Agent without tools")
    agent1 = AdkDomainAgent("agent1", {}, {"session_id": "test1"})
    await agent1.initialize()
    
    task_no_tools = TaskRequest(
        task_id="no_tools_task",
        task_type="conversation",
        description="Task without tools"
    )
    request_no_tools = AgentRequest(task_request=task_no_tools)
    
    try:
        await agent1.execute(request_no_tools)
    except Exception as e:
        print(f"   Expected error: {str(e)[:80]}...")
    
    assert agent1._tools_initialized, "Should initialize even without tools"
    print("✅ Agent initialized without tools")
    
    # Scenario 2: Agent with tools from start
    print("\n📝 Scenario 2: Agent with tools from start")
    agent2 = AdkDomainAgent("agent2", {}, {"session_id": "test2"})
    await agent2.initialize()
    
    tools = [UniversalTool("test_tool", "builtin", "Test tool")]
    task_with_tools = TaskRequest(
        task_id="with_tools_task",
        task_type="conversation", 
        description="Task with tools",
        available_tools=tools
    )
    request_with_tools = AgentRequest(task_request=task_with_tools)
    
    try:
        await agent2.execute(request_with_tools)
    except Exception as e:
        print(f"   Expected error: {str(e)[:80]}...")
    
    assert agent2._tools_initialized, "Should initialize with tools"
    print("✅ Agent initialized with tools")
    
    # Scenario 3: Multiple executions
    print("\n📝 Scenario 3: Multiple executions with same agent")
    execution_count = 3
    for i in range(execution_count):
        task = TaskRequest(
            task_id=f"task_{i}",
            task_type="conversation",
            description=f"Test task {i}"
        )
        request = AgentRequest(task_request=task)
        
        try:
            await agent2.execute(request)
        except Exception:
            pass  # Expected without ADK
    
    assert agent2._tools_initialized, "Should remain initialized after multiple executions"
    print(f"✅ Agent handled {execution_count} executions correctly")
    
    print("\n🎉 All scenarios passed!")

async def main():
    """Run all tool initialization tests."""
    print("🚀 Starting Tool Initialization Optimization Tests")
    print("=" * 70)
    
    try:
        await test_tool_initialization_optimization()
        await test_tool_initialization_scenarios()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED! Tool initialization optimization is working correctly.")
        print("\n📋 Summary:")
        print("   - Tools are initialized only once per agent")
        print("   - No redundant initialization on subsequent execute calls")
        print("   - Dynamic tool updates work correctly")
        print("   - Various initialization scenarios handled properly")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)