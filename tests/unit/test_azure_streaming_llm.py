# -*- coding: utf-8 -*-
"""Unit tests for Azure streaming wrapper."""

import asyncio

import pytest

pytest.importorskip("litellm")

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
    await connection.send_history(
        [types.Content(role="user", parts=[types.Part(text="hi")])]
    )
    await asyncio.sleep(0.05)
    await connection.close()
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
    # Ensure args are preserved for subsequent normalizations
    normalized_again = connection._normalize_history()
    function_call_part_again = normalized_again[0].parts[0].function_call
    assert function_call_part_again.args == {"query": "ai streaming"}
    assert connection._tool_calls["call-1"] == {"query": "ai streaming"}


@pytest.mark.asyncio
async def test_receive_stays_open_until_connection_closed():
    function_call = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=types.FunctionCall(
                        name="lookup", args={}, id="call-1"
                    )
                )
            ],
        ),
        partial=False,
    )
    final_text = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(text="final answer")],
        ),
        partial=False,
    )

    class StubStreamingLLM:
        def __init__(self, sequences):
            self._sequences = list(sequences)

        async def generate_content_async(self, request, stream=True):
            seq = self._sequences.pop(0)
            for item in seq:
                yield item

    stub_llm = StubStreamingLLM([[function_call], [final_text]])
    base_request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part(text="hi")])]
    )
    connection = AzureLiveConnection(stub_llm, base_request)

    collected: list[LlmResponse] = []

    async def consume():
        async for resp in connection.receive():
            collected.append(resp)

    consumer = asyncio.create_task(consume())
    await connection.send_history(base_request.contents)
    await asyncio.sleep(0.05)
    assert collected
    assert collected[0].content.parts[0].function_call.name == "lookup"
    assert not consumer.done()

    tool_response = types.FunctionResponse(
        name="lookup", id="call-1", response={"result": "ok"}
    )
    await connection.send_content(
        types.Content(
            role="tool", parts=[types.Part(function_response=tool_response)]
        )
    )

    async def wait_for(count: int) -> bool:
        for _ in range(20):
            if len(collected) >= count:
                return True
            await asyncio.sleep(0.05)
        return False
    assert await wait_for(2)
    assert any(
        resp.content
        and resp.content.parts
        and getattr(resp.content.parts[0], "text", None) == "final answer"
        for resp in collected
    )

    await connection.close()
    await asyncio.wait_for(consumer, timeout=1)
    assert collected[-1].turn_complete is True


@pytest.mark.asyncio
async def test_normalize_history_skips_existing_function_calls():
    llm = AzureStreamingLLM("azure/gpt-4o")
    base_request = LlmRequest(contents=[])
    connection = AzureLiveConnection(llm, base_request)

    function_call = types.Content(
        role="model",
        parts=[
            types.Part(
                function_call=types.FunctionCall(
                    name="search_tool", args={"query": "x"}, id="call-1"
                )
            )
        ],
    )
    tool_response = types.Content(
        role="tool",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    name="search_tool",
                    id="call-1",
                    response={"result": "ok"},
                )
            )
        ],
    )
    connection._history = [function_call, tool_response]  # type: ignore[attr-defined]
    connection._tool_calls["call-1"] = {"query": "x"}  # type: ignore[attr-defined]

    normalized = connection._normalize_history()
    assert len(normalized) == 2
    assert normalized[0].parts[0].function_call.args == {"query": "x"}
    assert normalized[1].role == "tool"
    assert connection._tool_calls["call-1"] == {"query": "x"}


@pytest.mark.asyncio
async def test_normalize_history_reorders_tool_response_before_call():
    llm = AzureStreamingLLM("azure/gpt-4o")
    base_request = LlmRequest(contents=[])
    connection = AzureLiveConnection(llm, base_request)

    tool_response = types.Content(
        role="tool",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    name="search_tool", id="call-1", response={"result": "ok"}
                )
            )
        ],
    )
    function_call = types.Content(
        role="model",
        parts=[
            types.Part(
                function_call=types.FunctionCall(
                    name="search_tool", args={"query": "x"}, id="call-1"
                )
            )
        ],
    )
    connection._history = [tool_response, function_call]  # type: ignore[attr-defined]
    connection._tool_calls["call-1"] = {"query": "x"}  # type: ignore[attr-defined]

    normalized = connection._normalize_history()
    assert normalized[0].parts[0].function_call.id == "call-1"
    assert normalized[1].role == "tool"


@pytest.mark.asyncio
async def test_send_content_reorders_newest_first_history():
    llm = AzureStreamingLLM("azure/gpt-4o")
    base_request = LlmRequest(contents=[])
    connection = AzureLiveConnection(llm, base_request)

    newest_first_history = [
        types.Content(role="user", parts=[types.Part(text="third")]),
        types.Content(role="model", parts=[types.Part(text="second")]),
        types.Content(role="user", parts=[types.Part(text="first")]),
    ]
    await connection.send_history(newest_first_history)

    latest_message = types.Content(role="user", parts=[types.Part(text="third")])
    await connection.send_content(latest_message)

    ordered_texts = [
        part.text
        for item in connection._history  # type: ignore[attr-defined]
        for part in (item.parts or [])
        if getattr(part, "text", None)
    ]
    assert ordered_texts == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_no_turn_complete_emitted_before_tool_response():
    function_call = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(
                    function_call=types.FunctionCall(
                        name="lookup", args={}, id="call-1"
                    )
                )
            ],
        ),
        partial=False,
    )
    final_text = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(text="final answer")],
        ),
        partial=False,
    )

    class StubStreamingLLM:
        def __init__(self):
            self._sequences = [[function_call], [final_text]]

        async def generate_content_async(self, request, stream=True):
            seq = self._sequences.pop(0)

            for item in list(seq):
                yield item

    base_request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part(text="hi")])]
    )
    connection = AzureLiveConnection(StubStreamingLLM(), base_request)
    await connection.send_history(base_request.contents)
    await asyncio.sleep(0.05)

    drained: list[LlmResponse] = []
    while not connection._response_queue.empty():  # type: ignore[attr-defined]
        drained.append(connection._response_queue.get_nowait())  # type: ignore[attr-defined]

    assert drained
    assert not any(getattr(item, "turn_complete", False) for item in drained)

    tool_response = types.FunctionResponse(
        name="lookup", id="call-1", response={"result": "ok"}
    )
    await connection.send_content(
        types.Content(
            role="tool", parts=[types.Part(function_response=tool_response)]
        )
    )
    await asyncio.sleep(0.05)
    await connection.close()
