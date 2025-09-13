#!/usr/bin/env python3
"""
Unit tests for AdkDomainAgent runtime check removal
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
from aether_frame.contracts import AgentConfig, AgentRequest, FrameworkType, TaskRequest


class TestAdkDomainAgentRuntimeChecks:
    """Test runtime check removal in AdkDomainAgent"""

    @pytest.fixture
    def agent_config(self):
        """Create agent config for testing"""
        return AgentConfig(
            name="test_adk_agent",
            agent_type="conversational_agent",
            framework_type=FrameworkType.ADK,
            model_config={"model": "gemini-1.5-flash"},
        )

    @pytest.fixture
    def agent_request(self, agent_config):
        """Create agent request for testing"""
        task_request = TaskRequest(
            task_id="test_task_001", task_type="chat", description="Test task"
        )

        return AgentRequest(
            agent_config=agent_config,
            task_request=task_request,
            agent_type="conversational_agent",
            metadata={"test": True},
        )

    @pytest.fixture
    def runtime_context(self):
        """Create runtime context for testing"""
        return {
            "is_runtime_ready": True,
            "framework_type": FrameworkType.ADK,
            "adk_available": True,
            "runner": Mock(),
            "session_service": Mock(),
        }

    @pytest.fixture
    def adk_agent(self, agent_config, runtime_context):
        """Create AdkDomainAgent instance for testing"""
        agent = AdkDomainAgent("test_agent_id", agent_config.__dict__, runtime_context)

        # Mock hooks to avoid initialization issues
        agent.hooks = AsyncMock()
        agent.hooks.before_execution = AsyncMock()
        agent.hooks.after_execution = AsyncMock()
        agent.hooks.on_agent_created = AsyncMock()

        return agent

    @pytest.mark.asyncio
    async def test_execute_no_initialization_check(self, adk_agent, agent_request):
        """Test that execute method works without initialization checks"""

        # Mock the ADK execution methods
        with patch.object(adk_agent, "_execute_adk_task") as mock_execute:
            from aether_frame.contracts import TaskResult, TaskStatus

            mock_result = TaskResult(
                task_id="test_task_001",
                status=TaskStatus.SUCCESS,
                result_data={"response": "test response"},
                messages=[],
            )
            mock_execute.return_value = mock_result

            # Set initialized to False - this should be ignored now
            adk_agent._initialized = False

            result = await adk_agent.execute(agent_request)

            # Should succeed despite _initialized=False
            assert isinstance(result, TaskResult)
            assert result.status == TaskStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_with_runtime_no_context_check(
        self, adk_agent, agent_request, runtime_context
    ):
        """Test that execute_with_runtime works without runtime context checks"""

        # Mock the ADK execution methods
        with patch.object(adk_agent, "_execute_adk_task_with_runtime") as mock_execute:
            from aether_frame.contracts import TaskResult, TaskStatus

            mock_result = TaskResult(
                task_id="test_task_001",
                status=TaskStatus.SUCCESS,
                result_data={"response": "test response"},
                messages=[],
            )
            mock_execute.return_value = mock_result

            # Set runtime context to NOT ready - should be ignored
            runtime_context["is_runtime_ready"] = False

            result = await adk_agent.execute_with_runtime(
                agent_request, runtime_context
            )

            # Should execute with runtime method, not fallback
            mock_execute.assert_called_once_with(agent_request, runtime_context)
            assert result.status == TaskStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_live_with_runtime_no_initialization_check(
        self, adk_agent, agent_request, runtime_context
    ):
        """Test that execute_live_with_runtime works without initialization checks"""

        # Mock the event converter and live execution
        with patch(
            "aether_frame.agents.adk.adk_domain_agent.AdkEventConverter"
        ) as mock_converter:
            mock_converter_instance = AsyncMock()
            mock_converter.return_value = mock_converter_instance

            # Mock stream and communicator
            async def mock_stream():
                from aether_frame.contracts import TaskChunkType, TaskStreamChunk

                yield TaskStreamChunk(
                    task_id="test_task_001",
                    chunk_type=TaskChunkType.RESPONSE,
                    sequence_id=0,
                    content="test response",
                    is_final=True,
                )

            mock_communicator = Mock()
            mock_converter_instance.convert_to_live_execution.return_value = (
                mock_stream(),
                mock_communicator,
            )

            # Set initialized to False - should be ignored
            adk_agent._initialized = False

            result = await adk_agent.execute_live_with_runtime(
                agent_request, runtime_context
            )

            # Should return valid live execution result
            assert isinstance(result, tuple)
            assert len(result) == 2
            stream, communicator = result

            # Test stream works
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)
            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_initialize_with_runtime_no_ready_check(self, adk_agent):
        """Test that initialize_with_runtime works without ready checks"""

        # Set runtime context to NOT ready - should be ignored
        adk_agent.runtime_context = {
            "is_runtime_ready": False,  # Should be ignored
            "runner": Mock(),
            "session_service": Mock(),
        }

        await adk_agent.initialize_with_runtime()

        # Should have been initialized despite is_runtime_ready=False
        assert adk_agent._initialized == True
        adk_agent.hooks.on_agent_created.assert_called_once()

    def test_removed_initialization_checks(self, adk_agent):
        """Verify that initialization checks have been removed from source code"""
        import inspect

        execute_source = inspect.getsource(adk_agent.execute)
        execute_with_runtime_source = inspect.getsource(adk_agent.execute_with_runtime)
        execute_live_source = inspect.getsource(adk_agent.execute_live_with_runtime)
        initialize_runtime_source = inspect.getsource(adk_agent.initialize_with_runtime)

        # These checks should NOT be present anymore
        assert "if not self._initialized:" not in execute_source
        assert "ADK agent not initialized" not in execute_source

        assert "if not self._initialized:" not in execute_with_runtime_source
        assert "ADK agent not initialized" not in execute_with_runtime_source

        assert "if not self._initialized:" not in execute_live_source
        assert "ADK agent not initialized" not in execute_live_source

        # Runtime context checks should also be removed
        assert (
            'if runtime_context.get("is_runtime_ready", False):'
            not in execute_with_runtime_source
        )
        assert (
            'if self.runtime_context and self.runtime_context.get("is_runtime_ready", False):'
            not in initialize_runtime_source
        )

    def test_bootstrap_ensures_initialization(self, adk_agent):
        """Test that bootstrap approach eliminates need for runtime checks"""

        # In bootstrap approach, all components are pre-initialized
        # So runtime checks become unnecessary

        # Agent should be created in an initialized state
        assert hasattr(adk_agent, "_initialized")
        assert hasattr(adk_agent, "runtime_context")
        assert adk_agent.runtime_context is not None

        # Runtime context should have required components
        assert "runner" in adk_agent.runtime_context
        assert "session_service" in adk_agent.runtime_context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
