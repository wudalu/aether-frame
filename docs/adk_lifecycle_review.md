# ADK Runner/Agent/Session 生命周期巡检记录

## 背景
- 参照 `docs/session_manager_design.md` 中的设计约束（第43-47行），当前实现应遵循“单活会话、销毁重建、不复用会话”的策略。
- 重点巡检 `src/aether_frame/framework/adk/` 下的 `adk_adapter.py`、`runner_manager.py`、`adk_session_manager.py`，以及相关的 agent 管理逻辑，梳理 Runner、Agent、Session 生命周期实现与文档的一致性。

## 主要发现摘要
1. **Runner 清理未同步更新 Agent 映射**：`cleanup_runner`（`runner_manager.py:322-360`）销毁 runner 后未回收 `AdkFrameworkAdapter` 中的 `agent_id -> runner_id` 映射（见 `adk_adapter.py:61-188`），导致用户再次切回该 agent 时 `get_runner_for_agent` 抛错。
2. **历史迁移使用错误 user_id**：`_extract_chat_history`（`adk_session_manager.py:312-328`）读取 `runner_context["user_id"]`，而 `_create_session_in_runner`（`runner_manager.py:240-269`）会在每次建会话时覆盖该字段，多会话并存时后续历史迁移会用到错误的 user_id。
3. **缓存会话未校验实际存在**：`coordinate_chat_session` 在“同一 agent”路径只返回缓存的 `active_adk_session_id`（`adk_session_manager.py:76-122`），若外层已经清理了 session（例如通过 RunnerManager API 或后台任务），会返回指向失效 session 的 ID，后续执行将直接失败。
4. **复用策略需体系化支撑**：当前实现已明确支持 Agent/Runner 复用（例如 `_select_agent_for_config` 复用 agent/runner），后续需更新设计文档，对齐“受控复用 + 主动清理”的策略并补齐配套机制。
5. **Runner/Agent/Session 清理入口未落地**：`cleanup_chat_session`（`adk_session_manager.py:265-277`）尚无调用入口；Runner、Agent 的主动回收策略仍缺失，长期运行可能导致资源堆积。

## 销毁策略现状梳理

- **Runner 层**  
  - 能力：`runner_manager.cleanup_runner`（`runner_manager.py:322-360`）与 `remove_session_from_runner`（`runner_manager.py:362-407`）负责释放 SessionService、ADK Runner。  
  - 触发：仅在 `AdkSessionManager._cleanup_session_only` 中被动调用（`adk_session_manager.py:224-236`），该函数只在 agent 切换流程 `_switch_agent_session`（`adk_session_manager.py:130-171`）中触发；如果用户没有发生 agent 切换或外部主动调用，这些清理逻辑不会执行。`AdkFrameworkAdapter.shutdown` 虽尝试调用 `runner_manager.cleanup_all`（`adk_adapter.py:782-783`），但目前 RunnerManager 未实现该方法。  
  - 缺口：缺少统一的生命周期入口（会话结束、进程退出钩子），以及与 AgentManager 的联动清理。

- **Session 层**  
  - 能力：`AdkSessionManager.cleanup_chat_session`（`adk_session_manager.py:265-277`）封装了“先删 session，再按需删 runner”，并清理 `chat_sessions` 缓存。  
  - 触发：当前代码库没有调用该 API；唯一的销毁场景仍来自 agent 切换时的 `_cleanup_session_only`。因此同一 agent 长时对话或用户主动结束聊天时，并不会释放 session。  
  - 缺口：需要在业务层或 FrameworkAdapter 层新增显式的 “chat end / timeout” 调用，或提供自动过期回收机制。

- **Agent 层**  
  - 能力：`AgentManager.cleanup_agent` 与 `cleanup_expired_agents`（`agents/manager.py:57-136`）负责销毁 domain agent 并清理内部映射。  
  - 触发：ADK 适配层未调用这些接口。即使 runner/session 被清理，agent 仍常驻 `_agents/_agent_configs`，可能导致复用逻辑拿到已经无 runner 的 agent（见问题 1）。  
  - 缺口：需要在 runner 被销毁或 agent 长时间 idle 时触发 AgentManager 清理，并与 `_agent_runners` 映射同步。

> 建议：在修复计划中安排补充统一的销毁入口（比如 session 结束 API、Adapter 级 shutdown 钩子、定时回收任务），并确保 RunnerManager、SessionManager、AgentManager 三者的状态同步。

## 详细分析

### 1. Runner 清理后 Agent 映射失效
- `_cleanup_session_only` 会在旧会话无其他 session 时调用 `runner_manager.cleanup_runner`（`adk_session_manager.py:224-236`）。
- `cleanup_runner` 仅删除内部 `self.runners/self.session_to_runner/self.config_to_runner`，但 `AdkFrameworkAdapter` 的 `_agent_runners` 映射仍保留老的 runner_id。
- 当用户之后切回该 agent 时，`get_runner_for_agent`（`runner_manager.py:368-394`）读取到已被销毁的 runner_id，并在验证阶段抛出 “Runner ... does not exist”。这会让 agent 切换流程直接失败。
- 建议：在 `cleanup_runner` 成功后通知 adapter 清理 `_agent_runners`，或在 session manager 切换时检测、自动重建 runner。

### 2. 历史迁移使用全局 user_id
- `_create_session_in_runner` 在每次新建 session 时都会覆写 `runner_context["user_id"]` 为当前请求的 user（`runner_manager.py:240-269`）。
- `_extract_chat_history`/`_inject_chat_history` 依赖该字段调用 `SessionService.get_session`（`adk_session_manager.py:312-328`、` adk_session_manager.py:360-420`）。
- 当一个 runner 承载多个用户会话时（例如 agent 复用），后建会话会把 `runner_context["user_id"]` 改成新用户，旧 session 的历史迁移会拿错 user_id，从而查不到 session 或误操作到他人会话。
- 建议：为每个 session 持久化 user_id（可复用 `runner_context["sessions"][session_id].user_id`），或在 session manager 内维护 `session_id -> user_id` 映射。

### 3. 同 agent 分支缺乏存在性校验
- 当 `chat_session.active_agent_id == target_agent_id` 且 `active_adk_session_id` 非空时，`coordinate_chat_session` 直接返回该 session_id（`adk_session_manager.py:92-111`）。
- 若 session 已被后台清理或 `RunnerManager.remove_session_from_runner` 执行过，缓存未更新，后续执行会在 `_create_runtime_context_for_existing_session`（`adk_adapter.py:206-223`）报 “Session not found”。
- 建议：同 agent 分支应调用 `runner_manager.get_runner_by_session` 或直接验证 `runner_context["sessions"]` 中是否存在该 session；缺失时应自动重建。

### 4. 复用策略与设计约束冲突
- 文档强调“Create-Destroy Pattern”+“No Session Reuse”（`docs/session_manager_design.md:43-47`）。
- 实际实现通过 `_select_agent_for_config` 与 `_config_agents` 支持 agent/runner 复用（`adk_adapter.py:247-339`），`RunnerManager` 也复用了 `config_to_runner`。
- SessionManager 仍假设单一活动会话，并在切换时直接销毁 runner，这与复用策略冲突：复用场景下销毁 runner 会影响其他会话；不销毁则会残留会话历史与 user_id 问题。
- 建议：要么更新设计文档说明复用策略及配套清理机制，要么收敛代码以符合“Create-Destroy”约束。

### 5. 会话清理流程缺口
- `AdkSessionManager.cleanup_chat_session` 已实现 Runner/Session 清理（`adk_session_manager.py:265-277`），但在 `AdkFrameworkAdapter` 中没有触发点或 API 绑定。
- 缺少“聊天结束/超时”入口意味着 SessionManager 只能在 agent 切换时清理资源，若用户长期停留或只使用单 agent，会导致会话/runner 长期占用。
- 建议：在对外接口加入口，例如在业务层面显式调用 cleanup，或在 RunnerManager 定期执行回收策略。

## 关注点与后续建议
- 在修复映射与 user_id 问题之前，建议补充自动化测试覆盖“切换后再切回”“同 runner 多用户”场景，复现现有缺陷。
- 需要决定最终形态：是贯彻“销毁重建”还是正式支持复用。如果继续复用，需要同步更新 SessionManager 设计文档与生命周期管理策略。

## 优先级与修复计划

| 问题 | 优先级 | 影响范围 | 建议修复思路 | 预估工作量 |
| --- | --- | --- | --- | --- |
| Runner 清理未同步更新 Agent 映射（见第1节） | 高 | 所有涉及 agent 切换/复用的聊天流；切换回旧 agent 会直接报错 | 在 `cleanup_runner` 完成后触发 adapter 清理 `_agent_runners`，或在 `get_runner_for_agent` 检测失效映射后自动重建 runner；补充“切换-切回”回归测试 | 中（约 1~2 人日，需改动 adapter + runner manager 并补测） |
| 历史迁移使用全局 user_id（见第2节） | 高 | 同 runner 多用户/多会话场景；可能造成历史迁移失败或串话 | 为 `runner_context["sessions"]` 存储 `user_id`，调整 `_extract/_inject` 使用该映射；补充多用户会话测试 | 中（约 2 人日，需要修改 session manager + runner manager，新增测试） |
| 同 agent 会话存在性未校验（见第3节） | 中 | 会话被后台清理或 runner 重建后继续使用旧 session 的场景；表现为偶发 ExecutionError | 在返回旧 session 前调用 `runner_manager.get_runner_by_session` 校验，不存在则自动重建；补充模拟后台清理的测试 | 低（约 0.5 人日） |
| 设计与实现复用策略冲突（见第4节） | 中 | 项目后续演进（是否继续复用）决策；影响清理策略、资源模型 | 需要产品/架构确认目标策略；若继续复用，应更新设计文档并完善 SessionManager 的复用安全性；若回归销毁重建，需要调整 adapter 逻辑 | 中（1 人日调研 + 视最终决策追加） |
| 会话清理入口缺失（见第5节） | 中 | 长期运行时 Runner/Session 累积；影响资源占用与后续复用策略 | 与业务层/外部接口对齐“聊天结束”钩子；补充超时/手动清理调用，或在 RunnerManager 增加定时回收 | 中（约 1~2 人日，需跨层协调） |

### 综合优先级与执行顺序建议

1. **P0：保障现有会话切换稳定性**  
   - 覆盖表格中的两个高优先级问题（映射同步与 user_id 记录）。两者相互关联，建议同一迭代内完成，并补充 E2E 回归测试（切换-切回、多用户复用）。  
   - 同时在实现中为后续销毁入口预留钩子（例如在 runner 清理回调中顺便触发 agent 清理）。  

2. **P1：完善会话存在性校验与清理入口**  
   - 先处理“同 agent 会话存在性未校验”，可复用 P0 的测试基线。  
   - 随后落地会话清理入口：在业务层定义 `end_chat_session` API 或超时策略，同时串联 AgentManager 的 `cleanup_agent`。  

3. **P1/P2：统一策略对齐**  
   - 与产品/架构确认最终策略：继续复用 or 坚持销毁重建。  
   - 若选择复用，需编写新的设计补充文档、梳理 SessionManager 状态机，并根据决策评估是否新增“runner 池”或“会话租约”机制。该项可能拆分为多阶段交付。  

> 执行建议：按照 P0 → P1 → P1/P2 的顺序推进，每阶段完成后更新设计文档与测试基线，确保生命周期管理与实际实现保持一致。
