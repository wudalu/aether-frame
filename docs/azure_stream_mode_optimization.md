## Azure streaming mode optimization plan

### Background
- `src/aether_frame/framework/adk/azure_streaming_llm.py` currently forwards every `TextChunk` yielded by `LiteLLM` into `_response_queue` almost immediately, which means UI and transport layers must parse highly granular deltas.
- For GPT‑4\* deployments hosted on Azure OpenAI, there is no public API flag for explicit token-per-chunk sizing. Azure support confirms the service “determines chunk size based on the model and text” and does not allow clients to override it (`using open AI API with stream option`, Microsoft Q&A, Sep 2023).
- Azure’s content filtering pipeline introduces two streaming modes ([Content Streaming in Azure OpenAI, Microsoft Learn, 2024](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/content-streaming)):
  - Default mode buffers tokens until moderation finishes → lower frequency, larger chunks.
  - Asynchronous filter mode emits every token immediately → higher frequency, annotation events trail behind.
- Community reports (e.g., `vercel/ai` issue #1066) show that client-side buffering strategies are the primary differentiator between “smooth” and “chunky” Azure responses, reinforcing the need for in-house throttling rather than expecting provider-side controls.

### Provider-level knobs (what we can and cannot tune)
1. **Model parameters**: continue honoring `max_output_tokens`, `temperature`, `top_p`, and `response_format`. They limit total completion size but do not affect stream cadence per official OpenAI streaming docs (see `stream_options` reference retrieved via Context7).
2. **`stream_options`**: Azure already honors `include_usage`; the Responses API also supports `continuous` streaming, but it only toggles server-side metadata. No chunk-size hooks.
3. **Content filtering mode**:
   - Default (buffered) reduces token frequency at the expense of latency, which may already meet the requirement if the deployment previously used the asynchronous filter.
   - If adopting asynchronous mode for latency, plan to counter the resulting burst of small deltas on the client side.
4. **Rate-limit aware batching**: Align `max_output_tokens` with realistic UI needs (e.g., 512–1024) to minimize unnecessary tiny chunks triggered by extremely long generations.

### Adapter-level throttling proposal
Goal: keep upstream streaming for responsiveness, while emitting fewer, larger messages to downstream consumers.

1. **Introduce a batching config** (new dataclass, e.g., `TokenBatchingConfig` under `src/aether_frame/framework/adk/streaming_controls.py`):
   - `min_chars_per_emit` (default 120),
   - `max_latency_ms` (default 200–400 ms),
   - `flush_on_sentence=True` (detect `.`/`?`/newline),
   - `flush_on_tool_call=True` (to respect structured payloads).
   Config should be injectable via `AzureStreamingLLM` kwargs so ADK façades remain untouched.
2. **Buffer inside `AzureLiveConnection._emit_stream_inner`**:
   - Instead of enqueueing `response` immediately, pass it to a new helper `_enqueue_with_batching`.
   - `_enqueue_with_batching` accumulates consecutive partial `LlmResponse` objects (text-only) in `self._text_accumulator` plus a running clock.
   - Flush rules:
     - buffer length ≥ `min_chars_per_emit`,
     - elapsed time ≥ `max_latency_ms`,
     - `response.partial` is `False`,
     - non-text payload (tool call / reasoning metadata) arrives.
   - When flushing, coalesce buffered text into a single `types.Content` before pushing to `_response_queue`.
3. **Reasoning segments**:
   - `_extract_reasoning_chunks` already exists. Emit reasoning deltas separately but gate them with the same batching thresholds so they do not overwhelm consumers when GPT‑4o provides dense rationale tokens.
4. **Back-pressure handling**:
   - Because batching reduces queue size, we can safely keep `_response_queue` unbounded. Add debug metrics (`total_flushes`, `avg_chars_per_flush`) to confirm actual gains.

Expected effect: transport and downstream parsing now see ~5–10× fewer messages depending on thresholds, with only ~100–200 ms added tail latency per chunk.

### Business chunk merging ideas
Even with adapter-level throttling, UI/business layers should avoid redundant work when processing history chunks.

1. **Streaming coalescer layer**: Add a service after `BaseLlmConnection.receive()` that:
   - de-duplicates identical signatures (`content_text_signature`) within a sliding window,
   - merges contiguous assistant text fragments until punctuation or a Markdown boundary is detected,
   - emits tool-call payloads only after ensuring their JSON arguments parse, reducing retries triggered by half-finished tool deltas.
2. **Configurable merge policy**:
   - `min_delta_chars` (e.g., 40) to skip micro updates,
   - `max_partial_count` to force flush if UI expects progress indicators.
3. **Chunk-aware telemetry**:
   - Log `chunk_count`, `avg_chunk_size`, and UI render time to verify improvements.
   - Surface these metrics in existing tracing so we can correlate throttling settings with perceived latency.
4. **History normalization**:
   - Reuse `_normalize_history` and `_capture_tool_calls` outcomes to merge model/tool trajectories before they hit domain agents, lowering the probability of a restart loop triggered by repeated tool IDs.

### Implementation sequence (staged rollout)
**Phase 1 – Adapter batching (highest leverage)**
1. Introduce `streaming_controls.TokenBatchingConfig` + tests.
2. Allow `AzureStreamingLLM` to accept the config via kwargs/feature flag.
3. Route `_emit_stream_inner` responses through `_enqueue_with_batching`, emitting flush metrics.
4. Observe: queue size, flush latency, avg chunk size. Tune thresholds before defaulting on.

**Phase 2 – Business chunk coalescer**
1. Add a post-receive coalescer module that can run in “metrics only” mode.
2. Emit duplicate counts, incomplete tool-call attempts, UI render cost.
3. Once metrics confirm benefits, enable actual merging/JSON gating per policy.

**Phase 3 – Combined telemetry & tuning**
1. Correlate “raw vs adapter vs business” chunk counts.
2. Adjust adapter thresholds or coalescer rules based on UX and latency feedback.
3. Document recommended defaults per model (e.g., GPT-4o vs GPT-4o-mini).

These steps let us satisfy the original requirement—limiting how often GPT‑4\* streaming pushes data through the stack—without depending on unsupported provider parameters, while also reducing post-processing overhead through chunk merging.
