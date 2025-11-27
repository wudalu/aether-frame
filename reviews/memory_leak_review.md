# 核心执行链路内存 / 资源泄漏审查

（交叉参考 `docs/architecture.md`、`docs/framework_abstraction.md`、`docs/adk_lifecycle_review.md`、`docs/adk_session_lifecycle_strategy.md`）

## 总览

- 当前 ADK 集成遵循“受控复用”思路，但文档中多次强调需要配套的主动清理和恢复通道；代码里仍存在多个只增长不回收的结构，违背了上述文档提出的“runner / agent / session 生命周期钩子”要求。
- 除 ADK 侧的对象缓存外，统一执行日志也会在每次调用时打开新的文件句柄且从不关闭，构成跨请求的资源泄露。
- 缺失清理钩子会持续持有业务会话 (`chat_session_id`) 对应的上下文和历史记录，既增加内存压力，也与 `docs/adk_session_lifecycle_strategy.md` 描述的“闲置淘汰 + 恢复”策略矛盾。

以下按风险排序列出主要问题及建议。

## 详细发现

1. **统一执行日志未关闭 FileHandler，文件句柄不断累积**  
   - 位置：`src/aether_frame/common/unified_logging.py:52-105`、`src/aether_frame/tools/service.py:176-185`、`src/aether_frame/observability/adk_logging.py:14-58`。  
   - 现象：`create_execution_context()` 每次调用都重新创建 `logging.FileHandler`，仅通过 `logger.handlers.clear()` 移除引用，并未调用 `handler.close()`。当工具服务或 ADK 观测钩子在每次任务/工具执行时使用该方法，会导致文件描述符和缓冲区在进程生命周期内一直增长。  
   - 建议：在移除 handler 前显式关闭；或将 `ExecutionContext` 改为上下文管理器，保证 `log_flow_end()` / `__aexit__` 中关闭 handler。必要时可缓存/复用 handler，避免“每请求一个文件”的模式。

2. **`_agent_sessions` 永久增长，旧会话引用不会释放**  
   - 位置：`src/aether_frame/framework/adk/adk_adapter.py:392-395, 539-544`。  
   - 现象：每次为 agent 创建新 ADK session 时，session_id 都被 append 到 `_agent_sessions[agent_id]`，但没有任何代码在 `remove_session_from_runner()` 或 `cleanup_chat_session()` 后剔除它们。`docs/adk_lifecycle_review.md` 已指出 cleanup 入口缺失，意味着这些列表会无限延伸，持有对历史会话及其元数据的引用。  
   - 建议：在 `RunnerManager.remove_session_from_runner()` 或 `AdkSessionManager.cleanup_chat_session()` 成功后，调用 adapter/manager 的回调删除对应 session_id；或者将 session 列表完全托管给 RunnerManager，集中管理生命周期。

3. **`RunnerManager._config_locks` 不回收，配置越多锁越多**  
   - 位置：`src/aether_frame/framework/adk/runner_manager.py:33-118`。  
   - 现象：`_config_locks.setdefault(config_hash, asyncio.Lock())` 为每个 agent 配置哈希创建锁，却从未在 runner 销毁或配置卸载时清理，导致锁对象及其事件循环引用持续存在。若业务针对不同用户定制 prompt / 工具，就会快速耗尽内存。  
   - 建议：在 `cleanup_runner()` 中，当 `config_to_runner` 删除该哈希时顺带移除锁；或用 `WeakValueDictionary` 存储锁对象，避免硬引用。

4. **`chat_sessions` / `SessionRecoveryStore` 清理依赖配置，易与策略偏离**  
   - 代码：`src/aether_frame/framework/adk/adk_session_manager.py:90-214, 917-1077`；配置：`src/aether_frame/config/settings.py:120-125`。  
   - 文档：`docs/adk_session_lifecycle_strategy.md` 要求“闲置淘汰 + 恢复 + 日志记录”，`docs/adk_lifecycle_review.md` 明确指出 `cleanup_chat_session()` 从未被调用。  
   - 现象：虽然生产环境已将 `session_idle_timeout_seconds` 设置为 3600 并能触发 idle watcher，但默认值仍为 0，开发/测试或误配环境很容易导致 watcher 不启动；再加上当前业务层没有显式调用 `AdkFrameworkAdapter.cleanup_chat_session()`，`chat_sessions` 字典以及 `available_knowledge`、`SessionRecoveryRecord` 等对象在这些环境里会无限增长。  
   - 建议：  
     1. 为避免环境差异，建议把正数 idle timeout 写入默认配置或提供部署校验，确保 watcher 始终启用。  
     2. 在执行链路末尾或 UI 触发“结束会话”时显式调用 `cleanup_chat_session()`，无论配置如何都能确保 chat session、ADK session、Runner、Agent 全链路同步回收。  
     3. 清理后立即移除 `_pending_recoveries`、`chat_sessions` 等引用，防止恢复记录长期驻留。

5. **Runner / Agent 映射在清理后仍保持强引用**  
   - 代码：`runner_manager.cleanup_runner`（`src/aether_frame/framework/adk/runner_manager.py:322-360`）、`AdkFrameworkAdapter._agent_runners`（`src/aether_frame/framework/adk/adk_adapter.py:61-188`）。  
   - 文档：`docs/adk_lifecycle_review.md` 中“Runner cleanup does not sync adapter mappings” 与 “Runner / agent / session cleanup entry points are missing”。  
   - 现象：`cleanup_runner` 仅删除 RunnerManager 内部状态，没有通知 adapter 更新 `_agent_runners` / `_agent_sessions`。这些 dict 会保留对已销毁 runner / agent 的引用，既会造成内存泄露，也会在下一次会话复用时触发“Runner 不存在”错误。  
   - 建议：  
     - 在 runner 被清理后调用 adapter 的 `_handle_agent_cleanup`，或由 RunnerManager 通过回调告知 adapter；  
     - 在 `AdkSessionManager.cleanup_chat_session()` 内部完成 runner/agent 的同步。  
     - 参照 `docs/adk_session_lifecycle_strategy.md` 的 MVP 设计，建立统一的“session end → runner cleanup → agent cleanup”流程和定期巡检任务。

## 建议优先级

| 优先级 | 问题 | 主要动作 |
|--------|------|----------|
| **P0** | Runner / Agent 映射不同步 | 补齐 `cleanup_runner` → adapter `_handle_agent_cleanup` → `AgentManager.cleanup_agent()` 的闭环，并在运行期检测到失效映射时即时清理，防止强引用长期存在。 |
| **P0** | FileHandler 未关闭 | 为 `create_execution_context()` 增加 handler 关闭/复用机制，并在 `ToolService`、ADK hooks 等所有调用点使用上下文式接口。 |
| **P0** | `_agent_sessions` 无边界增长 | 在 session 删除路径上同步清理由 agent → session 的映射，必要时新增集中管理结构。 |
| **P1** | `_config_locks` 永久保留 | 在 runner 清理时移除对应锁，或用弱引用结构；同时添加压力测试覆盖多配置场景。 |
| **P1** | Chat session 清理依赖配置 | 启用 idle watcher，提供业务层 API / hook 触发 `cleanup_chat_session()`，落实文档中的淘汰与恢复策略。 |

## 后续工作

1. 按 `docs/adk_session_lifecycle_strategy.md` 的 MVP 方案实现闲置清理（定时任务、日志、SessionRecovery 复用），并更新配置默认值。  
2. 对 `AdkSessionManager`、`RunnerManager`、`AgentManager` 之间的映射关系编写单元 / 集成测试，覆盖“session 结束、runner 销毁、agent 回收”的组合场景，防止回归。  
3. 补充运维监控：统计活跃 chat session / runner / agent 数量及清理频率，及时发现清理链路失效。  
4. 清理完成后更新架构文档，确保代码与“受控复用 + 主动回收”的策略保持一致。***
