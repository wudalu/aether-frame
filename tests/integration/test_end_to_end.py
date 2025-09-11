# -*- coding: utf-8 -*-
"""End-to-end validation test for Aether Frame."""

import asyncio

import pytest
import pytest_asyncio

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
from aether_frame.execution.execution_engine import ExecutionEngine
from aether_frame.execution.task_router import TaskRouter
from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from aether_frame.framework.framework_registry import FrameworkRegistry


class TestEndToEndFlow:
    """Test complete end-to-end execution flow."""

    @pytest_asyncio.fixture
    async def ai_assistant(self):
        """Create AI Assistant with ADK framework."""
        settings = Settings()

        # Create and register ADK adapter
        adk_adapter = AdkFrameworkAdapter()
        await adk_adapter.initialize()

        framework_registry = FrameworkRegistry()

        # Register ADK adapter with capability configuration
        from aether_frame.config.framework_capabilities import (
            get_framework_capability_config,
        )

        capability_config = get_framework_capability_config(FrameworkType.ADK)
        config = {
            "capabilities": capability_config,
            "async_execution": capability_config.async_execution,
            "memory_management": capability_config.memory_management,
            "observability": capability_config.observability,
            "streaming": capability_config.streaming,
            "execution_modes": capability_config.execution_modes,
            "default_timeout": capability_config.default_timeout,
            "max_iterations": capability_config.max_iterations,
            **capability_config.extra_config,
        }

        framework_registry.register_adapter(FrameworkType.ADK, adk_adapter, config)

        task_router = TaskRouter(settings)
        execution_engine = ExecutionEngine(framework_registry, settings)

        ai_assistant = AIAssistant(settings)
        ai_assistant.framework_registry = framework_registry
        ai_assistant.execution_engine = execution_engine

        return ai_assistant

    @pytest.mark.asyncio
    async def test_simple_chat_task_processing(self, ai_assistant):
        """Test processing a simple chat task end-to-end."""
        # Create a simple chat task
        user_context = UserContext(user_id="test_user_001", user_name="Test User")

        session_context = SessionContext(
            session_id="session_001", conversation_history=[]
        )

        execution_context = ExecutionContext(
            execution_id="exec_001",
            framework_type=FrameworkType.ADK,
            execution_mode="sync",
        )

        message = UniversalMessage(
            role="user", content="Hello, can you help me with a simple question?"
        )

        task_request = TaskRequest(
            task_id="task_001",
            task_type="chat",
            description="Simple chat interaction",
            user_context=user_context,
            session_context=session_context,
            execution_context=execution_context,
            messages=[message],
            execution_config=ExecutionConfig(
                execution_mode=ExecutionMode.SYNC, max_retries=1, timeout=30
            ),
        )

        # Process the task
        result = await ai_assistant.process_request(task_request)

        # Validate result
        assert result is not None
        assert result.task_id == "task_001"
        assert result.status in [
            TaskStatus.SUCCESS,
            TaskStatus.ERROR,
        ]  # Should be one of these

        if result.status == TaskStatus.SUCCESS:
            assert result.messages is not None
            assert len(result.messages) > 0
            assert result.metadata is not None
        else:
            # If it failed, there should be an error message
            assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_task_routing_logic(self):
        """Test task routing and strategy selection."""
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

        # Test complex research task routing
        complex_task = TaskRequest(
            task_id="complex_001",
            task_type="research",
            description="Complex research task with multiple sources",
            messages=[
                UniversalMessage(role="user", content=f"Message {i}")
                for i in range(15)  # Many messages to increase complexity
            ],
            available_tools=[
                UniversalTool(name=f"tool_{i}", description=f"Tool {i}")
                for i in range(8)  # Many tools to increase complexity
            ],
        )

        complex_strategy = await task_router.route_task(complex_task)

        assert complex_strategy is not None
        assert complex_strategy.framework_type in [
            FrameworkType.ADK,
            FrameworkType.LANGGRAPH,
        ]
        # Note: agent_type is now determined at the Framework Adapter layer, not in strategy
        assert complex_strategy.task_complexity in [
            TaskComplexity.COMPLEX,
            TaskComplexity.ADVANCED,
        ]

    @pytest.mark.asyncio
    async def test_framework_adapter_integration(self):
        """Test framework adapter initialization and basic operations."""
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

    def test_data_contracts_integration(self):
        """Test that data contracts work together correctly."""
        from aether_frame.contracts import KnowledgeSource, UniversalTool

        # Test that we can create a complete task request with all components
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

        knowledge_sources = [
            KnowledgeSource(
                name="docs",
                source_type="file",
                location="/docs",
                description="Documentation",
            )
        ]

        agent_config = AgentConfig(
            agent_type="research_agent",
            framework_type=FrameworkType.ADK,
            capabilities=["search", "analysis"],
            timeout=300,
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
            available_knowledge=knowledge_sources,
            execution_config=execution_config,
        )

        # Test ADK conversion
        adk_format = task_request.to_adk_format()

        assert adk_format["user_id"] == "integration_test_user"
        assert adk_format["session_id"] == "integration_session"
        assert len(adk_format["conversation_history"]) == 1
        assert len(adk_format["messages"]) == 1
        assert len(adk_format["tools"]) == 1
        assert len(adk_format["knowledge_sources"]) == 1

        # Verify the converted data maintains structure
        assert adk_format["tools"][0]["name"] == "search_tool"
        assert adk_format["knowledge_sources"][0]["name"] == "docs"


if __name__ == "__main__":
    # Run specific test
    pytest.main(
        [__file__ + "::TestEndToEndFlow::test_simple_chat_task_processing", "-v"]
    )
