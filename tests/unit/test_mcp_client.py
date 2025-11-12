# -*- coding: utf-8 -*-
"""Unit tests for MCPClient streaming helpers."""

import asyncio
from contextlib import asynccontextmanager
from types import ModuleType, SimpleNamespace

import pytest

import sys


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


@pytest.mark.asyncio
async def test_disconnect_cleans_up(monkeypatch):
    client = MCPClient(make_config())
    client.is_connected = True
    client._session = object()
    queue = asyncio.Queue()
    client._progress_handlers = {"token": queue}

    class DummyContext:
        def __init__(self):
            self.closed = False

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.closed = True
            return False

    session_ctx = DummyContext()
    stream_ctx = DummyContext()
    client._session_context = session_ctx
    client._stream_context = stream_ctx

    await client.disconnect()
    assert client._progress_handlers == {}
    assert client._session is None
    assert session_ctx.closed is True
    assert stream_ctx.closed is True


@pytest.mark.asyncio
async def test_notification_handler_covers_branches(capsys):
    client = MCPClient(make_config())
    message = SimpleNamespace(method="notifications/message", params={"level": "info", "data": "log"})
    await client._notification_handler(message)

    typed = SimpleNamespace(root=SimpleNamespace(params=SimpleNamespace(level="info", data="typed")))
    await client._notification_handler(typed)


@pytest.mark.asyncio
async def test_connect_invokes_open_session(monkeypatch):
    client = MCPClient(make_config())
    called = []

    async def fake_open():
        client._session = object()
        called.append(True)

    monkeypatch.setattr(client, "_open_persistent_session", fake_open)
    await client.connect()
    assert client.is_connected is True
    assert called == [True]


@pytest.mark.asyncio
async def test_call_tool_raises_when_error_chunk_emitted(monkeypatch):
    client = MCPClient(make_config())
    client.is_connected = True
    client._session = object()

    async def stream_with_error(name, arguments, extra_headers=None):
        yield {"type": "stream_start"}
        yield {"type": "error", "is_final": True, "error": "bad news"}

    monkeypatch.setattr(client, "call_tool_stream", stream_with_error)

    with pytest.raises(MCPToolError, match="bad news"):
        await client.call_tool("search", {})


@pytest.mark.asyncio
async def test_call_tool_stream_drains_remaining_progress(monkeypatch):
    client = MCPClient(make_config())
    client.is_connected = True
    client._session = object()

    async def fake_call_tool(name, arguments, progress_callback=None):
        if progress_callback:
            await progress_callback(0.25, 1.0, "quarter")
            await progress_callback(1.0, 1.0, "done")
        await asyncio.sleep(0)
        return SimpleNamespace(
            content=[SimpleNamespace(text="chunk-a"), SimpleNamespace(text="chunk-b")]
        )

    @asynccontextmanager
    async def fake_session_scope(self, extra_headers=None):
        yield SimpleNamespace(call_tool=fake_call_tool)

    monkeypatch.setattr(MCPClient, "_session_scope", fake_session_scope, raising=False)

    chunks = [
        chunk async for chunk in client.call_tool_stream("search", {"q": "info"})
    ]

    progress_chunks = [chunk for chunk in chunks if chunk["type"] == "progress_update"]
    assert len(progress_chunks) == 2  # one from live loop, one from drain loop
    assert chunks[-1]["type"] == "complete_result"
    assert chunks[-1]["content"][0].text == "chunk-a"
    assert client._progress_handlers == {}


@pytest.mark.asyncio
async def test_call_tool_stream_cleans_handlers_on_scope_failure(monkeypatch):
    client = MCPClient(make_config())
    client.is_connected = True
    client._session = object()

    @asynccontextmanager
    async def failing_scope(self, extra_headers=None):
        raise RuntimeError("scope failure")
        yield  # pragma: no cover

    monkeypatch.setattr(MCPClient, "_session_scope", failing_scope, raising=False)

    chunks = [
        chunk async for chunk in client.call_tool_stream("broken", {"value": 1})
    ]

    assert chunks[0]["type"] == "stream_start"
    assert chunks[-1]["type"] == "error"
    assert client._progress_handlers == {}


@pytest.mark.asyncio
async def test_session_scope_merges_extra_headers(monkeypatch):
    recorded = {}

    class FakeStreamContext:
        def __init__(self, headers):
            recorded["headers"] = headers
            self.closed = False

        async def __aenter__(self):
            return ("read", "write", None)

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.closed = True
            recorded["stream_closed"] = True

    class FakeClientSession:
        def __init__(self, read_stream, write_stream, message_handler):
            self.message_handler = message_handler
            self.closed = False

        async def __aenter__(self):
            recorded["session_entered"] = True
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.closed = True
            recorded["session_closed"] = True

        async def initialize(self):
            recorded["initialized"] = True

    monkeypatch.setattr(
        "aether_frame.tools.mcp.client.streamablehttp_client",
        lambda **kwargs: FakeStreamContext(kwargs["headers"]),
    )
    monkeypatch.setattr(
        "aether_frame.tools.mcp.client.ClientSession", FakeClientSession
    )

    client = MCPClient(make_config())

    async with client._session_scope(extra_headers={"X-Test": "123"}) as session:
        assert session is not None
        assert recorded["initialized"] is True

    assert recorded["headers"]["Authorization"] == "Bearer token"
    assert recorded["headers"]["X-Test"] == "123"
    assert recorded["session_closed"] is True
    assert recorded["stream_closed"] is True


@pytest.mark.asyncio
async def test_notification_handler_typed_notifications(monkeypatch):
    client = MCPClient(make_config())

    class LoggingNotification:
        def __init__(self):
            self.params = SimpleNamespace(level="debug", data="typed log")

    class ResourceUpdatedNotification:
        def __init__(self):
            self.params = SimpleNamespace(uri="doc://1")

    class ResourceListChangedNotification:
        pass

    class ProgressNotification:
        def __init__(self):
            self.params = SimpleNamespace(progress=1, total=2, message="halfway")

    class ServerNotification:
        def __init__(self, root):
            self.root = root

    fake_types = SimpleNamespace(
        ServerNotification=ServerNotification,
        LoggingMessageNotification=LoggingNotification,
        ResourceUpdatedNotification=ResourceUpdatedNotification,
        ResourceListChangedNotification=ResourceListChangedNotification,
        ProgressNotification=ProgressNotification,
    )
    monkeypatch.setattr("aether_frame.tools.mcp.client.types", fake_types)

    for notification_cls in (
        LoggingNotification,
        ResourceUpdatedNotification,
        ResourceListChangedNotification,
        ProgressNotification,
    ):
        message = ServerNotification(notification_cls())
        await client._notification_handler(message)
