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

## End-to-End Data Contracts

### Synchronous invocation

- **Build** – Create a `TaskRequest` via `TaskRequestFactory.create_chat_task(...)`
  (or the lower-level builder). The factory resolves tools and attaches the
  appropriate `AgentConfig` / `ExecutionContext`.
- **Execute** – Call `ExecutionEngine.execute_task(request)`. The engine routes
  to ADK and returns a `TaskResult`.
- **Consume** – `TaskResult` (`src/aether_frame/contracts/responses.py`) includes
  `status`, optional assistant `messages`, `tool_results`, and the structured
  `error: ErrorPayload` (`src/aether_frame/contracts/errors.py`) alongside the
  legacy `error_message`.

### Streaming invocation

- **Build** – `TaskRequestFactory.create_live_chat_task(...)` returns a
  `TaskRequest` whose `ExecutionContext.execution_mode == "live"` and whose
  metadata contains `stream_mode=True`.
- **Prompt for planning** – Because plan chunks originate from the model’s
  reasoning stream, provide an explicit instruction in
  `AgentConfig.system_prompt` such as:
  > “You are a meticulous analyst. Respond in two phases: (1) produce a numbered
  > plan labelled ‘Plan Step 1/2/...’ and keep the plan in the reasoning channel;
  > (2) call the required tools and deliver a final answer.”
  This nudge ensures the model emits reasoning segments that the runtime can
  translate into `plan.delta` / `plan.summary` chunks, even when the model is
  not token-streaming by default.
- **Execute** – Call `ExecutionEngine.execute_task_live(request, context)` or,
  if you prefer a higher-level helper, `ExecutionEngine.execute_task_live_session`
  (which simply wraps the raw `(event_stream, communicator)` into a
  `StreamSession`). The routing decision is still made by the framework;
  passing a live execution context signals the live path.
- **RunConfig alignment** – When ADK’s optional dependencies are present, the
  `AdkDomainAgent` now instantiates a `RunConfig` with `StreamingMode.SSE`
  (matching the official ADK guidance for GPT-family streaming). You can supply
  overrides via `agent_config.framework_config["run_config"]` to tweak fields
  such as `streaming_mode`, `max_llm_calls`, or provide your own
  `GenerateContentConfig`. If RunConfig is unavailable (older SDKs), the agent
  gracefully falls back to the legacy LiteLLM streaming behaviour.
- **Azure GPT-4.x fallback** – Because Azure’s LiteLLM adapter lacks ADK Live
  Connect support, the framework now ships a custom `AzureStreamingLLM` /
  `AzureLiveConnection` pair (mirroring the DeepSeek strategy). When streaming
  is enabled, `AdkModelFactory` automatically swaps Azure models to this wrapper
  so GPT-4.1/GPT-4o deployments can participate in live/HITL flows without
  waiting for upstream LiteLLM changes.
- **Consume** – Iterate over the resulting stream to receive `TaskStreamChunk`
  objects (`src/aether_frame/contracts/streaming.py`). The `StreamSession`
  wrapper (`src/aether_frame/streaming/stream_session.py`) exposes helpers such
  as `approve_tool(...)`, `send_user_message(...)`, `cancel(...)`, and
  `list_pending_interactions()` so HITL flows can be driven without touching ADK
  internals.
- **Chunk semantics** – Each chunk carries `chunk_type`, `chunk_kind`, and
  `metadata` describing the stage (`plan`, `assistant`, `tool`, `control`,
  `error`). Tool events now include `tool_full_name`, `tool_short_name`, and
  `tool_namespace`. Tool execution results are still returned in a single
  `tool.result` chunk; only the LLM response is token/segment streamed.

### Error handling

- **Structured errors everywhere** – Synchronous results embed
  `TaskResult.error`; streaming errors emit `TaskStreamChunk` with
  `chunk_type=TaskChunkType.ERROR` and `content=ErrorPayload.to_dict()`.
- **Common error codes** – `request.validation`, `framework.execution`,
  `framework.unavailable`, `stream.interrupted`, `tool.not_declared`,
  `tool.invalid_parameters`, `tool.execution`.
- **Debugging** – Inspect `ErrorPayload.details` for context (missing runner,
  upstream HTTP status, tool identifier, etc.). Because the structure is
  unified, the API layer can log or expose the same fields for both sync and
  streaming paths.

## Practical API Integration

The framework already exposes complete streaming/HITL capabilities. API
developers only need to provide lightweight wrappers so clients can interact
with them.

### 1. Session lifecycle

- **Bootstrap** – On service startup call `create_system_components(Settings)`
  and keep references to `execution_engine` / `task_factory`. Shut down with
  `shutdown_system(...)`.
- **Synchronous tasks** – Build a `TaskRequest`, invoke
  `execution_engine.execute_task(...)`, return the `TaskResult`.
- **Streaming tasks** – Build a live `TaskRequest` by setting
  `execution_context.execution_mode="live"` (the helper
  `TaskRequestFactory.create_live_chat_task(...)` does this automatically). Call
  `execution_engine.execute_task` – the framework will detect the live mode and
  take the streaming path. For convenience, you may also use
  `execute_task_live`/`execute_task_live_session` to obtain a `StreamSession`
  wrapper directly. Store the session keyed by `session_id` and call
  `StreamSession.close()` when finished.
- **System prompts** – Populate the model’s instructions via
  `AgentConfig.system_prompt` when constructing the `TaskRequest`
  (`TaskRequestBuilder`/`TaskRequestFactory` both accept a `system_prompt`
  argument). The value you supply is passed straight through to the ADK agent
  and ultimately to the underlying model, so prompting conventions such as
  “think step by step” or “always produce a numbered plan” should be authored
  here.

### 2. Event delivery (WebSocket or SSE)

- Iterate over the `StreamSession` and push each `TaskStreamChunk` to the
  client. The chunk’s `chunk_type`, `chunk_kind`, and `metadata.stage` indicate
  plan deltas, assistant tokens, tool proposals/results, completion markers, or
  errors.
- Optional throttling/aggregation can be added for response deltas, but keep the
  original semantics whenever possible.

### 3. User interaction endpoints

- **Tool approval** – `POST /live-sessions/{session_id}/approvals/{interaction_id}`
  → `stream_session.approve_tool(...)` with `approved`, `user_message`,
  `response_data`.
- **User messages** – `POST /live-sessions/{session_id}/messages`
  → `stream_session.send_user_message(text)`.
- **Cancellation** – `POST /live-sessions/{session_id}/cancel`
  → `stream_session.cancel(reason)`.
- **Status polling** – `stream_session.list_pending_interactions()` returns the
  outstanding proposals (useful for reconnecting clients). If the broker times
  out, it will emit the corresponding `tool.error` or `tool.result` chunk with
  `auto_timeout` metadata, so simply relaying chunks keeps the client informed.

### 4. Error reporting

- For synchronous requests, read `TaskResult.error` and forward `code`,
  `message`, and `details`.
- For streaming, forward any chunk with `chunk_type=ERROR` (or
  `chunk_kind="tool.error"`) as soon as it arrives. The payload is a serialized
  `ErrorPayload`, so clients can show consistent error messages.

## Stream Mode Integration Plan

The API service sits above this framework layer and speaks HTTP/WebSocket to
front-end clients. Our responsibility is to expose cohesive primitives so that
layer can call `TaskRequest` endpoints and return structured results without
peeking into ADK internals.

### Phase 0 – Framework Surface (immediate)

- **`StreamSession` wrapper** – wrap `LiveExecutionResult` in a lightweight
  object that exposes:
  - `events`: async iterator of `TaskStreamChunk`
  - `send_user_message(...)` / `send_approval_response(...)`
  - `list_pending_interactions()` for API-side status polling
  - `close()`
- **Task factory helpers** – publish helpers such as
  `TaskFactory.build_live_request()` / `build_sync_request()` that take
  (tenant, payload, options) and return canonical `TaskRequest` instances with
  tools, prompts, model config, and HITL settings already populated.
- **Chunk metadata contract** – document mandatory metadata keys (`stage`,
  `tool_name`, `requires_approval`, `interaction_timeout_seconds`,
  `approval_policy`, etc.) and ensure every chunk emitted by the adapter fills
  them consistently so the API layer can forward them verbatim.

### Phase 1 – Error & Approval Normalisation

- **Error code registry** – introduce a shared enum/constant set (e.g.
  `aether_frame/contracts/error_codes.py`) and make `TaskResult.error_message`
  emit `{ "code": ..., "detail": ..., "source": ... }`. Live streaming must
  emit `chunk_type=ERROR` chunks that reuse the same structure.
- **Approval state API** – extend `AdkApprovalBroker` with public helpers to
  list pending approvals and expose expiry timestamps. This allows the API
  layer to implement `/approvals/{interaction_id}` for status queries and
  retries.
- **Tool name mapping** – guarantee that streaming/tool events carry both the
  short DeepSeek name and the fully-qualified MCP namespace so API consumers
  can display/track them accurately.

### Phase 1b – Session Recovery & Multi-Client Support

- **session_recovery enhancements** – persist chunk sequence, approval state,
  and pending tool calls so `resume_live_session(session_id)` can rehydrate the
  stream and re-register outstanding approvals.
- **Broker reattachment** – on resume, automatically re-enqueue pending
  interactions with the broker so a reconnecting client receives the same
  approval prompts.
- **Multi-subscriber guidance** – document how multiple clients can subscribe
  to the same `StreamSession` (e.g. leader + reviewer) and prevent duplicate
  approval submissions.

### Phase 2 – Observability & Tool Telemetry

- **Structured logging** – emit structured logs for every plan delta, tool
  proposal, approval decision, and tool result (including latency). Provide a
  hook so the API layer can forward these to its logging pipeline.
- **Metrics/tracing** – add Prometheus/OTEL counters for approval latency,
  proposal counts, tool success/failure rates, and per-session token usage.
- **Tool delta streaming (stretch)** – evaluate streaming intermediate tool
  progress once the above foundations are live.

## Current Limitations

- Tool execution output is still buffered and emitted only once the tool call
  completes. Streamed tool deltas are a future phase (see Phase 2).
- Audio/video real-time inputs remain unsupported; DeepSeek's API currently
  accepts text-only content in this pipeline.
- The fallback completion chunk is a safety net; once DeepSeek reliably emits a
  non-partial final message this branch can be simplified.
- Additional metrics (latency, token usage per segment) should be threaded into
  the event metadata when the observability backlog is prioritised.

With these pieces in place, DeepSeek integrates cleanly with the ADK streaming
interface, and the surrounding API layer can provide plan visibility,
prompt/response continuity, and tool-call round trips to end users without
tight coupling to internal adapters.
