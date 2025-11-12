# -*- coding: utf-8 -*-
"""Unit tests for ToolService register/execute flows."""

import sys
from types import ModuleType, SimpleNamespace

import pytest

from aether_frame.contracts import ToolRequest, ToolResult, ToolStatus
from aether_frame.contracts.enums import TaskChunkType
from aether_frame.contracts.streaming import TaskStreamChunk
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


class StreamingTool(DummyTool):
    def __init__(
        self,
        *,
        stream_chunks=None,
        raise_in_stream=False,
        not_implemented=False,
        result=None,
    ):
        super().__init__(result=result)
        self.stream_chunks = stream_chunks or [
            TaskStreamChunk(
                task_id="stream",
                chunk_type=TaskChunkType.RESPONSE,
                sequence_id=0,
                content={"ok": True},
            )
        ]
        self.raise_in_stream = raise_in_stream
        self.not_implemented = not_implemented

    async def execute_stream(self, tool_request):
        if self.raise_in_stream:
            raise RuntimeError("stream boom")
        if self.not_implemented:
            raise NotImplementedError()
        for chunk in self.stream_chunks:
            yield chunk


class HealthTool(DummyTool):
    def __init__(self):
        super().__init__()
        self.cleaned = False

    async def health_check(self):
        return {"status": "ok"}

    async def cleanup(self):
        self.cleaned = True


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


@pytest.mark.asyncio
async def test_initialize_loads_builtin_tools(tmp_path, monkeypatch):
    service = ToolService()
    config = {"enable_mcp": False, "enable_adk_native": False}
    await service.initialize(config)
    health = await service.health_check()
    assert health["total_tools"] >= 3

    await service.shutdown()
    assert service._tools == {}


@pytest.mark.asyncio
async def test_execute_tool_stream_emits_native_chunks():
    service = ToolService()
    chunk = TaskStreamChunk(
        task_id="stream",
        chunk_type=TaskChunkType.RESPONSE,
        sequence_id=0,
        content={"message": "hi"},
        is_final=True,
    )
    tool = StreamingTool(stream_chunks=[chunk])
    await service.register_tool(tool)

    request = ToolRequest(tool_name="echo", tool_namespace="builtin", parameters={})
    chunks = [item async for item in service.execute_tool_stream(request)]

    assert chunks == [chunk]


@pytest.mark.asyncio
async def test_execute_tool_stream_fallback_to_sync_includes_metadata():
    service = ToolService()
    result = ToolResult(
        tool_name="echo",
        tool_namespace="builtin",
        status=ToolStatus.SUCCESS,
        result_data={"payload": True},
    )
    tool = StreamingTool(not_implemented=True, result=result)
    await service.register_tool(tool)

    request = ToolRequest(tool_name="echo", tool_namespace="builtin", parameters={})
    chunks = [item async for item in service.execute_tool_stream(request)]

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == TaskChunkType.RESPONSE
    assert chunk.metadata["fallback_to_sync"] is True
    assert chunk.content == {"payload": True}


@pytest.mark.asyncio
async def test_execute_tool_stream_handles_stream_exception():
    service = ToolService()
    tool = StreamingTool(raise_in_stream=True)
    await service.register_tool(tool)

    request = ToolRequest(tool_name="echo", tool_namespace="builtin", parameters={})
    chunks = [item async for item in service.execute_tool_stream(request)]

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == TaskChunkType.ERROR
    assert chunk.metadata["status"] == ToolStatus.ERROR.value


@pytest.mark.asyncio
async def test_load_mcp_tools_registers_discovered_tools(monkeypatch):
    service = ToolService()
    service._config = {
        "mcp_servers": [
            {"name": "stub", "endpoint": "https://mcp", "headers": {}, "timeout": 5},
            {"name": "bad", "endpoint": "https://bad", "headers": {}, "timeout": 5},
        ]
    }

    class FakeClient:
        def __init__(self, config):
            if config.name == "bad":
                raise RuntimeError("cannot init")
            self.config = config
            self.connected = False

        async def connect(self):
            self.connected = True

        async def discover_tools(self):
            return [
                SimpleNamespace(
                    name=f"{self.config.name}.search",
                    description="search tool",
                    parameters_schema={"type": "object"},
                )
            ]

    class FakeServerConfig:
        def __init__(self, name, endpoint, headers, timeout):
            self.name = name
            self.endpoint = endpoint
            self.headers = headers
            self.timeout = timeout

    class FakeMCPTool(Tool):
        def __init__(self, mcp_client, tool_name, tool_description, tool_schema, namespace):
            super().__init__(name=tool_name, namespace=namespace)
            self.parameters_schema = tool_schema
            self.description = tool_description

        async def initialize(self):
            return None

        async def execute(self, tool_request: ToolRequest) -> ToolResult:
            return ToolResult(
                tool_name=self.name,
                tool_namespace=self.namespace,
                status=ToolStatus.SUCCESS,
                result_data={},
            )

        async def validate_parameters(self, parameters):
            return True

        async def get_schema(self):
            return self.parameters_schema

        async def get_capabilities(self):
            return []

        async def cleanup(self):
            return None

    fake_mcp_module = ModuleType("aether_frame.tools.mcp")
    fake_mcp_module.MCPClient = FakeClient
    fake_mcp_module.MCPServerConfig = FakeServerConfig
    fake_mcp_module.MCPTool = FakeMCPTool
    monkeypatch.setitem(sys.modules, "aether_frame.tools.mcp", fake_mcp_module)

    await service._load_mcp_tools()
    assert "stub.search" in service._tools
    assert all(tool.namespace == "stub" for tool in service._tools.values())


@pytest.mark.asyncio
async def test_health_check_reports_tool_status():
    service = ToolService()
    tool = HealthTool()
    await service.register_tool(tool)

    report = await service.health_check()
    assert report["total_tools"] == 1
    assert report["tools"]["builtin.echo"]["status"] == "ok"


@pytest.mark.asyncio
async def test_shutdown_cleans_registered_tools():
    service = ToolService()
    tool = HealthTool()
    await service.register_tool(tool)

    await service.shutdown()
    assert tool.cleaned is True
    assert service._tools == {}
    assert service._tool_namespaces == {}
