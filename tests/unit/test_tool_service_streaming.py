# -*- coding: utf-8 -*-
"""Unit tests for ToolService streaming integration."""

import pytest

from aether_frame.contracts import ToolRequest, ToolResult, ToolStatus
from aether_frame.contracts.enums import TaskChunkType
from aether_frame.contracts.streaming import TaskStreamChunk
from aether_frame.tools.base.tool import Tool
from aether_frame.tools.service import ToolService


class StreamingTool(Tool):
    """Tool that supports native streaming."""

    def __init__(self, name: str = "stream_tool", namespace: str = "test"):
        super().__init__(name=name, namespace=namespace)
        self._initialized = True

    async def initialize(self, config=None):
        self._initialized = True

    async def execute(self, tool_request: ToolRequest) -> ToolResult:
        return ToolResult(
            tool_name=self.full_name,
            tool_namespace=self.namespace,
            status=ToolStatus.SUCCESS,
            result_data="stream-execute",
        )

    async def execute_stream(self, tool_request: ToolRequest):
        yield TaskStreamChunk(
            task_id=f"tool_execution_{self.full_name}",
            chunk_type=TaskChunkType.RESPONSE,
            sequence_id=0,
            content="stream-chunk-1",
            metadata={"tool_name": self.full_name},
        )
        yield TaskStreamChunk(
            task_id=f"tool_execution_{self.full_name}",
            chunk_type=TaskChunkType.COMPLETE,
            sequence_id=1,
            content="stream-complete",
            is_final=True,
            metadata={"tool_name": self.full_name},
        )

    async def get_schema(self):
        return {}

    async def validate_parameters(self, parameters):
        return True

    async def cleanup(self):
        pass


class NonStreamingTool(Tool):
    """Tool without streaming support."""

    def __init__(self, name: str = "sync_tool", namespace: str = "test"):
        super().__init__(name=name, namespace=namespace)
        self._initialized = True

    async def initialize(self, config=None):
        self._initialized = True

    async def execute(self, tool_request: ToolRequest) -> ToolResult:
        return ToolResult(
            tool_name=self.full_name,
            tool_namespace=self.namespace,
            status=ToolStatus.SUCCESS,
            result_data={"echo": tool_request.parameters.get("message", "")},
        )

    async def get_schema(self):
        return {}

    async def validate_parameters(self, parameters):
        return True

    async def cleanup(self):
        pass


@pytest.mark.asyncio
async def test_execute_tool_stream_with_native_streaming():
    service = ToolService()
    await service.register_tool(StreamingTool())

    request = ToolRequest(tool_name="stream_tool", tool_namespace="test")
    chunks = []

    async for chunk in service.execute_tool_stream(request):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert chunks[0].chunk_type == TaskChunkType.RESPONSE
    assert chunks[0].content == "stream-chunk-1"
    assert chunks[1].chunk_type == TaskChunkType.COMPLETE
    assert chunks[1].is_final is True


@pytest.mark.asyncio
async def test_execute_tool_stream_falls_back_to_sync():
    service = ToolService()
    await service.register_tool(NonStreamingTool())

    request = ToolRequest(
        tool_name="sync_tool",
        tool_namespace="test",
        parameters={"message": "hello"},
    )
    chunks = []

    async for chunk in service.execute_tool_stream(request):
        chunks.append(chunk)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == TaskChunkType.RESPONSE
    assert chunk.is_final is True
    assert chunk.metadata.get("fallback_to_sync") is True
    assert chunk.metadata.get("tool_name") == "test.sync_tool"
    assert chunk.content == {"echo": "hello"}


@pytest.mark.asyncio
async def test_execute_tool_stream_missing_tool():
    service = ToolService()
    request = ToolRequest(tool_name="missing_tool")

    chunks = []
    async for chunk in service.execute_tool_stream(request):
        chunks.append(chunk)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_type == TaskChunkType.ERROR
    assert chunk.is_final is True
    assert "Tool missing_tool not found" in chunk.content
