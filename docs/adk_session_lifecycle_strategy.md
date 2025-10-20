# ADK Lifecycle Strategy (Sessions, Runners, Agents)

## Background & Objectives

Our current ADK integration intentionally supports **controlled reuse** of chat sessions、ADK runners、domain agents，以降低重复拉起成本；同时也允许业务层通过 `chat_session_id` 切换 agent。复用策略提升了性能，但也意味着需要配套的主动清理与恢复机制，避免资源占用失控或复用失败。我们需要一个兼顾以下目标的策略：

- **Continuity** – 在复用模式下仍可保持业务上下文，一次创建的 agent/runner 持续服务同一会话。
- **Resource control** – 通过 idle 清理等手段及时释放闲置的 runner/agent，避免长期占用。
- **Predictable recovery** – 当资源被清理或失效后，能快速重建并恢复历史上下文。

This document summarizes industry approaches (AWS Bedrock AgentCore, Microsoft Agent Framework, enterprise chatbot platforms) and proposes an MVP plus longer-term roadmap tailored to Aether Frame’s ADK stack.


## Industry Insights

| Theme | Observations | Relevance |
| --- | --- | --- |
| Idle timeout + state summarisation | Amazon Bedrock AgentCore enforces an `idleSessionTimeout` (currently limited to 1 hour) and recommends storing conversation state externally, then re-hydrating the agent by loading summaries when the session restarts.<sup>[1](#ref1)</sup> | 与我们的复用策略类似：需要在释放 runner 之前安全保存上下文，以便随后复用/恢复。 |
| Persistent “memory” tiers | Bedrock AgentCore Memory distinguishes **短期**（单次会话内）和 **长期**（跨会话的偏好/摘要）。<sup>[2](#ref2)</sup> | 提醒我们在复用模型下，也需要明确哪些内容随会话复用、哪些需要持久化并在重建时注入。 |
| Two-level retention windows | Many SaaS support bots (ServiceNow, Zendesk) apply a short idle window for expensive resources (live runner), and a longer retention window for conversational artifacts (history, metadata). | Reinforces a split between “resource lifetime” and “context lifetime.” |
| Manual lifecycle hooks + automation | Enterprise bots expose “close conversation” APIs but rely on automation (cron jobs, usage-based policies) to invoke them, because users rarely terminate chats themselves. | Justifies adding explicit cleanup endpoints plus background sweeps. |

**Summarization best practices:** Bedrock Memory uses LLM prompts to summarise sessions into structured memory and lets developers customise prompts, retention limits, and memory injection when sessions restart.<sup>[2](#ref2)</sup> This aligns with our plan to summarise transcripts before runner teardown and rehydrate on demand.


## Short-Term MVP Plan

Goal: introduce a predictable, automated cleanup mechanism while preserving user experience.

### Functional scope
1. **Idle eviction & cleanup (Runner/Agent/Session)**
   - 定时扫描 `ChatSessionInfo.last_activity`（可复用现有字段），针对超出阈值（如 30 分钟）的业务会话：
     1. 记录原始 transcript（可作为后续摘要输入，MVP 阶段允许暂存原文）。
     2. 调用 `cleanup_chat_session` 触发 session/runnner/agent 一体化销毁。
     3. 将清理结果写入结构化日志，便于审计。
   - 提供配置项控制 idle 超时及是否开启清理。

2. **受控复用（当期）+ 预留恢复接口**
   - 继续沿用“Agent/Runner 可复用”的策略，要求业务层维持同一 `chat_session_id`，并在复用前校验 runner/agent 状态。
   - Idle 清理后暂不自动重建；下一次请求若触发“未找到 session”，业务可判断是否调用预留恢复入口。
   - 预留恢复 API（目前为空实现），为后续补充历史注入、Runner 重建等能力做准备。

3. **可观测性（MVP 范围）**
   - 已增强的 DEBUG 日志基础上，补充 idle 清理相关日志与指标打点（如清理原因、 idle 时长、重建耗时）。
   - 记录业务 `chat_session_id`、内部 `adk_session_id` 与 `agent_id` 的关键生命周期事件，方便排查复用问题。

> 摘要与长期存储仍作为后续增强（可在 Phase 2 处理），MVP 先确保资源可控释放与复用稳定。

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
