# -*- coding: utf-8 -*-
"""Unit tests for MCPClient streaming helpers."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import sys
from types import ModuleType, SimpleNamespace


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
            return SimpleNamespace(content=[])

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
    mcp_module.client = ModuleType("client")
    mcp_module.client.streamable_http = stream_module

    types_module = ModuleType("mcp.types")
    types_module.Tool = SimpleNamespace
    types_module.ServerNotification = object
    types_module.LoggingMessageNotification = object
    types_module.ResourceUpdatedNotification = object
    types_module.ResourceListChangedNotification = object
    types_module.ProgressNotification = object
    sys.modules["mcp.types"] = types_module
    mcp_module.types = types_module


_ensure_mcp_stubs()

from aether_frame.tools.mcp.client import MCPClient, MCPConnectionError, MCPToolError
from aether_frame.tools.mcp.config import MCPServerConfig


def make_config():
    return MCPServerConfig(
        name="stub",
        endpoint="https://mcp.example.com",
        headers={"Authorization": "Bearer token"},
        timeout=10,
    )


@pytest.mark.asyncio
async def test_call_tool_collects_complete_result(monkeypatch):
    client = MCPClient(make_config())
    client.is_connected = True
    client._session = object()

    async def fake_stream(name, arguments, extra_headers=None):
        yield {"type": "stream_start"}
        yield {"type": "complete_result", "is_final": True, "content": {"ok": True}}

    monkeypatch.setattr(client, "call_tool_stream", fake_stream)

    result = await client.call_tool("search", {"q": "docs"})
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_call_tool_raises_when_no_final_chunk(monkeypatch):
    client = MCPClient(make_config())
    client.is_connected = True
    client._session = object()

    async def incomplete_stream(name, arguments, extra_headers=None):
        yield {"type": "stream_start"}

    monkeypatch.setattr(client, "call_tool_stream", incomplete_stream)

    with pytest.raises(MCPToolError):
        await client.call_tool("search", {})


@pytest.mark.asyncio
async def test_call_tool_stream_emits_progress_and_result(monkeypatch):
    client = MCPClient(make_config())
    client.is_connected = True
    session = SimpleNamespace()
    client._session = session

    async def fake_call_tool(name, arguments, progress_callback=None):
        if progress_callback:
            await progress_callback(0.5, 1.0, "halfway")
        return SimpleNamespace(content=[SimpleNamespace(text="done")])

    @asynccontextmanager
    async def fake_session_scope(self, extra_headers=None):
        yield SimpleNamespace(call_tool=fake_call_tool)

    monkeypatch.setattr(MCPClient, "_session_scope", fake_session_scope, raising=False)

    chunks = [
        chunk
        async for chunk in client.call_tool_stream("search", {"q": "info"})
    ]

    assert chunks[0]["type"] == "stream_start"
    assert any(chunk["type"] == "progress_update" for chunk in chunks)
    assert chunks[-1]["type"] == "complete_result"
    assert chunks[-1]["content"] == "done"


@pytest.mark.asyncio
async def test_call_tool_stream_yields_error_when_session_fails(monkeypatch):
    client = MCPClient(make_config())
    client.is_connected = True
    client._session = object()

    async def failing_call_tool(*args, **kwargs):
        raise RuntimeError("boom")

    @asynccontextmanager
    async def fake_session_scope(self, extra_headers=None):
        yield SimpleNamespace(call_tool=failing_call_tool)

    monkeypatch.setattr(MCPClient, "_session_scope", fake_session_scope, raising=False)

    chunks = [
        chunk
        async for chunk in client.call_tool_stream("search", {"q": "info"})
    ]

    assert chunks[-1]["type"] == "error"
    assert chunks[-1]["is_final"] is True


@pytest.mark.asyncio
async def test_call_tool_stream_requires_connection():
    client = MCPClient(make_config())
    with pytest.raises(MCPConnectionError):
        async for _ in client.call_tool_stream("search", {}):
            pass
