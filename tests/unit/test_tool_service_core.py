# -*- coding: utf-8 -*-
"""Unit tests for ToolService register/execute flows."""

from unittest.mock import MagicMock

import pytest

from aether_frame.contracts import ToolRequest, ToolResult, ToolStatus
from aether_frame.contracts.enums import TaskChunkType
from aether_frame.tools.base.tool import Tool
from aether_frame.tools.service import ToolService


class DummyTool(Tool):
    def __init__(self, name="echo", namespace="builtin", *, validate=True, raise_on_execute=False, result=None):
        super().__init__(name=name, namespace=namespace)
        self.parameters_schema = {"type": "object"}
        self._validate_ok = validate
        self.raise_on_execute = raise_on_execute
        self._result = result or ToolResult(
            tool_name=name,
            tool_namespace=namespace,
            status=ToolStatus.SUCCESS,
            result_data={"ok": True},
        )

    async def initialize(self, config=None):
        self._initialized = True

    async def execute(self, tool_request: ToolRequest) -> ToolResult:
        if self.raise_on_execute:
            raise RuntimeError("boom")
        return self._result

    async def get_schema(self):
        return {"type": "object"}

    async def validate_parameters(self, parameters):
        return self._validate_ok

    async def cleanup(self):
        self._initialized = False


@pytest.mark.asyncio
async def test_register_tool_tracks_namespace():
    service = ToolService()
    tool = DummyTool(name="echo", namespace="builtin")

    await service.register_tool(tool)

    assert service._tools["builtin.echo"] is tool
    assert "builtin" in service._tool_namespaces
    assert "echo" in service._tool_namespaces["builtin"]


@pytest.mark.asyncio
async def test_execute_tool_success_returns_tool_result(monkeypatch):
    service = ToolService()
    tool = DummyTool()
    await service.register_tool(tool)

    result = await service.execute_tool(
        ToolRequest(tool_name="echo", tool_namespace="builtin", parameters={"value": 1})
    )

    assert result.status == ToolStatus.SUCCESS
    assert result.result_data == {"ok": True}


@pytest.mark.asyncio
async def test_execute_tool_matches_full_name_without_namespace():
    service = ToolService()
    tool = DummyTool()
    await service.register_tool(tool)

    result = await service.execute_tool(
        ToolRequest(tool_name="builtin.echo", parameters={})
    )

    assert result.status == ToolStatus.SUCCESS


@pytest.mark.asyncio
async def test_execute_tool_validates_parameters():
    service = ToolService()
    tool = DummyTool(validate=False)
    await service.register_tool(tool)

    result = await service.execute_tool(
        ToolRequest(tool_name="echo", tool_namespace="builtin", parameters={})
    )

    assert result.status == ToolStatus.ERROR
    assert result.error.code == "tool.invalid_parameters"


@pytest.mark.asyncio
async def test_execute_tool_handles_missing_tool():
    service = ToolService()

    result = await service.execute_tool(
        ToolRequest(tool_name="missing", tool_namespace="builtin", parameters={})
    )

    assert result.status == ToolStatus.NOT_FOUND
    assert result.error.code == "tool.not_declared"


@pytest.mark.asyncio
async def test_execute_tool_handles_execution_errors():
    service = ToolService()
    tool = DummyTool(raise_on_execute=True)
    await service.register_tool(tool)

    result = await service.execute_tool(
        ToolRequest(tool_name="echo", tool_namespace="builtin", parameters={"foo": "bar"})
    )

    assert result.status == ToolStatus.ERROR
    assert result.error.code == "tool.execution"


@pytest.mark.asyncio
async def test_get_tool_schema_and_capabilities():
    service = ToolService()
    tool = DummyTool()
    await service.register_tool(tool)

    schema = await service.get_tool_schema("echo", "builtin")
    assert schema == {"type": "object"}

    capabilities = await service.get_tool_capabilities("echo", "builtin")
    assert capabilities == []

    missing_schema = await service.get_tool_schema("missing")
    assert missing_schema is None


@pytest.mark.asyncio
async def test_execute_tool_stream_parameter_validation_error():
    service = ToolService()
    tool = DummyTool(validate=False)
    await service.register_tool(tool)

    request = ToolRequest(tool_name="echo", tool_namespace="builtin")
    chunks = [chunk async for chunk in service.execute_tool_stream(request)]

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == TaskChunkType.ERROR
    assert chunk.content["code"] == "tool.invalid_parameters"
