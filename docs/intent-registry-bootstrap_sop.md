# 离线 Intent Registry Bootstrap 操作说明

状态: Draft  
日期: 2026-03-24  
范围: 提供一份精简的离线操作流程，用于构建 intent-recognition registry 的 bootstrap 产物。

交叉引用:
- `docs/intent-registry-bootstrap_design.md`
- `docs/intent-recognition_design.md`
- `docs/examples/intent-bootstrap/README.md`

## 1. 目标

这份 SOP 描述的是最小可用的离线流程，目标是：

1. 导出内部交互 traces
2. 生成机器辅助的 intent 标签
3. 由人工 review 这些标签
4. 产出一份 draft registry 包
5. 将 review 后的草案 promote 成 runtime 可用的 registry 产物

这是一个离线流程。

它不属于线上 runtime intent-recognition 链路的一部分。

## 2. 数据来源

主数据源应当是内部流量，而不是公开数据集。

推荐优先级顺序：

1. LLM request/response observability
2. execution metadata，如果有
3. 一份 checked-in 的 capability seed 文件

推荐获取链路：

```text
LLM request/response observability
  + execution metadata
  -> offline export job
  -> sanitized input-traces.jsonl
  -> bootstrap script
```

`input-traces.jsonl` 的最小必需字段：

1. `sample_id`
2. `conversation_id`
3. `user_message`
4. `created_at`

推荐补充字段：

1. `session_id`
2. `invocation_id`
3. `llm_input_text`
4. `llm_output_text`
5. `agent_name`
6. `model_name`
7. `final_status`
8. `metadata`

操作规则：

1. 如果第一阶段只能导出一个语义字段，优先导出 `user_message`
2. 当团队进入 slot mining、clarification 分析、evaluation 阶段时，再补 `llm_output_text`

## 3. Capability Seeds

脚本还需要一份小型、checked-in 的 seed 文件，用来定义当前支持的候选 intents。

推荐来源：

1. 产品当前支持的 execution paths
2. playbooks 或支持的 skill families
3. 基于这些 execution paths 人工整理出的 candidate intents

参考文件：

```text
docs/examples/intent-bootstrap/capability-seeds.example.json
```

操作规则：

1. seed intents 来自产品真实支持的 capability boundary
2. internal traffic 用来验证和修正 seed set
3. internal traffic 不应自动生成 production intents

## 4. 第一阶段：Prelabel Review

使用 `prelabel-review` 模式运行脚本：

```bash
uv run python scripts/bootstrap_intent_registry.py \
  --mode prelabel-review \
  --input-traces <path-to-input-traces.jsonl> \
  --capability-seeds <path-to-capability-seeds.json> \
  --output-dir <path-to-output-dir> \
  --enable-helper-labeling
```

目的：

1. 给内部流量生成机器建议标签
2. 识别低置信度和 `unknown` 样本
3. 产出人工 review 所需的 payload

预期输出：

```text
<output-dir>/
  prelabels.jsonl
  labeling_summary.json
  review_payloads/
    label_studio.jsonl
  unknown_samples.jsonl
```

输出使用方式：

1. 查看 `labeling_summary.json`，确认整体分布和明显缺口
2. 将 `review_payloads/label_studio.jsonl` 送入人工 review 流程
3. 单独查看 `unknown_samples.jsonl`，因为它们通常意味着不支持的流量或缺失的 seed intents

## 5. Human Review

机器辅助标签不是 production truth。

它们只是 review 输入。

人工 review 应该做：

1. 确认正确标签
2. 修正错误标签
3. 将真正 out-of-scope 的样本保留为 `unknown`
4. 不要在未 review capability boundary 的前提下发明新的 production intents

这一步的输出应是一份 reviewed label 文件，例如：

```text
reviewed-labels.jsonl
```

## 6. 第二阶段：Draft Registry

人工 review 完成后，使用 `draft-registry` 模式运行脚本：

```bash
uv run python scripts/bootstrap_intent_registry.py \
  --mode draft-registry \
  --input-traces <path-to-input-traces.jsonl> \
  --capability-seeds <path-to-capability-seeds.json> \
  --reviewed-labels <path-to-reviewed-labels.jsonl> \
  --output-dir <path-to-output-dir>
```

目的：

1. 按 intent 聚合 reviewed labels
2. 生成第一版机器产出的 registry draft
3. 生成配套的 review artifacts

预期输出：

```text
<output-dir>/
  candidate_intents.json
  slot_candidates.json
  draft_registry.json
  review_report.md
```

输出使用方式：

1. 查看 `candidate_intents.json`，确认候选 intent 集仍然和产品 capability boundary 对齐
2. 将 `slot_candidates.json` 视为 draft，而不是最终 slot truth
3. 将 `review_report.md` 作为面向人的总结
4. 将 `draft_registry.json` 视为离线 review artifact，而不是 runtime artifact

## 7. Promotion 到 Runtime

runtime 不应直接读取原始 bootstrap 输出。

promotion 是一个独立的、需要人工 review 的步骤：

```text
internal traces
  -> prelabel-review
  -> human review
  -> reviewed labels
  -> draft-registry
  -> human promotion
  -> runtime registry
```

promotion 应该做：

1. review draft intent list
2. review required / optional slots
3. review clarification wording
4. 将批准后的 draft 转成 runtime registry 格式

推荐的 runtime 目标形态：

1. 一个 checked-in 的 Python module
2. 或一个 checked-in 的受控 JSON artifact

操作规则：

1. `draft_registry.json` 不是 runtime 的 source of truth
2. promote 后的 registry 才是 runtime 的 source of truth

## 8. 边界

这条流程刻意保持窄范围。

它不负责：

1. 自动发布 registry 变更
2. 自动重训 production classifier
3. 替代 runtime intent recognition
4. 取消产品或 domain review 的必要性

## 9. 快速开始

可运行示例见：

1. [docs/examples/intent-bootstrap/README.md](/Users/wudalu/hsbc_code/aether-frame/docs/examples/intent-bootstrap/README.md)
2. [scripts/bootstrap_intent_registry.py](/Users/wudalu/hsbc_code/aether-frame/scripts/bootstrap_intent_registry.py)

详细设计说明见：

1. [docs/intent-registry-bootstrap_design.md](/Users/wudalu/hsbc_code/aether-frame/docs/intent-registry-bootstrap_design.md)
