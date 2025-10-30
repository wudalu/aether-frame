# DeepSeek Streaming Implementation

This document summarises the streaming pathway that now powers the `adk` live
execution flow inside **aether-frame**. The focus of this iteration was to wire
DeepSeek models into the ADK streaming contract, surface plan deltas, and keep
tool execution compatible with stream mode.

## High-Level Flow

1. **Adapter entry point** – `AdkFrameworkAdapter.execute_task_live` resolves the
   agent and runner exactly as the synchronous path does, then calls into the
   domain agent's live execution.
2. **Domain agent** – `AdkDomainAgent.execute_live` produces ADK `LlmResponse`
   objects. These responses flow through the Aether event converter to emit
   framework-level `TaskStreamChunk`s.
3. **Streaming model** – `DeepSeekStreamingLLM` (new) extends the ADK LiteLLM
   wrapper and speaks directly to DeepSeek via the LiteLLM gateway.
4. **Live connection** – `DeepSeekLiveConnection` manages restartable
   bidirectional streams, queues partial responses, and keeps state aligned with
   tool calls.
5. **Event conversion** – `AdkEventConverter` interprets the live responses,
   translating plan deltas, tool proposals, tool results, and final completions
   into the public streaming schema.

## DeepSeekStreamingLLM

The new adapter in `src/aether_frame/framework/adk/deepseek_streaming_llm.py`
keeps the LiteLLM compatibility layer but adds DeepSeek-specific semantics:

- **Reasoning/plan capture** – DeepSeek emits `reasoning_content` tokens ahead of
  the final answer. These are converted into `ReasoningChunk`s and surfaced as
  partial `LlmResponse`s with `custom_metadata.stage = "plan"`, enabling
  `TaskChunkType.PLAN_DELTA` chunks downstream. The final reasoning burst is
  annotated as a plan summary.
- **Incremental text streaming** – Assistant text deltas are forwarded as partial
  responses so the UI can stream tokens as they arrive.
- **Tool call assembly** – Streaming `tool_calls` payloads are reassembled across
  chunks, including chunk-index fallbacks so DeepSeek's non-sequential indices do
  not drop arguments. Once LiteLLM reports `finish_reason == "tool_calls"`, the
  adapter emits a full assistant message that references the reconstructed tool
  calls.
- **Usage metadata** – `stream_options.include_usage` is forced on. Usage chunks
  are consumed and attached to the final `LlmResponse` so token accounting stays
  intact.

## DeepSeekLiveConnection

`DeepSeekLiveConnection` implements `BaseLlmConnection` and mirrors ADK's live
API requirements:

- Maintains the full ADK history, replaying it on every restart while preserving
  tool-response ordering.
- Normalises tool response content into assistant ➜ tool pairs so DeepSeek can
  consume follow-up messages correctly.
- Queues streamed responses and emits sentinel markers. Restart requests cancel
  the active stream, drain the queue, and spin up a fresh request without losing
  partial results.
- Tracks accumulated assistant text to emit a fallback completion chunk if the
  model never sends a non-partial response (for example, when only reasoning
  text is produced).
- Ignores reasoning deltas when composing fallback text so planning output does
  not leak into the final assistant answer.

## Tool Execution Behaviour

Tool invocations remain buffered. The adapter waits for DeepSeek to finish
streaming a tool call proposal, executes the tool synchronously, and then sends
back the tool response. Only the final tool result chunk is streamed to the
client (no incremental tool output yet), matching the project's tolerance for
non-streaming tool execution during this phase.

## Configuration Notes

- `AdkModelFactory.create_model(..., enable_streaming=True)` automatically wires
  DeepSeek identifiers (`deepseek-chat`, `deepseek/...`) to the new streaming
  wrapper.
- The adapter honours `DEEPSEEK_API_KEY` and `DEEPSEEK_API_BASE` environment
  variables. By default requests are sent to `https://api.deepseek.com/v1`.
- LiteLLM remains the transport. No proxy-specific settings are required beyond
  the API key and optional base URL.

## Testing the Streaming Path

1. Activate the project virtual environment (`.venv`) with Python 3.12 and
   ensure `pip install -e .[dev]` has been executed.
2. Export DeepSeek credentials, e.g.:

   ```bash
   export DEEPSEEK_API_KEY="sk-your-key"
   # optional override
   export DEEPSEEK_API_BASE="https://api.deepseek.com/v1"
   ```

3. Run the manual end-to-end suite in streaming mode:

   ```bash
   python -m tests.manual.test_complete_e2e --models deepseek-chat --tests live_streaming_mode
   ```

   The log under `logs/` records every streamed chunk, including plan deltas,
   tool proposals, tool results, and the final assistant answer.

4. (Optional) Capture full coverage by omitting `--tests` to execute the entire
   DeepSeek scenario list.

## Current Limitations & Next Steps

- Tool execution output is still buffered and emitted only once the tool call
  completes. Streamed tool deltas are a future phase.
- Audio/video real-time inputs remain unsupported; DeepSeek's API currently
  accepts text-only content in this pipeline.
- The fallback completion chunk is a safety net; once DeepSeek reliably emits a
  non-partial final message this branch can be simplified.
- Additional metrics (latency, token usage per segment) should be threaded into
  the event metadata when the observability backlog is prioritised.

With these pieces in place, DeepSeek integrates cleanly with the ADK streaming
interface, providing plan visibility, prompt/response continuity, and tool-call
round trips compatible with the rest of the framework.
