# -*- coding: utf-8 -*-
"""Unit tests for base Tool contract defaults."""

import pytest

from aether_frame.tools.base.tool import Tool
from aether_frame.contracts import ToolRequest, ToolResult, ToolStatus


class SampleTool(Tool):
    async def initialize(self, config=None):
        self._initialized = True

    async def execute(self, tool_request: ToolRequest) -> ToolResult:
        return ToolResult(
            tool_name=self.full_name,
            tool_namespace=self.namespace,
            status=ToolStatus.SUCCESS,
        )

    async def get_schema(self):
        return {"name": self.full_name}

    async def validate_parameters(self, parameters):
        return True

    async def cleanup(self):
        self._initialized = False


@pytest.mark.asyncio
async def test_tool_full_name_and_health_defaults():
    tool = SampleTool(name="echo", namespace="builtin")
    assert tool.full_name == "builtin.echo"

    health = await tool.health_check()
    assert health["status"] == "not_initialized"

    await tool.initialize()
    assert tool.is_initialized is True

    health_after_init = await tool.health_check()
    assert health_after_init["status"] == "healthy"

    await tool.cleanup()
    assert tool.is_initialized is False


@pytest.mark.asyncio
async def test_tool_capabilities_and_execution():
    tool = SampleTool(name="echo")
    await tool.initialize()
    request = ToolRequest(tool_name="echo")
    result = await tool.execute(request)
    assert result.tool_name == "echo"
    assert await tool.validate_parameters({}) is True

    capabilities = await tool.get_capabilities()
    assert capabilities == []
