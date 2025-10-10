# Tool Integration Design - MCP Support

## Overview

This document outlines the minimal viable implementation for integrating Model Context Protocol (MCP) tool support into Aether Frame, focusing on core functionality and streaming support.

## Architecture Analysis

### Tool Data Flow

基于对TaskRequest数据结构的分析，真实的工具流程：

```python
# 用户输入: 工具名称列表
user_tools = ["echo", "mcp_server.search", "weather"]

# 系统处理: 工具名称 → UniversalTool对象
# TaskRequest: 包含UniversalTool对象列表
task_request = TaskRequest(
    available_tools=[UniversalTool(...), ...]  # List[UniversalTool] - 已解析的工具对象
)

# Agent执行: UniversalTool → ADK函数
adk_tools = [convert_to_adk_function(tool) for tool in task_request.available_tools]
```

### 关键发现

1. **TaskRequest.available_tools**: 用户指定的工具列表（`List[UniversalTool]`对象）
2. **AgentConfig.available_tools**: Agent默认工具能力（`List[str]`名称）
3. **工具解析时机**: 在TaskRequest创建阶段，而不是Agent创建阶段

## MCP集成策略

### 核心流程

**阶段1: 系统启动时**
```
Bootstrap → ToolService.initialize() → _load_mcp_tools() → 构建工具池
```

**阶段2: TaskRequest创建时** ⭐ 关键阶段
```
用户工具名称 → ToolResolver.resolve_tools() → UniversalTool对象 → TaskRequest.available_tools
```

**阶段3: Agent执行时**
```
TaskRequest.available_tools → _get_adk_tools() → ADK函数 → Agent.tools
```

### 数据流

```
用户工具名称 → ToolResolver → UniversalTool对象 → TaskRequest → ADK函数转换 → 工具执行 → MCP调用
```

## Architecture Overview

### 完整集成流程图

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Bootstrap     │───▶│   ToolService    │───▶│  MCP Servers    │
│                 │    │   .initialize()  │    │                 │
│                 │    │                  │    │ localhost:8000  │
└─────────────────┘    └──────────────────┘    │ remote-api.com  │
                               │                │     ...         │
                               ▼                └─────────────────┘
                       ┌──────────────────┐
                       │ _load_mcp_tools()│
                       │                  │
                       │ • MCPClient创建  │
                       │ • 工具发现        │
                       │ • MCPTool注册    │
                       │ • 构建工具池      │
                       └──────────────────┘
                               │
                               ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│TaskRequest创建  │───▶│ ToolResolver     │───▶│  Tool Pool      │
│                 │    │                  │    │                 │
│用户输入:        │    │ • 解析工具名称    │    │ builtin.echo    │
│["echo",         │    │ • 权限检查        │    │ builtin.chat_log│
│ "mcp.search"]   │    │ • 查找UniversalTool│   │ mcp_server.tool1│
│                 │    │ • 创建对象列表    │    │ mcp_server.tool2│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                               │
                               ▼
                       ┌──────────────────┐
                       │ TaskRequest      │
                       │                  │
                       │ available_tools= │
                       │ [UniversalTool1, │  
                       │  UniversalTool2] │
                       └──────────────────┘
                               │
                               ▼ (Agent执行时)
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Agent Execution │───▶│  _get_adk_tools()│───▶│ ADK Functions   │
│                 │    │                  │    │                 │
│AdkDomainAgent   │    │ • 遍历available_ │    │ echo_func()     │
│.execute()       │    │   tools          │    │ search_func()   │
│                 │    │ • 转换为ADK函数   │    │ ...             │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                               │
                               ▼ (工具调用时)
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Tool Execution  │───▶│ ToolRequest      │───▶│  MCPTool        │
│                 │    │                  │    │                 │
│ ADK调用函数      │    │ tool_name        │    │ .execute()      │
│ search_func()   │    │ parameters       │    │ .execute_stream │
│                 │    │ session_id       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
                                               ┌─────────────────┐
                                               │  MCP Server     │
                                               │                 │
                                               │ HTTP streaming  │
                                               │ Tool execution  │
                                               └─────────────────┘
```

## Core Components

### 1. MCPServerConfig

```python
@dataclass
class MCPServerConfig:
    """Simple MCP server configuration."""
    name: str  # Server identifier for namespacing
    endpoint: str  # Server endpoint (e.g., "http://localhost:8000/mcp")
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
```

### 2. MCPClient

```python
class MCPClient:
    """Simple MCP client for tool execution."""
    
    async def discover_tools(self) -> List[UniversalTool]:
        """Discover available tools from MCP server."""
        
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute tool synchronously."""
        
    async def call_tool_stream(self, name: str, arguments: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """Execute tool with streaming response."""
```

### 3. MCPTool

```python
class MCPTool(Tool):
    """MCP tool wrapper implementing the Tool interface."""
    
    async def execute(self, tool_request: ToolRequest) -> ToolResult:
        """Synchronous tool execution."""
        
    async def execute_stream(self, tool_request: ToolRequest) -> AsyncIterator[ToolStreamChunk]:
        """Streaming tool execution."""
        
    @property
    def supports_streaming(self) -> bool:
        """Check if tool supports streaming."""
```

### 4. ToolResolver

```python
class ToolResolver:
    """工具解析器 - 将工具名称解析为UniversalTool对象."""
    
    async def resolve_tools(self, tool_names: List[str], user_context: Optional[UserContext] = None) -> List[UniversalTool]:
        """将工具名称列表解析为UniversalTool对象列表."""
```

## Streaming Support

### MCP Streaming实现总结 🎯

**实施期间的重要发现和技术突破:**

#### 核心挑战与解决方案

**挑战1: 理解MCP协议层次**
- ❌ 初始误解：认为需要手动实现HTTP SSE通信
- ✅ 正确理解：MCP SDK提供抽象，Streamable HTTP是transport协议
- 💡 关键洞察：SSE用于会话管理，工具调用使用standard JSON-RPC

**挑战2: Progress Notifications传输**
- ❌ 第一次尝试：使用_meta参数传递progressToken  
- ❌ 第二次尝试：手动实现notification handler但无progress events
- ✅ 最终解决：使用`progress_callback`参数在call_tool()中

**挑战3: 真实vs伪Streaming识别**
- ❌ 伪流式：客户端等待完整结果后分块 (2-3秒阻塞 → 瞬间分块)
- ✅ 真实流式：服务器实时产生progress events (0.01s, 0.51s, 1.21s增量时间戳)
- 📊 验证方法：时间戳分析 + 事件计数

#### 技术实现要点

**1. MCP SDK正确使用方式**
```python
# 正确的progress callback实现
async def progress_callback(progress: float, total: float, message: str = ""):
    # 实时接收服务器端progress events
    
# 正确的tool调用方式
await session.call_tool(name, arguments, progress_callback=progress_callback)
```

**2. 服务器端Progress Reporting**
```python
# 服务器端必须实现context-based progress reporting
@mcp.tool()
async def tool(ctx: Context[ServerSession, None]):
    await ctx.report_progress(progress=0.5, total=1.0, message="Processing...")
```

**3. 双重通知机制架构**
```python
# 同时支持progress_callback和notification_handler
# progress_callback: 直接处理progress events
# notification_handler: 处理logging等其他notifications
```

#### 性能特征

**真实Streaming证据：**
- 实时时间戳：0.01s → 0.51s → 1.21s → 1.51s → 2.02s → 2.73s
- 6个progress events + 完整logging notifications
- 服务器端真实处理时间：每步0.3-0.7秒
- 无阻塞等待：客户端实时接收events

#### 架构优势

**1. 透明降级**
- streaming服务器：使用progress_callback接收real-time events  
- 非streaming服务器：自动fallback到标准JSON响应
- 统一接口：调用方无需关心底层实现

**2. 事件完整性**
- Progress events: 工具执行进度
- Logging events: 调试信息
- Error events: 异常处理
- Complete events: 执行完成

### Tool Base Class Extension

需要扩展现有的Tool基类以支持streaming：

```python
class Tool(ABC):
    async def execute_stream(self, tool_request: ToolRequest) -> AsyncIterator[ToolStreamChunk]:
        """Execute tool with streaming response (optional)."""
        
    @property
    def supports_streaming(self) -> bool:
        """Check if tool supports streaming execution."""
```

### ToolStreamChunk Data Structure

```python
@dataclass
class ToolStreamChunk:
    """Streaming chunk for tool execution."""
    tool_name: str
    chunk_type: str  # "data", "progress", "complete", "error"
    content: Union[str, Dict[str, Any]]
    is_final: bool = False
    sequence_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
```

## Implementation Strategy

### Phase 1: Core MCP Integration
1. **MCPServerConfig**: Server configuration data structure
2. **MCPClient**: Basic MCP communication client
3. **MCPTool**: Tool wrapper implementing Tool base class
4. **ToolResolver**: Tool name resolution component
5. **ToolService Integration**: Update _load_mcp_tools() method

### Phase 2: Streaming Features
1. **Tool Base Extension**: Add execute_stream() method
2. **ToolStreamChunk**: Streaming data structure
3. **ToolService Streaming**: Add execute_tool_stream() method
4. **ADK Integration**: Stream-aware tool conversion

### Phase 3: Advanced Features
1. **Authentication**: OAuth and API key support
2. **Resource Support**: MCP resources and prompts integration
3. **Caching**: Tool definition and result caching
4. **Permissions**: Tool access control system

## Directory Structure

```
src/aether_frame/tools/mcp/
├── __init__.py
├── client.py           # MCPClient
├── config.py          # MCPServerConfig  
└── tool_wrapper.py    # MCPTool

src/aether_frame/tools/
├── resolver.py         # ToolResolver
└── service.py         # Enhanced ToolService
```

## Configuration

### System Configuration

```python
{
    "tool_service": {
        "enable_mcp": True,
        "mcp_servers": [
            {
                "name": "local_tools",
                "endpoint": "http://localhost:8000/mcp",
                "headers": {"Authorization": "Bearer your-token"},
                "timeout": 30
            }
        ]
    }
}
```

### Usage Example

```python
# 1. 用户输入工具名称
user_tool_names = ["echo", "mcp_server.search", "weather"]

# 2. 创建TaskRequest（包含工具解析）
task_request = await task_engine.create_task_request(
    task_id="task_123",
    task_type="chat", 
    description="Help me search for information",
    tool_names=user_tool_names
)

# 3. Agent执行时使用TaskRequest中的工具
agent = AdkDomainAgent(agent_id, config)
result = await agent.execute(AgentRequest(task_request=task_request))
```

## Dependencies

```python
# requirements/base.in 
mcp>=1.0.0  # MCP Python SDK
```

## 分阶段实施计划 - 更新状态 📊

### 🎉 实施成果总结 (2025-10-10)

**超预期完成阶段：**
- ✅ **Phase 1: 核心MCP集成** - COMPLETED (100%)
- ✅ **Phase 2: Streaming功能** - COMPLETED (100%) 
- 🔄 **Phase 3: 完整系统集成** - PARTIALLY COMPLETED (40%)

**实际vs计划对比：**
- 📅 **原计划时间**: Phase 1 需要1-2天
- 🚀 **实际成果**: 在1天内完成Phase 1 + Phase 2 + 部分Phase 3
- 💡 **关键突破**: 真正的server-side streaming实现

### 详细实施状态

| 阶段 | 模块 | 功能描述 | 状态 | 验证结果 | 下一步行动 |
|-----|------|----------|------|----------|------------|
| **Phase 1.1** ✅ | MCPServerConfig | MCP服务器配置数据结构 | COMPLETED | ✅ 配置解析、验证、默认值处理 | 无 |
| **Phase 1.2** ✅ | MCPClient | 基础MCP通信客户端 + **真实streaming** | COMPLETED | ✅ 连接、工具发现、真实progress notifications | 无 |
| **Phase 1.3** ✅ | MCPTool | MCP工具包装器 + **流式支持** | COMPLETED | ✅ Tool接口、参数转换、流式执行 | 无 |
| **Phase 1.4** ✅ | ToolService扩展 | MCP工具加载和注册 | COMPLETED | ✅ 4个MCP工具成功注册到工具池 | 无 |
| **Phase 2.1** ✅ | ToolStreamChunk | 流式工具执行数据结构 | COMPLETED | ✅ 使用现有TaskStreamChunk | 无 |
| **Phase 2.2** ✅ | Tool基类扩展 | 添加execute_stream方法 | COMPLETED | ✅ MCPTool已实现streaming | 无 |
| **Phase 2.3** ✅ | MCPTool流式支持 | MCP工具流式执行 | COMPLETED | ✅ 8个chunks,5.13秒真实streaming | 无 |
| **Phase 3.1** 🔄 | ToolResolver | 工具名称解析器 | **NEEDED** | ❌ 需要实现"mcp.tool"格式解析 | **下一步** |
| **Phase 3.2** 🔄 | TaskRequest集成 | 工具解析集成点 | **NEEDED** | ❌ 需要集成到TaskRequest创建 | 待Phase 3.1 |
| **Phase 3.3** 🔄 | ADK Agent集成 | ADK函数转换和执行 | **NEEDED** | ❌ 需要Agent能调用MCP工具 | 待Phase 3.2 |

### 🚀 当前系统能力

**✅ 已实现功能:**
```python
# 1. MCP工具注册和发现
tool_service = ToolService()
await tool_service.initialize({
    "enable_mcp": True,
    "mcp_servers": [{"name": "server", "endpoint": "http://localhost:8002/mcp"}]
})

# 2. 工具列表查看
tools = await tool_service.list_tools()
# 返回: ['builtin.echo', 'test_streaming_server.long_computation', ...]

# 3. 同步工具执行
result = await tool_service.execute_tool(ToolRequest(
    tool_name="test_streaming_server.long_computation",
    parameters={"steps": 5}
))

# 4. 真实streaming工具执行
tool = tool_service._tools["test_streaming_server.long_computation"]
async for chunk in tool.execute_stream(tool_request):
    print(f"Real-time: {chunk.content}")  # 实时接收数据
```

**🔥 性能证据:**
- ✅ **真实streaming**: 8个chunks，时间戳0.01s→1.02s→2.02s→3.02s→4.02s→5.03s
- ✅ **Progress events**: 6个progress notifications实时接收
- ✅ **工具发现**: 4个MCP工具 + 3个builtin工具 = 7个工具
- ✅ **错误处理**: 完整的异常处理和状态管理

### 📋 下一阶段任务 (Phase 3 完成)

#### 🎯 Priority 1: ToolResolver实现 (Phase 3.1)

**目标**: 支持用户友好的工具名称解析

**需要实现:**
```python
class ToolResolver:
    async def resolve_tools(self, tool_names: List[str]) -> List[UniversalTool]:
        """
        解析工具名称格式:
        - "echo" → "builtin.echo"
        - "mcp.search" → "mcp_server.search" 
        - "test_streaming_server.long_computation" → 完整名称
        """

# 用例:
resolver = ToolResolver(tool_service)
tools = await resolver.resolve_tools(["echo", "mcp.search", "weather"])
```

**验证标准:**
- ✅ 名称解析：短名称→完整名称映射
- ✅ 权限检查：集成现有权限系统
- ✅ 工具查找：支持namespace.tool_name格式
- ✅ 错误处理：找不到工具时的处理

#### 🎯 Priority 2: TaskRequest集成 (Phase 3.2)

**目标**: 集成到TaskRequest创建流程

**需要实现:**
```python
# 在TaskRequest创建时自动解析工具
task_request = await task_engine.create_task_request(
    task_id="task_123",
    tool_names=["echo", "mcp.search", "weather"]  # 用户友好名称
)
# TaskRequest.available_tools = [UniversalTool(...), ...] # 自动解析
```

#### 🎯 Priority 3: ADK Agent集成 (Phase 3.3)

**目标**: 让Agent能使用MCP工具

**需要实现:**
```python
# Agent执行时能调用MCP工具
agent = AdkDomainAgent(agent_id, config)
result = await agent.execute(AgentRequest(
    task_request=task_request  # 包含MCP工具的TaskRequest
))
```

### 📅 实施时间线

| 时间 | 阶段 | 预期成果 | 验证方式 |
|------|------|----------|----------|
| **明天** | Phase 3.1 | ToolResolver完成 | 工具名称解析测试 |
| **后天** | Phase 3.2 | TaskRequest集成 | 端到端工具解析 |
| **第3天** | Phase 3.3 | ADK Agent集成 | Agent使用MCP工具 |
| **第4天** | Production | 生产就绪 | 完整e2e测试 |

### 🎯 成功标准

**Phase 3完成后，用户应该能够:**
```python
# 1. 简单配置MCP服务器
config = {"enable_mcp": True, "mcp_servers": [...]}

# 2. 使用友好的工具名称
user_tools = ["echo", "mcp.search", "weather"]

# 3. 创建包含MCP工具的任务
task_request = await create_task_request(tool_names=user_tools)

# 4. Agent自动使用MCP工具
agent = AdkDomainAgent(...)
result = await agent.execute(AgentRequest(task_request=task_request))

# 5. 享受真实的streaming体验
# (已实现! 🎉)
```

### 🔍 已验证的架构优势

1. **真实Streaming** ✅
   - 服务器端实时progress reporting
   - 客户端实时事件接收
   - 透明降级到非streaming服务器

2. **统一接口** ✅
   - MCPTool实现标准Tool接口
   - 与builtin工具无缝集成
   - 支持同步和异步执行

3. **可扩展架构** ✅
   - 支持多MCP服务器
   - 命名空间隔离
   - 配置驱动的工具加载

**下一步重点**: 完成用户体验层面的集成，让MCP工具在整个系统中"无缝"使用。

### 详细验证标准 - 完成状态

#### Phase 1: 核心MCP集成 ✅ COMPLETED

**Phase 1.1 - MCPServerConfig** ✅ COMPLETED
- ✅ 配置解析正确性：支持name, endpoint, headers, timeout
- ✅ 配置验证：endpoint格式、timeout范围检查
- ✅ 默认值处理：headers默认空字典，timeout默认30s

**Phase 1.2 - MCPClient** ✅ COMPLETED (超预期)
- ✅ 连接建立：成功连接到MCP服务器
- ✅ 工具发现：正确解析MCP服务器返回的工具列表
- ✅ 工具调用：同步调用并返回正确结果
- ✅ 错误处理：网络异常、超时、服务器错误处理
- 🚀 **额外实现**: 真正的progress callback streaming

**Phase 1.3 - MCPTool** ✅ COMPLETED (超预期)
- ✅ Tool接口实现：正确实现execute方法
- ✅ 参数转换：ToolRequest到MCP调用参数转换
- ✅ 结果转换：MCP响应到ToolResult转换
- ✅ 异常处理：MCP调用失败时错误信息传递
- 🚀 **额外实现**: execute_stream流式执行支持

**Phase 1.4 - ToolService扩展** ✅ COMPLETED
- ✅ MCP工具注册：_load_mcp_tools()成功加载工具
- ✅ 工具池验证：list_tools()包含MCP工具
- ✅ 工具查找：通过tool_service._tools访问MCP工具
- ✅ 配置驱动：enable_mcp=false时不加载MCP工具

#### Phase 2: 流式功能 ✅ COMPLETED

**Phase 2.1 - ToolStreamChunk** ✅ COMPLETED
- ✅ 数据结构完整：使用现有TaskStreamChunk
- ✅ 序列化支持：完整的数据结构
- ✅ 时间戳生成：自动生成timestamp
- ✅ 类型验证：TaskChunkType枚举值验证

**Phase 2.2 - Tool基类扩展** ✅ COMPLETED
- ✅ 向后兼容：现有Tool实现不受影响
- ✅ 默认实现：MCPTool实现了execute_stream()
- ✅ 流式检测：supports_streaming属性正确返回True
- ✅ AsyncIterator：正确的异步迭代器实现

**Phase 2.3 - MCPTool流式支持** ✅ COMPLETED (超预期)
- ✅ 流式调用：call_tool_stream()正确实现
- ✅ 数据转换：MCP流式响应到TaskStreamChunk转换
- ✅ 流式完整性：is_final标记正确设置
- ✅ 异常处理：流式过程中的错误处理
- 🚀 **真实streaming验证**: 8个chunks，5.13秒，真实时间戳间隔

#### Phase 3: 集成验证 🔄 IN PROGRESS (40% COMPLETED)

**Phase 3.1 - ToolResolver** ❌ NEEDED
- ❌ 名称解析：完整名称和简化名称解析
- ❌ 权限检查：_check_tool_permission()集成
- ❌ 工具查找：支持namespace.tool_name格式
- ❌ 对象转换：Tool到UniversalTool转换

**Phase 3.2 - TaskRequest集成** ❌ NEEDED
- ❌ 工具解析：工具名称列表正确解析为UniversalTool
- ❌ TaskRequest创建：available_tools字段正确填充
- ❌ 权限过滤：无权限工具被正确过滤
- ❌ 错误处理：找不到工具时的处理

**Phase 3.3 - ADK Agent集成** ❌ NEEDED
- ❌ 函数转换：UniversalTool到ADK函数转换
- ❌ 工具调用：ADK Agent成功调用MCP工具
- ❌ 会话管理：session_id正确传递
- ❌ 端到端：从用户工具名称到MCP服务器完整调用链

### 每阶段交付物

| 阶段 | 代码文件 | 测试文件 | 文档 |
|-----|----------|----------|------|
| Phase 1.1 | `tools/mcp/config.py` | `tests/tools/mcp/test_config.py` | 配置示例 |
| Phase 1.2 | `tools/mcp/client.py` | `tests/tools/mcp/test_client.py` | MCP通信文档 |
| Phase 1.3 | `tools/mcp/tool_wrapper.py` | `tests/tools/mcp/test_tool_wrapper.py` | 工具包装说明 |
| Phase 1.4 | 修改`tools/service.py` | `tests/tools/test_service_mcp.py` | 集成配置指南 |
| Phase 2.1 | `contracts/streaming.py` | `tests/contracts/test_streaming.py` | 流式数据格式 |
| Phase 2.2 | 修改`tools/base/tool.py` | `tests/tools/base/test_tool_streaming.py` | 流式工具指南 |
| Phase 2.3 | 更新`tool_wrapper.py` | 更新相关测试 | 流式调用示例 |
| Phase 3.1 | `tools/resolver.py` | `tests/tools/test_resolver.py` | 工具解析规则 |
| Phase 3.2 | 集成层代码 | `tests/integration/test_task_request.py` | 集成使用示例 |
| Phase 3.3 | 修改`agents/adk/` | `tests/e2e/test_mcp_integration.py` | 端到端使用指南 |

## Testing Strategy

- MCPClient connection and tool discovery
- MCPTool synchronous and streaming execution
- ToolResolver tool name resolution
- ToolService integration
- End-to-end tool execution workflow