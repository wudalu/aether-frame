# Aether Frame Observability 增强方案

## 目标与范围

构建一套覆盖日志、指标、追踪与告警的可观测体系，用于监控基于 Google ADK 的代理执行流程。目标包括：

1. **全面可见性**：实时掌握请求状态、耗时、token 成本、工具调用与会话状态。
2. **快速诊断**：发生异常时能够迅速定位原因，追踪调用链路。
3. **成本与质量透明**：统计模型/流程成本、工具成功率与用户反馈，为迭代提供依据。
4. **对标业界最佳实践**：结合企业级 AI 代理监控方案，规划自建与第三方工具的组合。

## ADK 原生能力回顾

- **usage_metadata**：在 ADK 事件流中自带 `prompt_token_count`、`candidates_token_count`、`total_token_count`。可按 turn/session 累积，用于成本估算。
- **LiteLLM & 回调**：LiteLLM 支持成本与延迟统计；ADK 也能通过 hook 拿到 usage 并发到外部系统（Prometheus、Cloud Monitoring）。
- **ADK Plugin**：可自定义插件，在执行时收集指标并推送到内部/外部监控系统。
- **官方示例**：API usage demo、AgentOps 集成、Maxim observability 等资料可直接参考，对接成本低。
- **LiveRequestQueue / 事件转换器**：live 流中可以截获所有事件，结合已有的 `AdkEventConverter` 实现工具调用、plan 步骤等的日志/指标记录。

## 现有日志缺口与改进方向

| 缺口 | 改进点 |
| ---- | ------ |
| 成功/失败缺少细分 | 统一 `component`、`flow_step`、`error_category`字段；失败时明确错误类型与关键信息（session/agent/tool）。 |
| 耗时统计不完整 | 在 Runner、SessionManager、工具调用等节点增加耗时日志；在 live 流程计算真实执行时间。 |
| live 结束日志缺失 | 避免 GeneratorExit 被误判为异常；在 `after_execution` 中补写 `execution_time`、`token_usage`、followup 信息。 |
| 输入输出缺乏摘要与治理 | 日志中记录消息摘要（hash、长度）；对敏感字段做脱敏或过滤处理。 |
| 日志格式 | 统一 JSON 输出，保证 `execution_id`/`chat_session_id` 在每条日志中；规划日志分级（执行策略/框架内部/监控输出）。 |

## 指标体系设计

### 核心指标

1. **请求统计**：`total_requests_total{framework=adk}`、`success_total`、`failure_total`、细化 `failure_reason`。
2. **耗时**：`request_duration_seconds`（按场景区分：创建、对话、live、工具调用等）；工具调用、MCP 请求耗时。
3. **Token/成本**：`tokens_prompt_total`、`tokens_completion_total`、按模型/工具细分；结合模型价表计算成本（可推送 `cost_usd_total`）。
4. **资源状态**：活跃 Session、Agent、Runner 数量；LiveRequestQueue 长度。
5. **质量信号**：工具成功率、plan 步骤覆盖、follow-up 成功率、用户反馈（若可收集）。

### 实现建议

- 在 `AdkObserver.after_execution/on_error` 中汇总并写入 Prometheus/GCM 指标。
- Session/Runner 管理模块增加状态变更指标，如 `agent_switch_total`、`session_recovery_total`。
- `AdkEventConverter` 识别 `TaskChunkType`，对工具调用成功/失败计数。
- live 流程中使用计时器记录执行时长，设置 `result.execution_time`。
- 引入失败分类：`LLM_ERROR`、`TOOL_ERROR`、`MCP_TIMEOUT`、`VALIDATION`、`SESSION_RECOVERY_FAILED`、`USER_ABORT` 等，在日志与指标中统一使用。

## 追踪与告警

### 分布式追踪

- 配置 OpenTelemetry，建立 Execution→Agent→Tool→LLM 的 span 链路。
- Span 属性：`agent_id`、`session_id`、`chat_session_id`、`tool_name`、`token_usage`、`latency_ms`、`status`。
- 可导出到 Cloud Trace、Tempo、Jaeger 等；与 Langfuse、AgentOps、Maxim 等 SaaS 示例结合，快速获取 UI 与分析能力。

### 告警策略

- Prometheus/Cloud Monitoring 设定阈值：异常率、耗时、token/成本、MCP 可用性等。
- 与 PagerDuty/Slack 集成，实现实时告警。
- 告警信息包含 `execution_id` 便于回放与日志定位。

## 行业最佳实践参考

> 来源：Microsoft Agent Factory、Softcery Observability Guide、MarkTechPost/Vellum 等。

1. **三层框架**：Tracing (全链路)、Monitoring (延迟、token、成本、错误)、Evaluation (LLM-as-a-judge、自定义评测)。  
2. **最佳做法**：
   - 统一结构化日志与 ID，方便汇聚分析；
   - 分别对工具调用与外部依赖设独立 SLO；
   - 结合 “模拟 + 线上” 管控回归与 production；
   - 聚合用户反馈 / 人审结果，形成质量闭环；
   - 做好隐私合规：敏感字段屏蔽、访问追踪。
3. **第三方工具**：
   - **Maxim AI**、**AgentOps**、**Langfuse**、**Helicone**、**LangSmith**、**Vellum** 等提供 turnkey 的 tracing、token/cost、调试 UI，可先打通一个（如 AgentOps + Langfuse），节省自建成本。

## 迭代步骤建议

### 短期（1-2 周）

1. 统一 observer 日志字段，确保 batch/live 都能输出 `ADK execution complete`、`token_usage` 等信息。
2. 接入 Prometheus 或 Cloud Monitoring，输出请求/耗时/token 等关键指标。
3. 将结构化日志接入日志平台（Loki/ELK），制作基础仪表盘。

### 中期（3-6 周）

1. 引入 OpenTelemetry 追踪，串联 Execution → Agent → Tool → 外部接口。
2. 接入 AgentOps / Langfuse 等 SaaS，验证 tracing、成本分析与调试能力。
3. 完成失败原因分类与统一统计，落地告警规则。

### 长期

1. 构建 ADK 监控插件，沉淀指标输出能力。
2. 与数据仓库/BI 对接，开展长期成本与质量分析。
3. 引入模拟与评测平台（Maxim、Vellum 等），形成“评测 → 部署 → 监控 → 反馈”的闭环机制。

## 规划与资源需求

- **工具**：Prometheus/Cloud Monitoring、OpenTelemetry Stack（Collector + 后端）、日志平台、AgentOps/Langfuse 等。
- **落地团队**：ADK/框架工程师（支持埋点）、平台/数据基础团队（指标接入）、SRE/运营（告警与应急流程）、业务方（评测与日志验证）。
- **风险**：外部接口不稳定、指标/日志体系不统一、敏感信息泄露。需制定标准策略与敏感信息防护机制。

## 总结

按本方案推进，可实现从“有日志”到“可观测 + 可告警 + 可评估”的升级，覆盖 ADK 原生能力与业界最佳实践，为后续代理系统的稳定性、成本控制和质量提升提供完整数据基础。
