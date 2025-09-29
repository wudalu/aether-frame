# Controller API 使用示例

## 新增的 RuntimeContext 预创建接口

### 1. 创建 RuntimeContext

使用 `/api/v1/create-agent` 接口预创建 RuntimeContext：

```bash
curl -X POST "http://localhost:8000/api/v1/create-agent" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "analytical_assistant",
    "system_prompt": "你是一个专业的数据分析师，擅长分析数据、生成图表和提供洞察。",
    "model": "deepseek-chat",
    "temperature": 0.7,
    "max_tokens": 1500,
    "available_tools": ["calculator", "chart_generator"],
    "user_id": "user_123",
    "framework_config": {
      "provider": "deepseek"
    },
    "metadata": {
      "purpose": "data_analysis",
      "priority": "high"
    }
  }'
```

响应示例：
```json
{
  "agent_id": "agent_abc123def456",
  "session_id": "adk_session_789xyz012",
  "runner_id": "runner_456ghi789",
  "framework_type": "ADK",
  "agent_type": "analytical_assistant",
  "model": "deepseek-chat",
  "created_at": "2025-01-28T10:30:45.123456",
  "processing_time": 0.856,
  "metadata": {
    "user_id": "user_123",
    "execution_id": "exec_context_create_1738056645123",
    "pattern": "create_new_agent_and_session",
    "created_by": "ControllerService",
    "purpose": "data_analysis",
    "priority": "high"
  }
}
```

### 2. 使用预创建的 RuntimeContext

使用返回的 `agent_id` 和 `session_id` 在后续的 `/api/v1/process` 请求中：

```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "analysis",
    "description": "数据分析任务",
    "messages": [
      {
        "role": "user",
        "content": "请分析一下销售数据的趋势",
        "metadata": {"source": "dashboard"}
      }
    ],
    "agent_id": "agent_abc123def456",
    "session_id": "adk_session_789xyz012",
    "metadata": {
      "context_reuse": true
    }
  }'
```

### 3. 继续使用同一个 Agent（新会话）

只使用 `agent_id`，系统会为该 agent 创建新的会话：

```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "analysis",
    "description": "新的分析任务",
    "messages": [
      {
        "role": "user",
        "content": "请分析另一组数据",
        "metadata": {"source": "new_request"}
      }
    ],
    "agent_id": "agent_abc123def456",
    "metadata": {
      "new_session": true
    }
  }'
```

## 优势

### 1. 性能提升
- **预创建优势**：RuntimeContext 创建包括 domain agent 初始化、ADK agent 创建、runner 和 session 设置
- **后续请求快速**：使用预创建的 context 可以跳过初始化步骤，直接进行任务处理

### 2. 会话管理
- **会话持续性**：使用相同的 `agent_id` + `session_id` 可以维持对话上下文
- **多会话支持**：同一个 agent 可以支持多个并行会话
- **灵活切换**：可以在不同会话间切换，或创建新会话

### 3. 资源复用
- **Agent 复用**：创建的 domain agent 可以被多个会话复用
- **Runner 复用**：相同配置的 agent 会复用同一个 runner
- **内存优化**：避免重复创建相同配置的组件

## 使用场景

### 1. 高频交互应用
```python
# 应用启动时预创建 context
context = create_context({
    "agent_type": "customer_service",
    "system_prompt": "你是客服助手...",
    "model": "deepseek-chat"
})

# 后续用户请求直接使用
for user_message in user_messages:
    response = process_with_context(
        context["agent_id"], 
        context["session_id"], 
        user_message
    )
```

### 2. 多用户会话管理
```python
# 为每个用户预创建专属 context
user_contexts = {}
for user_id in active_users:
    context = create_context({
        "agent_type": "personal_assistant",
        "user_id": user_id,
        "system_prompt": f"你是 {user_id} 的个人助手..."
    })
    user_contexts[user_id] = context

# 用户请求时使用对应的 context
def handle_user_request(user_id, message):
    context = user_contexts[user_id]
    return process_with_context(
        context["agent_id"],
        context["session_id"], 
        message
    )
```

### 3. 专业领域助手 - ECharts 图表生成示例

```bash
# 1. 创建专门的 ECharts 生成助手
curl -X POST "http://localhost:8000/api/v1/create-agent" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "echarts_generator",
    "system_prompt": "你是一个专业的ECharts图表生成器。无论用户输入什么内容，你都必须严格按照以下格式输出：\n\n1. 只输出一个完整的ECharts option配置对象\n2. 必须用```echarts 代码块包裹\n3. 不输出任何解释、说明或其他文字\n4. 配置必须是有效的JavaScript对象格式\n5. 根据用户输入的内容类型和数据，智能选择合适的图表类型（柱状图、折线图、饼图、散点图等）",
    "model": "deepseek-chat",
    "temperature": 0.3,
    "max_tokens": 2000
  }'

# 响应示例:
# {
#   "agent_id": "agent_echarts_abc123",
#   "session_id": "adk_session_xyz789",
#   ...
# }

# 2. 使用预创建的助手生成饼图
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "chart_generation",
    "messages": [
      {
        "role": "user",
        "content": "帮我生成一个饼图，显示公司各部门的人员分布：技术部40人，销售部30人，市场部20人，行政部10人"
      }
    ],
    "agent_id": "agent_echarts_abc123",
    "session_id": "adk_session_xyz789"
  }'

# 预期响应包含 ECharts 配置:
# {
#   "messages": [
#     {
#       "role": "assistant",
#       "content": "```echarts\n{\n  title: {\n    text: '公司各部门人员分布'\n  },\n  series: [{\n    type: 'pie',\n    data: [\n      {name: '技术部', value: 40},\n      {name: '销售部', value: 30},\n      {name: '市场部', value: 20},\n      {name: '行政部', value: 10}\n    ]\n  }]\n}\n```"
#     }
#   ]
# }
```

### 4. 多领域助手管理
```python
# 预创建不同专业领域的助手
contexts = {
    "coding": create_context({
        "agent_type": "coding_assistant",
        "system_prompt": "你是编程专家...",
        "available_tools": ["code_executor", "debugger"]
    }),
    "echarts": create_context({
        "agent_type": "echarts_generator", 
        "system_prompt": "你是专业的ECharts图表生成器...",
        "temperature": 0.3
    }),
    "analysis": create_context({
        "agent_type": "data_analyst", 
        "system_prompt": "你是数据分析师...",
        "available_tools": ["calculator"]
    })
}

# 根据任务类型选择合适的助手
def handle_task(task_type, message):
    context = contexts[task_type]
    return process_with_context(
        context["agent_id"],
        context["session_id"],
        message
    )
```

## 测试

运行测试脚本验证新接口：

```bash
# 测试创建 RuntimeContext
python tests/controller/test_http_requests.py --test 5

# 测试完整流程（创建 + 使用）
python tests/controller/test_http_requests.py --test 6

# 运行所有测试
python tests/controller/test_http_requests.py --test all
```