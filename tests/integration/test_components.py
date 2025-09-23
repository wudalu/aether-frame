# -*- coding: utf-8 -*-
"""Integration tests for Aether Frame components."""

import asyncio
import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(project_root, "src"))

from aether_frame.config.settings import Settings
from aether_frame.contracts import (
    AgentConfig,
    ExecutionConfig,
    ExecutionContext,
    ExecutionMode,
    FrameworkType,
    SessionContext,
    TaskComplexity,
    TaskRequest,
    TaskStatus,
    UniversalMessage,
    UniversalTool,
    UserContext,
)
from aether_frame.execution.ai_assistant import AIAssistant
from aether_frame.execution.task_router import TaskRouter
from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from aether_frame.framework.framework_registry import FrameworkRegistry


class TestComponentIntegration:
    """Test integration between system components."""

    def test_data_contracts_integration(self):
        """Test that data contracts work together correctly."""
        print("📋 Testing data contracts integration...")

        user_context = UserContext(user_id="integration_test_user")

        session_context = SessionContext(
            session_id="integration_session",
            conversation_history=[
                UniversalMessage(role="user", content="Previous message")
            ],
        )

        tools = [
            UniversalTool(
                name="search_tool",
                description="Search for information",
                parameters_schema={"type": "object"},
                required_permissions=["search"],
            )
        ]

        agent_config = AgentConfig(
            agent_type="research_agent",
            system_prompt="You are a research agent.",
            framework_type=FrameworkType.ADK,
            available_tools=["search", "analysis"],
            framework_config={"timeout": 300},
        )

        execution_config = ExecutionConfig(
            execution_mode=ExecutionMode.ASYNC,
            max_retries=3,
            enable_logging=True,
            enable_monitoring=True,
        )

        task_request = TaskRequest(
            task_id="integration_001",
            task_type="research",
            description="Integration test task",
            user_context=user_context,
            session_context=session_context,
            messages=[UniversalMessage(role="user", content="Test message")],
            available_tools=tools,
            execution_config=execution_config,
        )

        # Test task request properties
        assert task_request.user_context.get_adk_user_id() == "integration_test_user"
        assert task_request.session_context.get_adk_session_id() == "integration_session"
        assert len(task_request.session_context.conversation_history) == 1
        assert len(task_request.messages) == 1
        assert len(task_request.available_tools) == 1

        # Verify the data structure maintains integrity
        assert task_request.available_tools[0].name == "search_tool"

        print("✅ Data contracts integration successful")
        return True

    async def test_task_routing_logic(self):
        """Test task routing and strategy selection."""
        print("🔀 Testing task routing logic...")

        settings = Settings()
        task_router = TaskRouter(settings)

        # Test simple chat task routing
        simple_task = TaskRequest(
            task_id="simple_001",
            task_type="chat",
            description="Simple chat",
            messages=[UniversalMessage(role="user", content="Hi")],
        )

        strategy = await task_router.route_task(simple_task)

        assert strategy is not None
        assert (
            strategy.framework_type == FrameworkType.ADK
        )  # Should prefer ADK for chat
        # Note: agent_type is now determined at the Framework Adapter layer, not in strategy
        assert strategy.task_complexity in [
            TaskComplexity.SIMPLE,
            TaskComplexity.MODERATE,
            TaskComplexity.COMPLEX,
            TaskComplexity.ADVANCED,
        ]

        print("✅ Task routing logic successful")
        return True

    async def test_framework_adapter_integration(self):
        """Test framework adapter initialization and basic operations."""
        print("🔧 Testing framework adapter integration...")

        adk_adapter = AdkFrameworkAdapter()

        # Test initialization
        await adk_adapter.initialize()
        assert await adk_adapter.is_available() is True

        # Test capabilities
        capabilities = await adk_adapter.get_capabilities()
        assert isinstance(capabilities, list)
        assert "conversational_agents" in capabilities
        assert "memory_management" in capabilities

        # Test health check
        health = await adk_adapter.health_check()
        assert health["framework"] == "adk"
        assert health["status"] == "healthy"

        # Cleanup
        await adk_adapter.shutdown()

        print("✅ Framework adapter integration successful")
        return True

    async def test_simple_end_to_end_flow(self):
        """Test a simplified end-to-end flow."""
        print("🚀 Testing simple end-to-end flow...")

        # Create and initialize ADK adapter
        adk_adapter = AdkFrameworkAdapter()
        await adk_adapter.initialize()

        # Create AI Assistant
        settings = Settings()
        ai_assistant = AIAssistant(settings)

        # Register the ADK adapter
        ai_assistant.framework_registry.register_adapter(FrameworkType.ADK, adk_adapter)

        # Create a simple task request
        user_context = UserContext(user_id="simple_test_user")
        session_context = SessionContext(session_id="simple_session")
        message = UniversalMessage(role="user", content="Simple test message")

        task_request = TaskRequest(
            task_id="simple_test_001",
            task_type="chat",
            description="Simple end-to-end test",
            user_context=user_context,
            session_context=session_context,
            messages=[message],
            execution_config=ExecutionConfig(execution_mode=ExecutionMode.SYNC),
        )

        # Process the request
        result = await ai_assistant.process_request(task_request)

        # Validate result
        assert result is not None
        assert result.task_id == "simple_test_001"
        assert result.status in [TaskStatus.SUCCESS, TaskStatus.ERROR]

        # Cleanup
        await adk_adapter.shutdown()

        print("✅ Simple end-to-end flow successful")
        return True


async def run_async_tests():
    """Run all async integration tests."""
    test_integration = TestComponentIntegration()

    async_tests = [
        test_integration.test_task_routing_logic,
        test_integration.test_framework_adapter_integration,
        test_integration.test_simple_end_to_end_flow,
    ]

    passed = 0
    failed = 0

    for test_func in async_tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__}: {e}")
            failed += 1

    return passed, failed


def main():
    """Run all integration tests."""
    print("🔗 Running Integration Tests")
    print("=" * 50)

    test_integration = TestComponentIntegration()

    # Run sync tests
    sync_passed = 0
    sync_failed = 0

    try:
        test_integration.test_data_contracts_integration()
        sync_passed += 1
    except Exception as e:
        print(f"❌ test_data_contracts_integration: {e}")
        sync_failed += 1

    # Run async tests
    async_passed, async_failed = asyncio.run(run_async_tests())

    total_passed = sync_passed + async_passed
    total_failed = sync_failed + async_failed

    print("=" * 50)
    print(f"📊 Results: {total_passed} passed, {total_failed} failed")
    if total_failed == 0:
        print("🎉 All integration tests passed!")
    else:
        print("⚠️  Some integration tests failed")

    return total_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
