# -*- coding: utf-8 -*-
"""Reworked DeepSeek streaming adapter with predictable shutdown semantics."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
from contextlib import aclosing, asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from google.adk.models.base_llm_connection import BaseLlmConnection
from google.adk.models.lite_llm import (
    LiteLlm,
    LiteLLMClient,
    FunctionChunk,
    TextChunk,
    UsageMetadataChunk,
    _model_response_to_chunk,
    _get_completion_inputs,
    _build_request_log,
    _message_to_generate_content_response,
)
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from litellm import ChatCompletionAssistantMessage, ChatCompletionMessageToolCall, Function

logger = logging.getLogger(__name__)

_STREAM_FINISHED = object()
_MAX_DEBUG_VALUE_LENGTH = 800


def _debug_repr(value: Any, limit: int = _MAX_DEBUG_VALUE_LENGTH) -> str:
    try:
        text = repr(value)
    except Exception:  # noqa: BLE001
        return f"<repr-unavailable:{type(value).__name__}>"
    return text if len(text) <= limit else f"{text[:limit]}…"


def _preview(text: Optional[str], limit: int = 120) -> Optional[str]:
    if not text:
        return text
    return text if len(text) <= limit else f"{text[:limit]}…"


def _describe_chunk(chunk: Any) -> Dict[str, Any]:
    if isinstance(chunk, FunctionChunk):
        return {
            "name": chunk.name,
            "args_preview": _preview(chunk.args),
            "index": chunk.index,
            "id": chunk.id,
        }
    if isinstance(chunk, TextChunk):
        return {
            "length": len(chunk.text) if chunk.text else 0,
            "text_preview": _preview(chunk.text),
        }
    if isinstance(chunk, UsageMetadataChunk):
        return {
            "prompt_tokens": chunk.prompt_tokens,
            "completion_tokens": chunk.completion_tokens,
            "total_tokens": chunk.total_tokens,
        }
    return {"chunk_repr": _debug_repr(chunk)}


def _safe_get(value: Any, key: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    if hasattr(value, key):
        return getattr(value, key)
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except Exception:  # noqa: BLE001
            return default
    return default


def _clone_content(content: types.Content) -> types.Content:
    if hasattr(content, "model_copy"):
        return content.model_copy(deep=True)
    return types.Content.model_validate(content)


@dataclass
class ReasoningChunk:
    text: str
    is_final: bool = False


def _extract_reasoning_segments(message: Any) -> List[str]:
    reasoning = _safe_get(message, "reasoning_content")
    if not reasoning:
        return []

    segments: List[str] = []
    source = reasoning if isinstance(reasoning, list) else [reasoning]
    for item in source:
        text = ""
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = item.get("text") or item.get("content") or ""
        else:
            text = getattr(item, "text", None) or getattr(item, "content", None) or ""
            if not text and hasattr(item, "get"):
                text = item.get("text") or item.get("content") or ""
        if text:
            segments.append(text)
    return segments


def _extract_reasoning_chunks(response: Any) -> List[Tuple[ReasoningChunk, Optional[str]]]:
    chunks: List[Tuple[ReasoningChunk, Optional[str]]] = []
    for choice in _safe_get(response, "choices") or []:
        finish_reason = _safe_get(choice, "finish_reason")
        message = _safe_get(choice, "message") or _safe_get(choice, "delta")
        for segment in _extract_reasoning_segments(message):
            chunks.append((ReasoningChunk(segment, bool(finish_reason)), finish_reason))
    return chunks


def _coerce_tool_args(args: Any) -> str:
    if isinstance(args, (dict, list)):
        try:
            return json.dumps(args)
        except (TypeError, ValueError):
            return str(args)
    return args or ""


class _AwaitableLiteLLMClient(LiteLLMClient):
    async def acompletion(self, *args, **kwargs):
        result = await super().acompletion(*args, **kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result


class DeepSeekStreamingLLM(LiteLlm):
    """LiteLLM-backed DeepSeek adapter using deterministic stream lifecycle."""

    def __init__(
        self,
        model: str = "deepseek/deepseek-chat",
        *,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or kwargs.pop("deepseek_api_key", None)
        api_base = (
            api_base
            or os.getenv("DEEPSEEK_API_BASE")
            or os.getenv("DEEPSEEK_BASE_URL")
            or kwargs.pop("deepseek_base_url", None)
            or "https://api.deepseek.com/v1"
        )

        extra = dict(kwargs)
        if api_key:
            extra.setdefault("api_key", api_key)
        if api_base:
            extra.setdefault("api_base", api_base)

        super().__init__(model=model, **extra)
        self._api_key = api_key
        self._api_base = api_base
        self.llm_client = _AwaitableLiteLLMClient()

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if not stream:
            async for resp in super().generate_content_async(llm_request, stream=False):
                yield resp
            return

        async def _generator():
            self._maybe_append_user_content(llm_request)
            logger.debug(_build_request_log(llm_request))

            messages, tools, response_format, generation_params = _get_completion_inputs(llm_request)

            if "functions" in self._additional_args:
                tools = None

            completion_args: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "response_format": response_format,
                "stream": True,
            }
            completion_args.update(self._additional_args)
            if generation_params:
                completion_args.update(generation_params)

            stream_options = completion_args.get("stream_options")
            if stream_options is None:
                completion_args["stream_options"] = {"include_usage": True}
            elif isinstance(stream_options, dict):
                stream_options.setdefault("include_usage", True)

            logger.debug(
                "DeepSeekStreaming: requesting stream (model=%s tools=%s)",
                self.model,
                bool(tools),
            )
            stream_source = await self.llm_client.acompletion(**completion_args)

            if inspect.isawaitable(stream_source):
                stream_source = await stream_source
                logger.debug(
                    "DeepSeekStreaming: awaited stream coroutine -> %s",
                    type(stream_source).__name__,
                )

            text_buffer = ""
            function_calls: Dict[int, Dict[str, Optional[str]]] = {}
            aggregated_response: Optional[LlmResponse] = None
            aggregated_with_tool: Optional[LlmResponse] = None
            usage_metadata: Optional[types.GenerateContentResponseUsageMetadata] = None
            fallback_index = 0
            event_count = 0

            async for part in stream_source:
                event_count += 1
                logger.debug("DeepSeekStreaming: raw part %s", _debug_repr(part))

                for reasoning_chunk, _ in _extract_reasoning_chunks(part):
                    if reasoning_chunk.text.strip():
                        yield LlmResponse(
                            content=types.Content(
                                role="model",
                                parts=[types.Part.from_text(text=reasoning_chunk.text)],
                            ),
                            partial=True,
                            custom_metadata={
                                "stage": "plan",
                                "plan_text": reasoning_chunk.text,
                                "event_type": "plan_summary" if reasoning_chunk.is_final else "plan_delta",
                                "chunk_kind": "plan.summary" if reasoning_chunk.is_final else "plan.delta",
                                "source": "deepseek.reasoning",
                            },
                        )

                for chunk, finish in _model_response_to_chunk(part):
                    if isinstance(chunk, FunctionChunk):
                        index = chunk.index or fallback_index
                        if index not in function_calls:
                            function_calls[index] = {"name": "", "args": "", "id": None}

                        if chunk.name:
                            function_calls[index]["name"] += chunk.name
                        if chunk.args:
                            function_calls[index]["args"] += chunk.args
                            try:
                                json.loads(function_calls[index]["args"])
                                fallback_index += 1
                            except json.JSONDecodeError:
                                pass
                        function_calls[index]["id"] = chunk.id or function_calls[index]["id"] or str(index)

                    elif isinstance(chunk, TextChunk):
                        text_buffer += chunk.text
                        yield _message_to_generate_content_response(
                            ChatCompletionAssistantMessage(role="assistant", content=chunk.text),
                            is_partial=True,
                        )
                    elif isinstance(chunk, UsageMetadataChunk):
                        usage_metadata = types.GenerateContentResponseUsageMetadata(
                            prompt_token_count=chunk.prompt_tokens,
                            candidates_token_count=chunk.completion_tokens,
                            total_token_count=chunk.total_tokens,
                        )

                    if finish in {"tool_calls", "stop"} and function_calls:
                        tool_calls = []
                        for index, payload in function_calls.items():
                            if payload["id"]:
                                tool_calls.append(
                                    ChatCompletionMessageToolCall(
                                        type="function",
                                        id=payload["id"],
                                        function=Function(
                                            name=payload["name"],
                                            arguments=_coerce_tool_args(payload["args"]),
                                            index=index,
                                        ),
                                    )
                                )
                        aggregated_with_tool = _message_to_generate_content_response(
                            ChatCompletionAssistantMessage(
                                role="assistant",
                                content=text_buffer,
                                tool_calls=tool_calls,
                            )
                        )
                        text_buffer = ""
                        function_calls.clear()
                    elif finish == "stop" and text_buffer:
                        aggregated_response = _message_to_generate_content_response(
                            ChatCompletionAssistantMessage(role="assistant", content=text_buffer)
                        )
                        text_buffer = ""

                    logger.debug(
                        "DeepSeekStreaming: processed chunk type=%s finish=%s details=%s",
                        type(chunk).__name__ if chunk else None,
                        finish,
                        _describe_chunk(chunk),
                    )

            logger.debug("DeepSeekStreaming: stream iteration completed events=%s", event_count)

            if aggregated_response:
                if usage_metadata and not aggregated_response.usage_metadata:
                    aggregated_response.usage_metadata = usage_metadata
                    usage_metadata = None
                yield aggregated_response

            if aggregated_with_tool:
                if usage_metadata and not aggregated_with_tool.usage_metadata:
                    aggregated_with_tool.usage_metadata = usage_metadata
                yield aggregated_with_tool

        async for response in _generator():
            yield response

    @asynccontextmanager
    async def connect(self, llm_request: LlmRequest) -> BaseLlmConnection:
        connection = DeepSeekLiveConnection(self, llm_request)
        try:
            yield connection
        finally:
            await connection.close()


class DeepSeekLiveConnection(BaseLlmConnection):
    """Stream connection that cooperates with ADK live flow shutdown expectations."""

    def __init__(self, llm: DeepSeekStreamingLLM, base_request: LlmRequest) -> None:
        self._llm = llm
        self._base_request = base_request.model_copy(deep=True)
        self._history: List[types.Content] = []
        self._response_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._stream_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._tool_calls: Dict[str, Dict[str, Any]] = {}
        self._last_response: Optional[LlmResponse] = None
        self._text_accumulator: List[str] = []
        self._had_final_text = False
        self._pending_restart = False
        self._close_requested = False
        self._stream_finished = asyncio.Event()
        self._stream_finished.set()
        self._sentinel_emitted = False

    async def send_history(self, history: List[types.Content]) -> None:
        async with self._lock:
            logger.debug("DeepSeekStreaming: send_history count=%s", len(history))
            self._history = [_clone_content(item) for item in history]
            await self._restart_stream()

    async def send_content(self, content: types.Content) -> None:
        async with self._lock:
            logger.debug(
                "DeepSeekStreaming: send_content role=%s pending_restart=%s",
                getattr(content, "role", None),
                self._pending_restart,
            )
            self._history.append(_clone_content(content))
            self._capture_tool_calls(content)
            await self._restart_stream()

    async def send_realtime(self, blob: types.Blob) -> None:
        raise NotImplementedError("DeepSeek streaming does not support realtime media input.")

    async def receive(self) -> AsyncGenerator[LlmResponse, None]:
        while True:
            item = await self._response_queue.get()
            if item is _STREAM_FINISHED:
                logger.debug("DeepSeekStreaming: sentinel received, exiting receive loop")
                break
            if isinstance(item, LlmResponse):
                yield item

    async def close(self) -> None:
        if self._close_requested:
            return
        self._close_requested = True
        if self._stream_task:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._stream_finished.wait(), timeout=10)
        await self._emit_sentinel()

    async def _restart_stream(self) -> None:
        previous_task = self._stream_task
        self._pending_restart = True
        logger.debug(
            "DeepSeekStreaming: restarting stream history=%s previous_task=%s",
            len(self._history),
            bool(previous_task),
        )
        self._reset_stream_state()
        if previous_task:
            previous_task.cancel()
            with suppress(asyncio.CancelledError):
                await previous_task
            await self._response_queue.put(_STREAM_FINISHED)

        if not self._history:
            self._pending_restart = False
            return

        request = self._prepare_request()
        self._stream_finished.clear()
        self._stream_task = asyncio.create_task(self._emit_stream(request))
        self._pending_restart = False

    def _prepare_request(self) -> LlmRequest:
        request = self._base_request.model_copy(deep=True)
        request.contents = self._normalize_history()
        return request

    def _normalize_history(self) -> List[types.Content]:
        normalized: List[types.Content] = []
        for content in self._history:
            cloned = _clone_content(content)
            parts = getattr(cloned, "parts", None) or []

            tool_response_part = next(
                (part for part in parts if getattr(part, "function_response", None)),
                None,
            )
            if tool_response_part:
                tool_response = tool_response_part.function_response
                call_id = tool_response.id if tool_response else ""
                args = self._tool_calls.get(call_id) or {}
                payload = tool_response.response if tool_response else {}
                if not args and isinstance(payload, dict):
                    args = payload.get("arguments") or {}
                tool_name = (
                    tool_response.name
                    if tool_response
                    else payload.get("tool_name") if isinstance(payload, dict) else "tool_call"
                )
                assistant_content = types.Content(
                    role="model",
                    parts=[types.Part(function_call=types.FunctionCall(name=tool_name, args=args, id=call_id or None))],
                )
                normalized.append(assistant_content)
                cloned.role = "tool"
                normalized.append(cloned)
                if call_id:
                    self._tool_calls.pop(call_id, None)
                continue

            self._capture_tool_calls(cloned)
            normalized.append(cloned)
        return normalized

    async def _emit_stream(self, request: LlmRequest) -> None:
        try:
            await self._emit_stream_inner(request)
        except Exception:
            logger.exception("DeepSeekStreaming: emit_stream failed")
            await self._response_queue.put(
                LlmResponse(error_code="deepseek_error", error_message="stream emission failed")
            )
        finally:
            self._stream_task = None
            self._stream_finished.set()
            await self._emit_sentinel()

    async def _emit_stream_inner(self, request: LlmRequest) -> None:
        try:
            async with aclosing(self._llm.generate_content_async(request, stream=True)) as stream:
                async for response in stream:
                    self._last_response = response
                    self._ingest_text(response)
                    await self._response_queue.put(response)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DeepSeekStreaming: streaming failed %s", exc, exc_info=True)
            await self._response_queue.put(
                LlmResponse(error_code="deepseek_error", error_message=str(exc))
            )
        finally:
            completion_needed = not (
                self._last_response and getattr(self._last_response, "turn_complete", False)
            )
            if not self._had_final_text:
                fallback = self._compose_fallback_text()
                if fallback:
                    parts = [types.Part.from_text(text=fallback)]
                    self._text_accumulator.append(fallback)
                    await self._response_queue.put(
                        LlmResponse(
                            content=types.Content(role="model", parts=parts),
                            partial=False,
                        )
                    )
                    self._had_final_text = True
                    completion_needed = True
            if completion_needed:
                await self._response_queue.put(
                    LlmResponse(content=None, turn_complete=True)
                )
                logger.info("DeepSeekStreaming: emit_stream finalizing turn_complete=%s", completion_needed)

    def _reset_stream_state(self) -> None:
        self._text_accumulator = []
        self._had_final_text = False
        self._last_response = None

    def _ingest_text(self, response: LlmResponse) -> None:
        if not response or not response.content or not response.content.parts:
            return
        metadata = getattr(response, "custom_metadata", None) or {}
        if metadata.get("stage") == "plan":
            return
        fragments = []
        for part in response.content.parts:
            text = getattr(part, "text", None)
            if text:
                fragments.append(text)
        if fragments:
            self._text_accumulator.extend(fragments)
            if not response.partial and any(fragment.strip() for fragment in fragments):
                self._had_final_text = True

    def _compose_fallback_text(self) -> str:
        combined = " ".join(fragment.strip() for fragment in self._text_accumulator if fragment)
        return combined.strip()

    def _capture_tool_calls(self, content: types.Content) -> None:
        for part in getattr(content, "parts", None) or []:
            function_call = getattr(part, "function_call", None)
            if function_call:
                call_id = function_call.id or function_call.name
                if call_id:
                    self._tool_calls[call_id] = function_call.args or {}

    async def _emit_sentinel(self) -> None:
        if self._sentinel_emitted:
            return
        self._sentinel_emitted = True
        logger.debug("DeepSeekStreaming: emitting sentinel")
        await self._response_queue.put(_STREAM_FINISHED)
