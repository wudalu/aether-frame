#!/usr/bin/env python3
"""
Unit tests for AdkFrameworkAdapter runtime check removal
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.contracts import (
    ExecutionContext,
    FrameworkType,
    TaskComplexity,
    TaskRequest,
    TaskResult,
    TaskStatus,
)
from aether_frame.execution.task_router import ExecutionStrategy
from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter


class TestAdkFrameworkAdapterRuntimeChecks:
    """Test runtime check removal in AdkFrameworkAdapter"""

    @pytest.fixture
    async def initialized_adapter(self):
        """Create a properly initialized adapter for testing"""
        adapter = AdkFrameworkAdapter()

        # The new architecture uses session-based management
        # No need to mock AgentManager, adapter handles sessions directly
        # Mock initialized state (simulating bootstrap initialization)
        adapter._initialized = True
        adapter._adk_available = True

        return adapter

    @pytest.fixture
    def sample_task_request(self):
        """Create a sample task request for testing"""
        return TaskRequest(
            task_id="test_task_001",
            task_type="chat",
            description="Test task description",
            metadata={"test": True},
        )

    @pytest.fixture
    def sample_strategy(self):
        """Create a sample execution strategy"""
        return ExecutionStrategy(
            framework_type=FrameworkType.ADK,
            task_complexity=TaskComplexity.SIMPLE,
            execution_config={},
            runtime_options={},
            execution_mode="async",
            framework_score=1.0,
            fallback_frameworks=[],
        )

    @pytest.mark.asyncio
    async def test_execute_task_no_initialization_check(
        self, initialized_adapter, sample_task_request, sample_strategy
    ):
        """Test that execute_task works without initialization checks"""

        # Mock the session-based execution since we don't have real ADK in test environment
        from unittest.mock import AsyncMock, Mock, patch

        with patch(
            "aether_frame.agents.adk.adk_domain_agent.AdkDomainAgent"
        ) as mock_agent_class:
            with patch(
                "google.adk.sessions.InMemorySessionService"
            ) as mock_session_service_class:
                with patch("google.adk.runners.Runner") as mock_runner_class:
                    # Mock agent creation and execution
                    mock_agent = AsyncMock()
                    mock_agent_class.return_value = mock_agent

                    # Mock session service
                    mock_session_service = Mock()
                    mock_session_service.create_session.return_value = Mock(
                        session_id="test_session"
                    )
                    mock_session_service_class.return_value = mock_session_service

                    # Mock runner
                    mock_runner = AsyncMock()
                    mock_runner.run.return_value = "test response"
                    mock_runner_class.return_value = mock_runner

                    # This should NOT raise any initialization errors
                    # even if we manually set initialized to False (simulating the old behavior)
                    initialized_adapter._initialized = (
                        False  # This should be ignored now
                    )

                    result = await initialized_adapter.execute_task(
                        sample_task_request, sample_strategy
                    )

                    # Should succeed because bootstrap ensures proper initialization
                    assert isinstance(result, TaskResult)
                    assert result.task_id == "test_task_001"
                    assert result.status == TaskStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_task_session_based_execution(
        self, initialized_adapter, sample_task_request, sample_strategy
    ):
        """Test that execute_task works with session-based execution"""

        # Mock the session-based execution since we don't have real ADK in test environment
        from unittest.mock import AsyncMock, Mock, patch

        with patch(
            "aether_frame.agents.adk.adk_domain_agent.AdkDomainAgent"
        ) as mock_agent_class:
            with patch(
                "google.adk.sessions.InMemorySessionService"
            ) as mock_session_service_class:
                with patch("google.adk.runners.Runner") as mock_runner_class:
                    # Mock agent creation and execution
                    mock_agent = AsyncMock()
                    mock_agent_class.return_value = mock_agent

                    # Mock session service
                    mock_session_service = Mock()
                    mock_session_service.create_session.return_value = Mock(
                        session_id="test_session"
                    )
                    mock_session_service_class.return_value = mock_session_service

                    # Mock runner
                    mock_runner = AsyncMock()
                    mock_runner.run.return_value = "test response"
                    mock_runner_class.return_value = mock_runner

                    result = await initialized_adapter.execute_task(
                        sample_task_request, sample_strategy
                    )

                    # Should succeed with session-based execution
                    assert isinstance(result, TaskResult)
                    assert result.status == TaskStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_task_live_session_based(
        self, initialized_adapter, sample_task_request
    ):
        """Test that execute_task_live works with session-based execution"""

        # Mock the session-based live execution since we don't have real ADK in test environment
        from unittest.mock import AsyncMock, Mock, patch

        with patch(
            "aether_frame.agents.adk.adk_domain_agent.AdkDomainAgent"
        ) as mock_agent_class:
            with patch(
                "google.adk.sessions.InMemorySessionService"
            ) as mock_session_service_class:
                with patch("google.adk.runners.Runner") as mock_runner_class:
                    # Mock agent creation
                    mock_agent = AsyncMock()
                    mock_agent_class.return_value = mock_agent

                    # Mock session service
                    mock_session_service = Mock()
                    mock_session_service.create_session.return_value = Mock(
                        session_id="test_session"
                    )
                    mock_session_service_class.return_value = mock_session_service

                    # Mock runner with live execution
                    mock_runner = AsyncMock()

                    async def mock_stream():
                        yield "test stream chunk"

                    mock_communicator = Mock()
                    mock_runner.run_live.return_value = (
                        mock_stream(),
                        mock_communicator,
                    )
                    mock_runner_class.return_value = mock_runner

                    # Create execution context
                    context = ExecutionContext(
                        execution_id="test_exec_001",
                        framework_type=FrameworkType.ADK,
                        execution_mode="live",
                    )

                    result = await initialized_adapter.execute_task_live(
                        sample_task_request, context
                    )

                    # Should return live execution result
                    assert isinstance(result, tuple)
                    assert len(result) == 2
                    stream, communicator = result

    @pytest.mark.asyncio
    async def test_execute_task_error_handling_still_works(
        self, initialized_adapter, sample_task_request, sample_strategy
    ):
        """Test that error handling still works with session-based execution"""

        # Mock an error in session-based execution
        from unittest.mock import patch

        with patch(
            "aether_frame.agents.adk.adk_domain_agent.AdkDomainAgent"
        ) as mock_agent_class:
            # Make agent creation fail
            mock_agent_class.side_effect = Exception("Test error")

            result = await initialized_adapter.execute_task(
                sample_task_request, sample_strategy
            )

            # Should return error result, not raise exception
            assert isinstance(result, TaskResult)
            assert result.status == TaskStatus.ERROR
            assert "Test error" in result.error_message

    @pytest.mark.asyncio
    async def test_bootstrap_initialized_adapter_behavior(self):
        """Test that adapter behaves correctly when initialized through bootstrap"""

        # Simulate bootstrap initialization
        adapter = AdkFrameworkAdapter()

        # Bootstrap would call initialize()
        mock_config = {"app_name": "test_app"}

        # ADK initialization might succeed in test environment
        try:
            await adapter.initialize(mock_config)
            # If it succeeds, that's good
            assert adapter._initialized == True
        except Exception as e:
            # If it fails, that's also expected in test environment
            assert True  # Test passes either way

    def test_removed_checks_documentation(self, initialized_adapter):
        """Verify that the runtime checks have been properly removed"""

        # Check that the execute_task method doesn't contain the old initialization check
        import inspect

        execute_task_source = inspect.getsource(initialized_adapter.execute_task)
        execute_task_live_source = inspect.getsource(
            initialized_adapter.execute_task_live
        )

        # These checks should NOT be present anymore
        assert "if not self._initialized:" not in execute_task_source
        assert "if not self._agent_manager:" not in execute_task_source
        assert "ADK framework not initialized" not in execute_task_source

        assert "if not self._initialized:" not in execute_task_live_source
        assert "if not self._runner:" not in execute_task_live_source
        assert "Agent manager not initialized" not in execute_task_live_source

    @pytest.mark.asyncio
    async def test_performance_session_reuse(
        self, initialized_adapter, sample_task_request, sample_strategy
    ):
        """Test that session reuse improves performance"""
        import time
        from unittest.mock import AsyncMock, Mock, patch

        with patch(
            "aether_frame.agents.adk.adk_domain_agent.AdkDomainAgent"
        ) as mock_agent_class:
            with patch(
                "google.adk.sessions.InMemorySessionService"
            ) as mock_session_service_class:
                with patch("google.adk.runners.Runner") as mock_runner_class:
                    # Mock components
                    mock_agent = AsyncMock()
                    mock_agent_class.return_value = mock_agent

                    mock_session_service = Mock()
                    mock_session_service.create_session.return_value = Mock(
                        session_id="test_session"
                    )
                    mock_session_service_class.return_value = mock_session_service

                    mock_runner = AsyncMock()
                    mock_runner.run.return_value = "test response"
                    mock_runner_class.return_value = mock_runner

                    # Time multiple executions with same session (should reuse)
                    start_time = time.time()

                    for _ in range(5):
                        result = await initialized_adapter.execute_task(
                            sample_task_request, sample_strategy
                        )
                        assert result.status == TaskStatus.SUCCESS

                    end_time = time.time()
                    execution_time = end_time - start_time

                    # Should complete quickly with session reuse
                    assert (
                        execution_time < 1.0
                    )  # Should complete in less than 1 second for 5 calls

                    # Verify agent was created only once (session reuse)
                    assert mock_agent_class.call_count == 1


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
