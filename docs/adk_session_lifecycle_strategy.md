# ADK Lifecycle Strategy (Sessions, Runners, Agents)

## Background & Objectives

Our current ADK integration deliberately supports **controlled reuse** of chat sessions, ADK runners, and domain agents to reduce the cost of repeatedly spinning resources. The product layer can switch agents by supplying a `chat_session_id`. This reuse model boosts performance, but it also demands proactive cleanup and recovery mechanisms so we do not leak resources or encounter reuse failures. We need a strategy that balances the following goals:

- **Continuity** – Preserve business context while reusing components so the same agent/runner keeps serving the conversation.
- **Resource control** – Release idle runners/agents promptly via idle cleanup to avoid long-lived resource usage.
- **Predictable recovery** – Rebuild quickly and restore history when resources are reclaimed or fail unexpectedly.

This document summarizes industry approaches (AWS Bedrock AgentCore, Microsoft Agent Framework, enterprise chatbot platforms) and proposes an MVP plus longer-term roadmap tailored to Aether Frame’s ADK stack.


## Industry Insights

| Theme | Observations | Relevance |
| --- | --- | --- |
| Idle timeout + state summarisation | Amazon Bedrock AgentCore enforces an `idleSessionTimeout` (currently limited to 1 hour) and recommends storing conversation state externally, then re-hydrating the agent by loading summaries when the session restarts.<sup>[1](#ref1)</sup> | Mirrors our reuse approach: capture context safely before releasing a runner so we can reuse or restore it later. |
| Persistent “memory” tiers | Bedrock AgentCore Memory distinguishes **short-term** (within the current session) and **long-term** (cross-session preferences/summaries).<sup>[2](#ref2)</sup> | Highlights the need to decide which data travels with the session and which must be persisted and re-injected during reconstruction. |
| Two-level retention windows | Many SaaS support bots (ServiceNow, Zendesk) apply a short idle window for expensive resources (live runner), and a longer retention window for conversational artifacts (history, metadata). | Reinforces a split between “resource lifetime” and “context lifetime.” |
| Manual lifecycle hooks + automation | Enterprise bots expose “close conversation” APIs but rely on automation (cron jobs, usage-based policies) to invoke them, because users rarely terminate chats themselves. | Justifies adding explicit cleanup endpoints plus background sweeps. |

**Summarization best practices:** Bedrock Memory uses LLM prompts to summarise sessions into structured memory and lets developers customise prompts, retention limits, and memory injection when sessions restart.<sup>[2](#ref2)</sup> This aligns with our plan to summarise transcripts before runner teardown and rehydrate on demand.


## Short-Term MVP Plan

Goal: introduce a predictable, automated cleanup mechanism while preserving user experience.

### Functional scope
1. **Idle eviction & cleanup (Runner/Agent/Session)**
   - Periodically scan `ChatSessionInfo.last_activity` (existing field). For sessions that exceed the threshold (e.g., 30 minutes):
     1. Persist the raw transcript (can feed the summariser later; raw storage is acceptable for MVP).
     2. Call `cleanup_chat_session` to tear down the session, runner, and agent together.
     3. Emit structured logs describing the cleanup for auditing purposes.
   - Provide configuration to control the idle timeout and whether cleanup is enabled.

2. **Controlled reuse (current model) + placeholder recovery hook**
   - Continue reusing agents/runners when the business layer keeps the same `chat_session_id`, validating runner/agent health before reuse.
   - After idle cleanup we do not auto-rebuild; when the next request sees “session not found,” business logic can decide whether to invoke the recovery endpoint.
   - Provide a stub recovery API that future work can extend with history injection and runner recreation.

3. **Observability (MVP scope)**
   - Extend existing DEBUG logging with idle cleanup metrics (reason, idle duration, rebuild latency).
   - Record key lifecycle events for `chat_session_id`, internal `adk_session_id`, and `agent_id` to simplify troubleshooting.

> Summaries and long-term storage remain future enhancements (Phase 2). The MVP focuses on controllable cleanup and stable reuse.

### Effort & Dependencies

| Item | Owners | Estimate |
| --- | --- | --- |
| Idle timeout scheduler (background task or coroutine) | Framework team | 3–4 eng days |
| Session persistence (raw transcript & placeholder summariser) | ADK integration | 2–3 eng days |
| Resume hook & integration with existing `_create_runtime_context` flow (session + runner + agent) | Framework team | 3 eng days |
| Tests (unit + integration) | QA/Dev | 2 eng days |
| Ops/Config (flags, metrics) | DevOps | 1–2 eng days |

**MVP Total:** ~10–13 engineering days. Dependencies: storage layer for conversation logs (already exists), minimal summarisation (can reuse existing LLM call or postpone to long-term plan).


## Long-Term Roadmap

### Phase 1 (MVP above)
- Idle eviction, manual summarisation, resume support, metrics.

### Phase 2 – Adaptive lifecycle controls
1. **Heartbeat / Keep-alive API:** allow clients to keep sessions alive explicitly (e.g., active UI sends pings).
2. **Capacity-based eviction:** implement LRU/LFU policy to cap concurrent runners or per-user quotas.
3. **Configurable retention tiers:** separate `runner_idle_timeout`, `session_retention_window`, `summary_retention_window`.
4. **Improved summarisation:**
   - Fine-tune prompts for short-term vs long-term memory (inspired by Bedrock Memory prompts).
   - Decide on structured output (facts, TODOs, last user sentiment).
5. **Partial teardown:** permit releasing live runner but keeping agent container (if ADK supports) or vice versa (requires ADK capability review).

### Phase 3 – Observability & governance
1. **Lifecycle dashboards** – track active sessions, evictions, average idle times.
2. **Policy hooks** – allow product teams to register custom rules (e.g., compliance-driven shutdown).
3. **Shared memory services** – integrate with knowledge base for cross-session user insights.
4. **Automated summariser evaluation** – measure faithfulness, drift, and summarisation cost.

### Phase 4 – Ecosystem integrations
1. **Multi-framework parity** – extend lifecycle manager beyond ADK to other frameworks.
2. **Hybrid persistence** – integrate vector store or external DB for long-term memory.
3. **Adaptive cost control** – dynamic scaling based on compute budget, predicted concurrency.


## Impact Assessment

| Area | Impact |
| --- | --- |
| **Framework code** | `adk_session_manager`, `adk_adapter`, `runner_manager`, background scheduler module. |
| **Storage** | Need reliable transcript storage & summarisation output repository. |
| **Testing** | Integration tests for eviction/resume; load tests to validate LRU policies. |
| **Operations** | Configuration management for timeouts; new metrics/alerts. |
| **Product UX** | Optionally expose “End chat” button; communicate behaviour (e.g., session may spin up after idle). |
| **Security & compliance** | Ensure summarised data retention aligns with privacy policies. |


## References

1. <a id="ref1"></a>Amazon Bedrock AgentCore developer guide – discussion of `idleSessionTimeout` and recommendation to persist session history for rehydration.  
2. <a id="ref2"></a>Amazon Bedrock AgentCore Memory documentation – describes short-term vs long-term memory, configurable summarisation prompts, and retention limits.
