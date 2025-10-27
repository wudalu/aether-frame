# Streaming Implementation Blueprint

This document captures the current state of ADK live streaming support inside **aether-frame**, the key gaps we must close, and the phased roadmap for shipping production-grade streaming.

## 1. Current Architecture Snapshot

- **Entry point**: `AdkFrameworkAdapter.execute_task_live` is still a placeholder that yields an error chunk. Live calls never reach the ADK runtime because the adapter does not hydrate the domain agent or session context.
- **Domain agent**: `AdkDomainAgent.execute_live` already wires `runner.run_live` into streaming chunks via `AdkEventConverter`. When given a runner + `LiveRequestQueue`, it produces text/progress chunks and tool call requests, but today the adapter never invokes it.
- **Event conversion**: `AdkEventConverter` maps partial/final responses and bare function-call requests to `TaskStreamChunk`. There is no support for plan deltas, proposal metadata, or correlation identifiers.
- **Human-in-the-loop (HITL)**: `AdkLiveCommunicator` can resume ADK’s live queue and currently supports raw user messages. Because we do not emit structured interaction chunks, approvals and clarifications are impossible to trigger.
- **Tools**: Universal tools still run synchronously through `ToolService`. Only the final response is surfaced, with no progress instrumentation or alignment to the `TaskStreamChunk` metadata we plan to extend.

## 2. Guiding Principles

1. **Preserve conversational continuity** – live mode must reuse the same runner, session, and agent state that synchronous calls use.
2. **Granular event taxonomy** – every streamed chunk must encode author, stage (plan/llm/tool/hitL), sequence id, and tool-call correlation when applicable.
3. **Bidirectional safety** – human approvals and cancellations should always round-trip through `LiveRequestQueue`, guaranteeing ADK stays in sync with UI decisions.
4. **Backward compatibility** – keep the existing `TaskStreamChunk` shape so current clients continue to work while we enrich metadata.
5. **Parity across execution modes** – `execute_task` (sync) and `execute_task_live` (stream) must share the same tool plumbing so both paths benefit from future enhancements.

## 3. Streaming Roadmap

**Focus adjustment**: The near-term goal is to stream agent execution plans and HITL checkpoints rather than raw LLM deltas. Tool execution remains buffered until approvals complete, and LLM token streaming is deferred.

### Phase 0 — Adapter Bridge & Session Contract *(ETA: ~1 sprint)*

- Replace `execute_task_live` with a real adapter bridge that:
  - Reuses `_handle_conversation` (sync path) to construct `RuntimeContext`, resolve the `AdkDomainAgent`, and attach `runner`, `session_id`, and `user_id`.
  - Calls a new `_execute_live_with_domain_agent` helper that forwards to `AdkDomainAgent.execute_live`, reusing the existing ADK plumbing.
  - Wraps the returned communicator so we can log, cleanup, and reconcile the public `chat_session_id` with ADK sessions via `AdkSessionManager`.
- Encode a durable session contract: heartbeat/idle timeouts, graceful cancellation, and downgrade-to-sync behaviour when streaming is unavailable.
- Extend `TaskStreamChunk` metadata with `chunk_kind`, `chunk_version`, `sequence_id`, and `interaction_id` scaffolding; update factories/tests to accept the additive fields without breaking clients.
- Smoke tests to prove live invocation reaches ADK, the communicator closes on completion, and sync execution remains unaffected.

### Phase 1 — Agent Plan Streaming & Pre-Tool Approvals *(ETA: ~1 sprint)*

- Extend `AdkEventConverter` to emit plan-centric chunks:
  - `TaskChunkType.PLAN_DELTA` with incremental plan steps (sanitised from ADK event content) tagged `metadata.stage = "plan"`.
  - `TaskChunkType.PLAN_SUMMARY` once planning stabilises, with correlation to the originating user turn.
  - Plan extraction uses ADK event metadata (`event_type in {"plan","intermediate_step"}`) when available; otherwise we rely on prompt-level tags (e.g., `Plan:` blocks) so the converter can safely slice reasoning output without exposing raw chain-of-thought.
- Introduce `TaskChunkType.TOOL_PROPOSAL` for every pending tool call:
  - Payload includes `interaction_id`, tool name, argument preview, risk/intent metadata, and `requires_confirmation`.
  - Integrate with `AdkLiveCommunicator` so approvals can approve, reject, edit arguments, or request clarification.
- Build an approval broker in the adapter layer:
  - Queue concurrent requests, enforce single-flight resolution, and push timeout/abort policies back into ADK via structured commands.
  - Apply a configurable timeout (default 90s) that auto-resumes with a policy-defined fallback (`auto_cancel`, `auto_approve`, or `safe-default`) when no human response arrives, mirroring Codex/Claude behaviour where sessions continue without manual approval to avoid deadlocks.
  - Surface human clarification requests as `TaskChunkType.HITL_PROMPT`, reusing the communicator to capture responses.
- Add `TaskChunkType.TOOL_RESULT` as a final, non-streaming payload: capture the complete tool response, execution metadata (latency, retries), and correlate to `interaction_id`, keeping MVP simple while preserving schemas for future tool streaming.
- Update unit and integration coverage (`tests/unit/test_adk_adapter_live.py`, new streaming fixtures) to exercise plan ordering, approval edits, timeout fallbacks, and tool result correlation using mocked ADK events.

### Phase 2 — Tool Completion Streaming Hooks *(ETA: ~1 sprint, post-MVP)*

- Preserve the async streaming interface in `ToolService.execute_tool_stream`, but default agent integration to buffered mode. Define translation helpers that can later forward tool chunks into ADK live streams without impacting MVP.
- Design chunk semantics for future rollout (`tool.delta`, `tool.log`, `tool.partial_result`) and document transport considerations.
- Validate end-to-end behaviour by toggling a feature flag in tests to enable synthetic tool streaming, ensuring the wiring is ready once we invest in full adoption.

### Phase 3 — Extended HITL & Resilience *(ETA: ~2 sprints)*

- Expand HITL coverage beyond tool approvals:
  - Support manual data injection, escalation prompts, and cancellation commands, all mapped to structured chunk types.
  - Persist resumable checkpoints (last plan step, pending approvals) using `AdkSessionManager` so reconnects do not replay approvals.
- Add observability guardrails:
  - Structured logging per chunk, metrics for approval latency/abandon rate, and traces keyed by `task_id` + `interaction_id`.
  - Backpressure controls to shed or batch chunks when downstream consumers lag.
- Run chaos scenarios (network drop, stale approvals, concurrent cancellations) and document SLOs alongside the incident runbook.

## 4. Integration with Existing Infrastructure

- **Adapter lifecycle**: Reuse the synchronous `_handle_conversation` and `RunnerManager` plumbing inside `AdkFrameworkAdapter.execute_task_live` so runner hydration, session reuse, and cleanup remain consistent across modes.
- **Domain agent streaming**: Keep leveraging `AdkDomainAgent.execute_live`, extending only the returned event payloads. The generator already streams ADK events; we simply enrich `AdkEventConverter` to emit the new plan/approval chunk types.
- **Chunk schema**: Extend `TaskStreamChunk` dataclass and related factories (including the MCP client in `tests/tools/mcp/real_streaming_server.py`) to accept the new metadata fields, ensuring older consumers can ignore unknown keys.
- **Communicator bridge**: Enhance `AdkLiveCommunicator` with typed methods (`send_approval_result`, `send_clarification`) rather than raw text so Phase 1 approvals translate cleanly into ADK commands.
- **Tooling**: When emitting `TaskChunkType.TOOL_RESULT`, rely on the existing `ToolService` wrappers and logging hooks instead of introducing a parallel execution path. Keep the streaming interface accessible for future phases but disabled by default.
- **Testing**: Expand current suites (`tests/unit/test_adk_adapter_error_handling.py`, `tests/integration/test_adk_idle_cleanup_flow.py`) with streaming-specific fixtures to validate session cleanup, approval timeouts, and downgrade-to-sync behaviour.
- **Transport**: Default client transport is Server-Sent Events; we will publish SSE examples first, while keeping the adapter transport-agnostic so WebSocket consumers can be added later.

## 5. Action Checklist (next sprint)

1. Ship the Phase 0 adapter bridge, sequence metadata extensions, and smoke tests. ✅ (done)
2. **Current focus**: land Phase 1 scope (plan delta, tool proposal, buffered tool result, approval broker) with unit + integration coverage.
3. Align with frontend on SSE payload examples (`PLAN_DELTA`, `TOOL_PROPOSAL`, `TOOL_RESULT`) and codify timeout UX.
4. Backlog: draft the tool streaming hook design doc so Phase 2 can start once MVP stabilises.

## 6. Open Questions

- **Plan tagging confidence**: Do all ADK events expose `event_type` consistently across models, or do we need prompt adjustments to guarantee `Plan:` tags?
- **Approval UX**: What is the default behaviour when humans do not respond (auto-cancel, auto-approve, or escalation)?
- **Schema rollout**: Do we need version negotiation for `TaskStreamChunk` additions, or can we rely on additive parsing across all clients?

---

By locking Phase 1 we unblock real-time visibility into the agent’s execution plan and structured HITL approvals. Tool completion streaming and deeper observability follow incrementally without destabilising the initial release.
