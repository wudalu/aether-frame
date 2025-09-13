#!/usr/bin/env python3
"""
Unit tests for ToolService runtime check removal
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.tools.base.tool import Tool
from aether_frame.tools.service import ToolService


class MockTool(Tool):
    """Mock tool for testing"""

    def __init__(self, name="mock_tool", namespace=None, initialized=True):
        super().__init__(name, namespace)
        self._initialized = initialized

    @property
    def is_initialized(self):
        return self._initialized

    async def initialize(self):
        self._initialized = True

    async def execute(self, request):
        return {"result": "mock_execution"}

    async def get_schema(self):
        return {"type": "mock"}

    async def get_capabilities(self):
        return ["mock_capability"]

    async def health_check(self):
        return {"status": "healthy"}

    async def cleanup(self):
        pass

    async def validate_parameters(self, parameters):
        return True


class TestToolServiceRuntimeChecks:
    """Test runtime check removal in ToolService"""

    @pytest.fixture
    def tool_service(self):
        """Create tool service for testing"""
        return ToolService()

    @pytest.fixture
    def mock_initialized_tool(self):
        """Create initialized mock tool"""
        return MockTool("initialized_tool", "test", initialized=True)

    @pytest.fixture
    def mock_uninitialized_tool(self):
        """Create uninitialized mock tool"""
        return MockTool("uninitialized_tool", "test", initialized=False)

    @pytest.mark.asyncio
    async def test_register_tool_no_initialization_check(
        self, tool_service, mock_uninitialized_tool
    ):
        """Test that register_tool works without initialization checks"""

        # Mock tool is NOT initialized, but this should be ignored
        assert not mock_uninitialized_tool.is_initialized

        # Register should work without trying to initialize
        await tool_service.register_tool(mock_uninitialized_tool)

        # Tool should be registered
        tools = await tool_service.list_tools()
        assert mock_uninitialized_tool.full_name in tools

        # Tool should NOT have been initialized by the service
        # (because bootstrap ensures tools are pre-initialized)
        # Note: This test verifies the initialization check was removed
        assert not mock_uninitialized_tool.is_initialized

    @pytest.mark.asyncio
    async def test_register_initialized_tool_works(
        self, tool_service, mock_initialized_tool
    ):
        """Test that initialized tools work normally"""

        assert mock_initialized_tool.is_initialized

        await tool_service.register_tool(mock_initialized_tool)

        tools = await tool_service.list_tools()
        assert mock_initialized_tool.full_name in tools

    @pytest.mark.asyncio
    async def test_health_check_always_healthy(self, tool_service):
        """Test that health check always returns healthy (no initialization check)"""

        # Even without initialization, service should report healthy
        # because bootstrap ensures proper initialization
        health = await tool_service.health_check()

        assert health["service_status"] == "healthy"
        assert "total_tools" in health
        assert "namespaces" in health
        assert "tools" in health

    @pytest.mark.asyncio
    async def test_health_check_with_tools(self, tool_service, mock_initialized_tool):
        """Test health check with registered tools"""

        await tool_service.register_tool(mock_initialized_tool)

        health = await tool_service.health_check()

        assert health["service_status"] == "healthy"
        assert health["total_tools"] == 1
        assert mock_initialized_tool.full_name in health["tools"]

    def test_removed_initialization_checks(self, tool_service):
        """Verify that initialization checks have been removed from source code"""
        import inspect

        register_tool_source = inspect.getsource(tool_service.register_tool)
        health_check_source = inspect.getsource(tool_service.health_check)

        # These checks should NOT be present anymore
        assert "if not tool.is_initialized:" not in register_tool_source
        assert "await tool.initialize()" not in register_tool_source

        assert (
            '"healthy" if self._initialized else "not_initialized"'
            not in health_check_source
        )
        assert "self._initialized" not in health_check_source

    @pytest.mark.asyncio
    async def test_bootstrap_initialization_approach(self, tool_service):
        """Test that bootstrap approach eliminates need for runtime checks"""

        # Create a tool that would normally need initialization
        uninitialized_tool = MockTool("test_tool", initialized=False)

        # In bootstrap approach, tools are assumed to be properly initialized
        # when they are registered, so no runtime check is needed
        await tool_service.register_tool(uninitialized_tool)

        # Service should work normally
        tools = await tool_service.list_tools()
        assert "test_tool" in tools

        health = await tool_service.health_check()
        assert health["service_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_service_functionality_preserved(
        self, tool_service, mock_initialized_tool
    ):
        """Test that removing runtime checks doesn't break core functionality"""

        # Register tool
        await tool_service.register_tool(mock_initialized_tool)

        # List tools
        tools = await tool_service.list_tools()
        assert len(tools) == 1
        assert mock_initialized_tool.full_name in tools

        # Get schema
        schema = await tool_service.get_tool_schema(
            mock_initialized_tool.name, mock_initialized_tool.namespace
        )
        assert schema is not None
        assert schema["type"] == "mock"

        # Get capabilities
        capabilities = await tool_service.get_tool_capabilities(
            mock_initialized_tool.name, mock_initialized_tool.namespace
        )
        assert "mock_capability" in capabilities

    @pytest.mark.asyncio
    async def test_performance_improvement_no_runtime_checks(self, tool_service):
        """Test that removing runtime checks improves performance"""
        import time

        # Create multiple uninitialized tools
        tools = [MockTool(f"tool_{i}", initialized=False) for i in range(10)]

        # Register tools - should be fast without runtime initialization checks
        start_time = time.time()

        for tool in tools:
            await tool_service.register_tool(tool)

        end_time = time.time()
        registration_time = end_time - start_time

        # Should complete quickly without initialization overhead
        assert registration_time < 0.1  # Should complete in less than 100ms

        # Verify all tools are registered
        registered_tools = await tool_service.list_tools()
        assert len(registered_tools) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
