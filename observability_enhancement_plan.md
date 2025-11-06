# ADK 可观测性增强方案（草案）

## 背景与目标
- 项目尚未正式上线，但需要在现有日志基础上构建稳健的执行链路观测能力，支撑后续性能、稳定性调优。
- 近期已有 `AdkObserver`、`AdkAgentHooks` 的初步改造，但日志关键信息缺失（执行耗时、失败原因分类等），难以量化行为。
- 本文聚焦于“不依赖 OTel” 的策略：优先复用 ADK 自带信号与现有日志栈，后续按需接入第三方 SaaS。

## 当前状态速览
- **执行起止日志**：在 `before_execution` / `after_execution` 钩子写入，但 `after_execution` 触发时 `TaskResult.execution_time` 尚未填充，导致完成日志 `execution_time=None`。
- **live/batch 不一致**：live 流程创建 `TaskResult` 时未记录耗时、对话输入，仅在部分事件中包含 `token_usage`。
- **错误日志**：`error_stage` 存在，缺乏统一的 `error_category`、`failure_reason`，也未串联 runner、adapter、agent 层之间的失败链。
- **结构化输出**：`logger.info(..., extra={"key_data": ...})` 未经过统一 formatter，字段在常规文件日志中不可见，难以与 `unified_logging` 汇合。

## ADK 原生信号（无需 OTel）
| 能力 | 场景 | 方案 |
| --- | --- | --- |
| `google.adk.*` logger | Runner、LLM 流程有丰富 DEBUG/INFO 事件（模型调用、Token 统计、工具流程） | 在 `logging.py` 对这些命名空间绑定 JSON handler，与现有结构化日志对齐。 |
| Callbacks（`before_agent` / `after_agent` / `before_model` / `after_model` / `before_tool` / `after_tool`） | 可截取请求/响应、工具参数 | 在 hooks 中写 wrapper，调用 `ExecutionContext.log_key_data()`，记录输入摘要、工具调用序列。 |
| Tool/Invocation Context | `ToolContext`、`CallbackContext` 携带 session、agent、用户信息 | 在工具实现里追加结构化日志，记录调用者、耗时、返回值、异常。 |
| Runner 事件 `usage_metadata` | `run_async` / `run_live` 的事件携带 prompt/completion token | 将 `usage_metadata` 转为 `token_usage`，写入 `TaskResult.metadata` 并同步到 observer。 |
| `AdkObserver.start_trace/add_span` | 虚拟 trace 能力 | 在不接 OTel 的情况下，利用 JSON 存储 span 树，定期落盘或推送内部观测 API。 |
| 第三方 SDK（可选） | AgentOps、LangWatch、Opik 等 | 轻量引入 `agentops.init()` 可获得时序图、Token 成本；LangSmith/LangWatch 提供 prompt 级追踪。 |

## 现有日志需补齐的关键字段
1. **执行耗时**：在 hooks 中预存 `start_time`，`after_execution` 计算耗时并写入 observer、`TaskResult.metadata.execution_stats.duration_ms`。
2. **输入/输出摘要**：沿用 `_summarize_input_messages`，截断 200 字；输出部分采样前 200 字，避免泄露敏感数据。
3. **Token 使用**：live/batch 均读取 `usage_metadata`，统一写入 `metadata.token_usage = {prompt_tokens, completion_tokens, total_tokens}`。
4. **执行上下文**：补齐 `agent_context`（agent_id、runner_id、session/用户），便于跨系统串联。
5. **日志结构化**：将 observer、工具日志统一交给 `ExecutionContext.log_key_data()`，确保 `logs/aether-frame-test.log` 能看到 JSON 字段。

## 失败场景监控与分类
- 新增 `ErrorCategory`（建议放在 `contracts/enums.py`）：
  - `INITIALIZATION`（初始化/依赖缺失）、`MODEL_INVOCATION`、`TOOL_CALL`、`RUNTIME_CONTEXT`、`STREAM_INTERRUPTED`、`SYSTEM` 等。
- 在 `TaskResult.metadata`、observer `key_data` 中写入：
  - `error_category`
  - `error_stage`（沿用现有字段）
  - `failure_reason`（面向上游，描述 root cause，例如 `missing_runner`, `generator_exit`, `tool_timeout`）
  - `is_retriable`（布尔）
- 对比 `TaskStatus.ERROR` 与 `TaskStatus.SUCCESS` 统计执行占比，兼顾 batch / live。
- 针对 runner 事件中的异常（如 `GeneratorExit`）在 `adk_live_stream()` 的 `finally` 分支写日志，避免无声失败。

## 业界观测实践要点
- **Uptrace（2025）**：强调建立统一语义，把 `输入→决策→工具→响应` 完整串联，指标需覆盖成功率、耗时分布、Token 成本、并发队列长度。[来源：Uptrace《AI Agent Observability Explained》]
- **AgentOps 官方指南**：通过包装 ADK 方法构建层级 span，自动记录 prompt、工具参数、错误场景，适合快速获得 trace 视图。[来源：AgentOps Integration 文档]
- **OTel GenAI 语义约定**：即便当前不接 OTel，也可借鉴其字段命名（`gen_ai.request.model`, `gen_ai.completion.token_count`），方便未来平滑迁移。
- **行业建议**：关注“非确定性失败”——如模型返回空响应、工具调用部分成功，需要额外指标记录 fallback/重试次数。

## 重点提升计划与 Checklist
### 计划 A：Observer 日志完善（高 ROI）
1. 在 `AdkAgentHooks` 保存 `start_time`，`after_execution` 计算耗时并回填。
2. live 流程：在 `adk_live_stream()` 创建 `start_time`，完成时写入 `result.metadata.execution_stats`。
3. `AdkObserver.record_execution_*`：
   - 统一 `metadata` 字段（含 `input_preview`, `token_usage`, `agent_context`, `execution_stats`）。
   - 通过 `ExecutionContext.log_key_data()` 输出 JSON，确保 logs 可读。
4. 单元 / 集成验证：
   - 运行 `python -m pytest tests/unit/agents/adk/test_adk_agent_hooks.py`（若无需新增则补测试）。
   - 执行 `scripts/run_complete_e2e.sh`，核对 `logs/aether-frame-test.log` 中新增字段。

### 计划 B：失败原因日志完善
1. 定义 `ErrorCategory` 枚举，更新返回结果与 observer 日志。
2. 在 `adk_adapter`、`adk_domain_agent`、工具执行路径补充 `failure_reason`、`is_retriable`。
3. 对 `hooks.on_error` 增加统一入口，集中写失败日志（含上下文）。
4. 回归测试：构造工具异常、模型异常、runtime 缺失三类场景，确认日志字段齐全。

## 进一步的监控补充（可选）
- 编排脚本，定期将 observer 的 `_metrics/_traces` 导出为 JSON，上传至内部监控或 ELK。
- 引入 AgentOps/LangWatch/Opik 其中之一，覆盖交互回放、token 成本分析。
- 对关键工具添加耗时阈值报警（例如通过现有 log shipper 上报）。
- 结合 `ExecutionContext`，自动生成执行摘要（输入摘要、工具序列、耗时、错误）供团队周报使用。

## 验证与落地建议
1. 每轮改动运行 `python -m pytest` 与 `scripts/run_complete_e2e.sh`，确认日志字段存在且数值合理。
2. 在 `logs/complete_e2e_test_*.log`、`logs/aether-frame-test.log` 搜索 `execution_stats`、`error_category`，确认格式。
3. 若引入第三方 SaaS，先在测试环境开关，保持与主日志链路隔离。

## 参考资料
- Uptrace. *AI Agent Observability Explained: Key Concepts and Standards*. 2025-04-16.
- Google ADK Docs. *Callbacks: Observe, Customize, and Control Agent Behavior*.
- Google ADK Docs. *Agent Observability with AgentOps*.

