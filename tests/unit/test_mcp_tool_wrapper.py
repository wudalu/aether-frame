# -*- coding: utf-8 -*-
"""Unit tests for MCPTool wrapper behaviors."""

import asyncio
from types import SimpleNamespace

import pytest

import sys
from types import ModuleType


def _ensure_mcp_stubs():
    if "mcp" in sys.modules:
        return

    mcp_module = ModuleType("mcp")
    sys.modules["mcp"] = mcp_module

    client_module = ModuleType("mcp.client")
    sys.modules["mcp.client"] = client_module

    class DummyClientSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def initialize(self):
            return None

        async def call_tool(self, *args, **kwargs):
            return []

    client_module.ClientSession = DummyClientSession
    mcp_module.ClientSession = DummyClientSession

    stream_module = ModuleType("mcp.client.streamable_http")

    class DummyStreamContext:
        async def __aenter__(self):
            return (None, None, None)

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def streamablehttp_client(**kwargs):
        return DummyStreamContext()

    stream_module.streamablehttp_client = streamablehttp_client
    sys.modules["mcp.client.streamable_http"] = stream_module

    types_module = ModuleType("mcp.types")
    types_module.Tool = object
    sys.modules["mcp.types"] = types_module


_ensure_mcp_stubs()

from aether_frame.contracts import (
    ExecutionContext,
    FrameworkType,
    SessionContext,
    ToolRequest,
    ToolStatus,
    UserContext,
    UserPermissions,
)
from aether_frame.contracts.responses import ToolResult
from aether_frame.tools.mcp.client import MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig
from aether_frame.tools.mcp.tool_wrapper import MCPTool


class DummyMCPClient:
    def __init__(self):
        self.is_connected = True
        self.called_with = None
        self.stream_chunks = []
        self.config = MCPServerConfig(
            name="demo",
            endpoint="https://mcp.example.com",
            headers={},
            timeout=30,
        )

    async def call_tool(self, name, arguments, extra_headers=None):
        self.called_with = (name, arguments, extra_headers)
        if isinstance(arguments, dict) and arguments.get("raise") == "connection":
            raise MCPConnectionError("offline")
        if arguments.get("raise") == "tool":
            raise MCPToolError("boom")
        if arguments.get("raise") == "unexpected":
            raise RuntimeError("panic")
        return {"ok": True}

    async def call_tool_stream(self, name, arguments, extra_headers=None):
        if arguments.get("stream_error") == "connection":
            raise MCPConnectionError("offline")
        if arguments.get("stream_error") == "tool":
            raise MCPToolError("broken")

        async def iterator():
            for chunk in self.stream_chunks:
                yield chunk

        return iterator()

    async def disconnect(self):
        self.is_connected = False


def make_tool():
    client = DummyMCPClient()
    tool = MCPTool(
        mcp_client=client,
        tool_name="search",
        tool_description="Search tool",
        tool_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        namespace="demo",
    )
    return tool, client


@pytest.mark.asyncio
async def test_execute_success_and_metadata():
    tool, client = make_tool()
    request = ToolRequest(tool_name="search", parameters={"query": "docs"})
    result = await tool.execute(request)

    assert isinstance(result, ToolResult)
    assert result.status == ToolStatus.SUCCESS
    assert result.metadata["mcp_server"] == "demo"
    assert client.called_with[0] == "search"


@pytest.mark.asyncio
async def test_execute_strips_optional_none_parameters():
    tool, client = make_tool()
    request = ToolRequest(
        tool_name="search",
        parameters={
            "query": "docs",
            "includeHistory": None,
            "filters": ["open", None],
            "context": {"id": "123", "note": None},
        },
    )

    await tool.execute(request)

    assert client.called_with[1] == {
        "query": "docs",
        "filters": ["open"],
        "context": {"id": "123"},
    }


@pytest.mark.asyncio
async def test_execute_handles_connection_error():
    tool, client = make_tool()
    request = ToolRequest(tool_name="search", parameters={"raise": "connection"})
    result = await tool.execute(request)
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "tool.execution"


@pytest.mark.asyncio
async def test_execute_handles_generic_error():
    tool, client = make_tool()
    request = ToolRequest(tool_name="search", parameters={"raise": "unexpected"})
    result = await tool.execute(request)
    assert result.status == ToolStatus.ERROR
    assert result.error.code == "internal.error"


@pytest.mark.asyncio
async def test_execute_stream_converts_chunks():
    tool, client = make_tool()
    client.stream_chunks = [
        {"type": "data", "content": "partial"},
        {"type": "complete", "content": {"result": 1}, "is_final": True},
    ]
    request = ToolRequest(tool_name="search", parameters={"query": "docs"})

    chunks = [chunk async for chunk in tool.execute_stream(request)]
    assert chunks[0].chunk_type.name == "RESPONSE"
    assert chunks[1].chunk_kind == "tool.complete"


@pytest.mark.asyncio
async def test_execute_stream_handles_errors():
    tool, client = make_tool()
    request = ToolRequest(tool_name="search", parameters={"stream_error": "tool"})
    chunks = [chunk async for chunk in tool.execute_stream(request)]
    assert chunks[0].chunk_type.name == "ERROR"
    assert chunks[0].metadata["error_type"] == "MCPToolError"


@pytest.mark.asyncio
async def test_validate_parameters_and_headers():
    tool, client = make_tool()
    good = await tool.validate_parameters({"query": "docs"})
    bad = await tool.validate_parameters({"query": 123})
    assert good is True
    assert bad is False

    request = ToolRequest(
        tool_name="search",
        parameters={},
        metadata={"mcp_headers": {"X-Trace": "abc"}},
        session_context=SessionContext(session_id="sess-1", conversation_id="conv"),
        execution_context=ExecutionContext(
            execution_id="exec-1", framework_type=FrameworkType.ADK, trace_id="trace-1"
        ),
        user_context=UserContext(
            user_id="user-1",
            user_name="alice",
            session_token="token-xyz",
            permissions=UserPermissions(permissions=["mcp.read"]),
        ),
    )
    request.session_id = "sess-override"
    headers = tool._build_request_headers(request)
    assert headers["X-AF-Session-ID"] == "sess-1"
    assert headers["X-AF-Execution-ID"] == "exec-1"
    assert headers["X-AF-User-Name"] == "alice"
    assert headers["X-Trace"] == "abc"
