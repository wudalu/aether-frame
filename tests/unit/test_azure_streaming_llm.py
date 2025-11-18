# -*- coding: utf-8 -*-
"""Unit tests for Azure streaming wrapper."""

import asyncio

import pytest

from aether_frame.framework.adk.azure_streaming_llm import (
    AzureLiveConnection,
    AzureStreamingLLM,
    TextChunk,
)
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types


@pytest.mark.asyncio
async def test_generate_content_async_stream(monkeypatch):
    llm = AzureStreamingLLM("azure/gpt-4o")
    request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part(text="hi")])]
    )

    async def fake_completion(**kwargs):
        async def gen():
            yield object()

        return gen()

    def fake_model_response_to_chunk(_chunk):
        return [(TextChunk(text="hello "), None), (TextChunk(text="world"), "stop")]

    monkeypatch.setattr(llm.llm_client, "acompletion", fake_completion)
    monkeypatch.setattr(
        "aether_frame.framework.adk.azure_streaming_llm._model_response_to_chunk",
        fake_model_response_to_chunk,
    )

    outputs = []
    async for response in llm.generate_content_async(request, stream=True):
        if response.content and response.content.parts:
            outputs.append(response.content.parts[0].text)
    assert outputs == ["hello ", "world", "hello world"]


@pytest.mark.asyncio
async def test_live_connection_restart(monkeypatch):
    llm = AzureStreamingLLM("azure/gpt-4o")
    base_request = LlmRequest(contents=[])
    connection = AzureLiveConnection(llm, base_request)

    async def fake_generate(self, request, stream=True):
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="ok")]),
            partial=False,
        )

    monkeypatch.setattr(
        AzureStreamingLLM,
        "generate_content_async",
        fake_generate,
    )

    async def collect():
        responses = []
        async for resp in connection.receive():
            responses.append(resp)
        return responses

    collector = asyncio.create_task(collect())
    await connection.send_history([types.Content(role="user", parts=[types.Part(text="hi")])])
    results = await asyncio.wait_for(collector, timeout=5)
    assert len(results) == 2
    assert results[0].content.parts[0].text == "ok"
    assert results[1].turn_complete is True
    await connection.close()


@pytest.mark.asyncio
async def test_normalize_history_converts_tool_responses():
    llm = AzureStreamingLLM("azure/gpt-4o")
    base_request = LlmRequest(contents=[])
    connection = AzureLiveConnection(llm, base_request)

    tool_response = types.FunctionResponse(
        name="search_tool",
        id="call-1",
        response={"result": {"items": 3}},
    )
    tool_response_part = types.Part(function_response=tool_response)
    connection._history = [types.Content(role="model", parts=[tool_response_part])]  # type: ignore[attr-defined]
    connection._tool_calls["call-1"] = {"query": "ai streaming"}  # type: ignore[attr-defined]

    normalized = connection._normalize_history()

    assert len(normalized) == 2
    function_call_part = normalized[0].parts[0].function_call
    assert function_call_part.name == "search_tool"
    assert function_call_part.id == "call-1"
    assert function_call_part.args == {"query": "ai streaming"}
    tool_chunk = normalized[1]
    assert tool_chunk.role == "tool"
    assert getattr(tool_chunk.parts[0], "function_response") is not None
