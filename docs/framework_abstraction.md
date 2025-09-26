# Framework Abstraction Layer Design

## Overview

The Framework Abstraction Layer provides a unified interface for multiple agent frameworks (ADK, AutoGen, LangGraph) while maintaining framework-agnostic execution capabilities. **Current implementation focuses on ADK as the primary framework** with an extensible architecture designed for future multi-framework support through a strategy-based routing approach.

The design follows a **layered contract approach**, starting with ADK-compatible foundation and designed for progressive evolution toward universal framework support.

**Implementation Status:**
- ✅ **ADK Integration Complete**: Full ADK support with session management and agent lifecycle
- ✅ **Unified Data Contracts**: TaskRequest, TaskResult, AgentConfig with session management fields
- ✅ **Framework Registry**: Auto-loading and capability-driven adapter management
- 🚧 **Live Execution**: Basic framework implemented, interactive features in development
- 📋 **Multi-Framework Support**: Architecture ready for AutoGen and LangGraph integration

## Design Goals

- **ADK-First Implementation**: Complete ADK integration with extensibility for future frameworks
- **Session-Based Architecture**: Support persistent multi-turn conversations with agent_id + session_id model
- **Framework Agnostic Contracts**: Unified data structures that work consistently across different frameworks
- **Progressive Abstraction**: Evolution from ADK-specific to universal data contracts without breaking changes
- **Layered Architecture**: Clear separation following the established system architecture layers
- **Contract-Driven Design**: Well-defined data contracts between architectural layers

## Architecture Overview

### Current Implementation Status

Following the established architecture in `docs/architecture.md`, the current implementation provides:

```
1. Application Execution Layer (✅ Complete) → 2. Framework Abstraction Layer (✅ ADK Complete) → 3. Core Agent Layer (✅ Complete) → 4. Tool Service Layer (🚧 Basic)
```

**Current Execution Flow:**
- **AIAssistant** → **ExecutionEngine** → **TaskRouter** → **FrameworkRegistry** → **AdkFrameworkAdapter**
- **AdkFrameworkAdapter** → **AgentManager** + **RunnerManager** → **AdkDomainAgent** → **ADK Runtime**

**Design Philosophy**: 
- **ADK-First Implementation**: Start with ADK-native integration, maintain extensible architecture
- **Session Management**: agent_id + session_id architecture for persistent conversations
- **Contract-First**: Define data contracts between layers, implement with ADK optimization

### Type System Overview (Current Implementation)

The framework abstraction uses a hierarchical type system with ADK-optimized contracts and clear dependency relationships:

```
Core Request/Response Flow (Current):
TaskRequest → ExecutionEngine → AdkFrameworkAdapter → AgentRequest → ADK Runtime
    ↓              ↓                   ↓              ↓           ↓
TaskResult  ← ExecutionStrategy ← AdkDomainAgent ← AgentResponse ← ADK Response

Session Management Flow (Current):
TaskRequest (agent_id/session_id/agent_config) → AdkFrameworkAdapter
    ↓
Three Execution Modes:
├── agent_id + session_id → Continue existing session
├── agent_id only → Create new session for existing agent  
└── agent_config only → Create new agent and session

Primary Data Types (Implemented):
├── TaskRequest ✅
│   ├── Core fields: task_id, task_type, description
│   ├── Session management: agent_id, session_id, agent_config
│   ├── Message context: messages (UniversalMessage)
│   ├── Execution context: user_context, session_context
│   └── Tool integration: available_tools, available_knowledge
│
├── TaskResult ✅  
│   ├── Core fields: task_id, status, messages
│   ├── Session management: agent_id, session_id (for follow-up)
│   ├── Execution data: result_data, execution_time
│   └── Framework metadata: metadata with framework info
│
├── AgentConfig ✅
│   ├── Agent definition: agent_id, agent_type
│   ├── Model config: model, temperature, max_tokens
│   ├── Framework binding: framework_type (ADK)
│   └── System prompt: system_instruction
│
├── AgentRequest ✅ (Domain Agent Input)
│   ├── Agent context: agent_type, framework_type
│   ├── Task context: task_request
│   ├── Session binding: session_id
│   └── Runtime context: runtime_options
│
└── ExecutionStrategy ✅ (Router Output)
    ├── Framework selection: framework_type (currently ADK)
    ├── Complexity analysis: task_complexity
    ├── Runtime options: execution_config, runtime_options
    └── Execution mode: execution_mode
```

## Data Contracts (Current Implementation)

### Core Request/Response Contracts

#### TaskRequest (Application Layer Input) - ✅ Implemented
```python
@dataclass
class TaskRequest:
    # Core identification
    task_id: str  # Unique identifier for task tracking
    task_type: str  # Task category for routing (e.g., "chat", "analysis") 
    description: str  # Task description
    
    # Session management (NEW: Three execution modes)
    agent_id: Optional[str] = None  # Continue with existing agent
    session_id: Optional[str] = None  # Continue existing session
    agent_config: Optional[AgentConfig] = None  # Create new agent
    
    # Message and context
    messages: List[UniversalMessage] = field(default_factory=list)
    user_context: Optional[UserContext] = None
    session_context: Optional[SessionContext] = None
    execution_context: Optional[ExecutionContext] = None
    
    # Tool and knowledge integration
    available_tools: List[UniversalTool] = field(default_factory=list)
    available_knowledge: List[KnowledgeSource] = field(default_factory=list)
    execution_config: Optional[ExecutionConfig] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### TaskResult (Application Layer Output) - ✅ Implemented
```python
@dataclass 
class TaskResult:
    # Core fields
    task_id: str  # Matching task identifier
    status: TaskStatus  # SUCCESS, ERROR, PARTIAL, TIMEOUT, CANCELLED
    
    # Response content
    messages: List[UniversalMessage] = field(default_factory=list)
    result_data: Optional[Dict[str, Any]] = None
    tool_results: List[ToolResult] = field(default_factory=list)
    
    # Session management (NEW: For follow-up requests)
    agent_id: Optional[str] = None  # Agent ID for continued conversation
    session_id: Optional[str] = None  # Session ID for multi-turn chat
    
    # Execution metadata
    execution_context: Optional[ExecutionContext] = None
    execution_time: Optional[float] = None
    created_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### AgentConfig (Agent Creation) - ✅ Implemented
```python
@dataclass
class AgentConfig:
    # Agent identification
    agent_id: str  # Unique agent identifier
    agent_type: str  # Agent type (e.g., "adk_domain_agent")
    framework_type: FrameworkType  # Target framework (currently ADK)
    
    # Agent configuration
    name: str  # Human-readable agent name
    model: str  # LLM model to use (e.g., "gemini-1.5-flash", "deepseek-chat")
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    system_instruction: Optional[str] = None  # System prompt
    
    # Tool integration
    tools: List[UniversalTool] = field(default_factory=list)
    
    # Framework-specific configuration
    adk_config: Optional[AdkAgentConfig] = None  # ADK-specific settings
```

#### ExecutionStrategy (Router Output) - ✅ Implemented
```python
@dataclass
class ExecutionStrategy:
    # Framework selection (currently always ADK)
    framework_type: FrameworkType  # Selected framework
    task_complexity: TaskComplexity  # SIMPLE, MODERATE, COMPLEX, ADVANCED
    
    # Execution configuration
    execution_mode: str = "async"  # Execution mode
    execution_config: Dict[str, Any]  # Framework-specific config
    runtime_options: Dict[str, Any]  # Runtime parameters
    
    # Routing metadata
    framework_score: float = 1.0  # Framework selection confidence
    fallback_frameworks: List[FrameworkType] = field(default_factory=list)
```

### Supporting Data Structures

#### Live Execution and Streaming Contracts

##### TaskStreamChunk (Real-time Event Streaming)
```python
@dataclass
class TaskStreamChunk:
    """Streaming execution block for real-time task processing."""
    task_id: str  # Task identifier for event correlation
    chunk_type: TaskChunkType  # Event type: RESPONSE, PROGRESS, TOOL_CALL_REQUEST, ERROR, etc.
    sequence_id: int  # Sequential ordering for event stream
    content: Union[str, Dict[str, Any]]  # Event content (text or structured data)
    timestamp: datetime = field(default_factory=datetime.now)
    is_final: bool = False  # Indicates final event in stream
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional event metadata
```

##### InteractionResponse (User Feedback)
```python
@dataclass
class InteractionResponse:
    """User response to an interaction request during live execution."""
    interaction_id: str  # Unique identifier for interaction tracking
    interaction_type: InteractionType  # Type of interaction: TOOL_APPROVAL, USER_INPUT, etc.
    approved: bool  # User's approval decision
    response_data: Optional[Dict[str, Any]] = None  # Additional response data
    user_message: Optional[str] = None  # Optional user message
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
```

##### InteractionRequest (System Interaction Requests)
```python
@dataclass
class InteractionRequest:
    """Request for user interaction during task execution."""
    interaction_id: str  # Unique identifier for tracking
    interaction_type: InteractionType  # Type of interaction needed
    task_id: str  # Associated task identifier
    content: Union[str, Dict[str, Any]]  # Interaction content or prompt
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
```

##### Type Aliases for Live Execution
```python
# Type aliases for better readability
LiveSession = AsyncIterator[TaskStreamChunk]  # Event stream type
LiveExecutionResult = tuple[LiveSession, "LiveCommunicator"]  # Complete live result
```

#### User and Session Management
```python
@dataclass
class UserContext:
    """Flexible user identification supporting different frameworks"""
    user_id: Optional[str] = None  # Explicit user identifier (ADK required)
    user_name: Optional[str] = None  # Human-readable username
    session_token: Optional[str] = None  # Session-based identification
    permissions: Optional[UserPermissions] = None  # User access permissions
    preferences: Optional[UserPreferences] = None  # User preference settings
    
    def get_adk_user_id(self) -> str:
        """Get or generate user_id for ADK compatibility"""
        pass

@dataclass
class SessionContext:
    """Unified session management across frameworks"""
    session_id: Optional[str] = None  # ADK-compatible session identifier
    conversation_id: Optional[str] = None  # Alternative session tracking ID
    conversation_history: List[UniversalMessage] = field(default_factory=list)
    session_state: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    def get_adk_session_id(self) -> Optional[str]:
        """Get ADK-compatible session_id"""
        pass
```

#### Message and Content
```python
@dataclass
class UniversalMessage:
    """Framework-agnostic message format with ADK compatibility"""
    role: str  # Message role: "user", "assistant", "system", "tool"
    content: Union[str, List[ContentPart]]  # Message content (text or multi-modal)
    author: Optional[str] = None  # ADK uses 'author' instead of 'role'
    name: Optional[str] = None    # AutoGen agent name identifier
    tool_calls: Optional[List[ToolCall]] = None  # Tool invocation requests
    
    def to_adk_format(self) -> Dict[str, Any]:
        """Convert to ADK native format"""
        pass

@dataclass
class ContentPart:
    """Multi-modal content part compatible with ADK parts structure"""
    text: Optional[str] = None
    function_call: Optional[ToolCall] = None
    file_reference: Optional[FileReference] = None
    image_reference: Optional[ImageReference] = None
```

#### Configuration and Metadata
```python
@dataclass
class ExecutionConfig:
    """Unified execution configuration combining runtime and framework settings"""
    timeout: Optional[int] = None
    max_retries: int = 3
    streaming: bool = False
    parallel_execution: bool = False
    preferred_framework: Optional[FrameworkType] = None
    framework_settings: Dict[str, Any] = field(default_factory=dict)
    enable_tracing: bool = True
    enable_metrics: bool = True
    log_level: str = "INFO"

@dataclass
class AgentConfig:
    """Framework-adaptable agent configuration"""
    agent_id: str
    agent_type: str
    framework_type: FrameworkType
    name: str
    model: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: List[UniversalTool] = field(default_factory=list)
    system_instruction: Optional[str] = None
    adk_config: Optional[AdkAgentConfig] = None

@dataclass
class StrategyConfig:
    """Strategy configuration for framework selection"""
    strategy_name: str
    applicable_task_types: List[str]
    complexity_levels: List[TaskComplexity]
    execution_modes: List[ExecutionMode]
    target_framework: FrameworkType
    priority: int
    description: Optional[str] = None
```

#### Tool Definitions
```python
@dataclass
class ToolDefinition:
    """Tool definition with schema and metadata"""
    name: str  # Tool identifier (may include namespace prefix)
    description: str  # Tool functionality description
    parameters_schema: Dict[str, Any]  # JSON Schema for tool parameters
    supports_streaming: bool = False  # Whether tool supports streaming execution
    required_permissions: Optional[List[str]] = None  # Required user permissions

@dataclass
class ToolStreamChunk:
    """Streaming tool execution chunk"""
    tool_name: str  # Tool identifier
    chunk_type: str  # Chunk type: "data", "progress", "error", "complete"
    content: Union[str, Dict[str, Any]]  # Chunk content
    is_final: bool = False  # Whether this is the final chunk

@dataclass
class MCPServerConfig:
    """MCP server connection configuration"""
    name: str  # Server identifier (used for namespacing)
    endpoint: str  # Server endpoint URL
    transport_type: str = "http"  # Transport: "http", "websocket", "stdio"
    connection_timeout: int = 30  # Connection timeout in seconds
```

#### Enumerations
```python
@dataclass
class TaskStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

@dataclass
class ToolStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"

@dataclass
class FrameworkType(Enum):
    ADK = "adk"
    AUTOGEN = "autogen"
    LANGGRAPH = "langgraph"

@dataclass
class TaskComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    ADVANCED = "advanced"

@dataclass
class ExecutionMode(Enum):
    SYNC = "sync"
    ASYNC = "async"
    STREAMING = "streaming"
    BATCH = "batch"

@dataclass
class AgentStatus(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    IDLE = "idle"
    ERROR = "error"
    CLEANUP = "cleanup"
    TERMINATED = "terminated"

@dataclass
class TaskChunkType(Enum):
    """Types of streaming execution events"""
    PROCESSING = "processing"  # Task processing started
    TOOL_CALL_REQUEST = "tool_call_request"  # Agent requests tool execution
    TOOL_APPROVAL_REQUEST = "tool_approval_request"  # User approval needed for tool
    USER_INPUT_REQUEST = "user_input_request"  # Agent requests user input
    RESPONSE = "response"  # Agent response (final or partial)
    PROGRESS = "progress"  # Intermediate progress update
    COMPLETE = "complete"  # Task completion
    ERROR = "error"  # Error occurred
    CANCELLED = "cancelled"  # Task was cancelled

@dataclass
class InteractionType(Enum):
    """Types of user interactions during live execution"""
    TOOL_APPROVAL = "tool_approval"  # Approve/deny tool execution
    USER_INPUT = "user_input"  # Provide requested input
    CONFIRMATION = "confirmation"  # Confirm action
    SELECTION = "selection"  # Select from options
```

## Layer Interface Design

### Layer Dependencies Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          Application Execution Layer                             │
│  AIAssistant ──→ ExecutionEngine ──→ TaskRouter ──→ FrameworkRegistry           │
│       │               │                    │              │                     │
│       │               └────────────────────┴──────────────┴─→ FrameworkAdapter │
└───────┼─────────────────────────────────────────────────────────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────────────────────┐
│                        Framework Abstraction Layer                             │
│                    FrameworkAdapter ──→ AgentManager                           │
└─────────────────────────────────────────────┼───────────────────────────────────┘
                                              │
┌─────────────────────────────────────────────▼───────────────────────────────────┐
│                           Core Agent Layer                                     │
│      AgentManager ──→ DomainAgent ──→ AgentHooks                               │
│           │               │              │                                     │
│           └───────────────┴──────────────┴──→ Tool Service Layer               │
└─────────────────────────────────────────────┼───────────────────────────────────┘
                                              │
┌─────────────────────────────────────────────▼───────────────────────────────────┐
│                         Tool Service Layer                                     │
│  ToolService ──→ Tool ──→ MCPClientManager ──→ MCPClient                       │
│       │         │                                                             │
│       │         ├──→ MCPTool                                                  │
│       │         ├──→ ADKNativeTool                                            │
│       │         ├──→ ExternalAPITool                                          │
│       │         └──→ BuiltinTool                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Inter-Layer Dependencies

#### 1. Application Execution Layer → Framework Abstraction Layer
- **AIAssistant** creates **ExecutionContext** and delegates to **ExecutionEngine**
- **ExecutionEngine** uses **TaskRouter** for strategy selection
- **ExecutionEngine** retrieves **FrameworkAdapter** from **FrameworkRegistry**
- **ExecutionEngine** delegates task execution to selected **FrameworkAdapter**

#### 2. Framework Abstraction Layer → Core Agent Layer  
- **FrameworkAdapter** creates **DomainAgent** instances directly for task execution
- **FrameworkAdapter** manages agent lifecycle (creation, execution, cleanup) internally  
- **FrameworkAdapter** converts TaskRequest/TaskResult to/from framework-specific formats
- **AgentManager** provides optional session-based agent lifecycle management for persistent sessions

#### 3. Core Agent Layer → Tool Service Layer
- **AgentManager** provides **DomainAgent** instances with access to **ToolService**
- **DomainAgent** makes tool execution requests through **ToolService**
- **AgentHooks** may integrate with **ToolService** for framework-specific tool handling

#### 4. Tool Service Layer Internal Dependencies
- **ToolService** manages multiple **Tool** implementations
- **ToolService** uses **MCPClientManager** for MCP tool discovery and execution
- **MCPClientManager** maintains connections to multiple **MCPClient** instances
- Each **Tool** subclass implements specific execution patterns

### Intra-Layer Dependencies

#### Application Execution Layer Internal Flow
```
AIAssistant → ExecutionEngine → TaskRouter → StrategyConfig
     ↓              ↓               ↓            ↓
ExecutionContext ←─ FrameworkRegistry ←─ Framework Selection
     ↓              ↓
TaskResult ←─ FrameworkAdapter (selected based on strategy)
```

#### Framework Abstraction Layer Internal Flow  
```
FrameworkAdapter → AgentManager → DomainAgent Factory
     ↓                 ↓              ↓
Task Validation → Agent Creation → Framework-Specific Agent
     ↓                 ↓              ↓  
Framework Format ← Agent Execution ← Agent Configuration
```

#### Core Agent Layer Internal Flow
```
AgentManager → Agent Factory → DomainAgent → AgentHooks
     ↓             ↓             ↓            ↓
Agent Cache → Agent Instance → Processing Flow → Framework Extensions
     ↓             ↓             ↓            ↓
Lifecycle Mgmt ← Agent Response ← Hook Points ← Custom Behaviors
```

#### Tool Service Layer Internal Flow
```
ToolService → Tool Discovery → Tool Registry → Tool Execution
     ↓            ↓               ↓             ↓
Permission Check → MCPClientManager → Tool Instance → Result Processing
     ↓            ↓               ↓             ↓
Access Control ← Namespace Routing ← Tool Types ← Response Format
                 ↓
                 MCPClient → MCP Server
```

### Dependency Injection Pattern

#### Constructor Dependencies (Required)
- **AIAssistant(ExecutionEngine)**: Requires execution engine for task delegation
- **ExecutionEngine(TaskRouter, FrameworkRegistry)**: Requires routing and registry services
- **TaskRouter(List[StrategyConfig])**: Requires strategy configurations for routing decisions
- **DomainAgent(agent_id, AgentConfig)**: Requires identity and configuration for initialization

#### Runtime Dependencies (Injected)
- **DomainAgent.set_hooks(AgentHooks)**: Framework-specific hooks injected at runtime
- **AgentManager.register_agent_factory()**: Framework factories registered during setup
- **ToolService.register_tool()**: Tools registered during service initialization
- **FrameworkRegistry.register_adapter()**: Adapters registered during system startup

### Lifecycle Dependencies

#### Initialization Order
1. **Tool Service Layer**: Initialize ToolService, discover and register tools
2. **Core Agent Layer**: Set up AgentManager, register agent factories  
3. **Framework Abstraction Layer**: Create FrameworkAdapters, register with registry
4. **Application Execution Layer**: Initialize TaskRouter with strategies, create ExecutionEngine

#### Runtime Execution Flow
1. **Request Entry**: AIAssistant receives TaskRequest
2. **Strategy Selection**: TaskRouter analyzes and selects execution strategy
3. **Framework Routing**: ExecutionEngine routes to appropriate FrameworkAdapter
4. **Agent Coordination**: FrameworkAdapter uses AgentManager for agent operations
5. **Tool Integration**: DomainAgent accesses ToolService for tool execution
6. **Response Assembly**: Results flow back through layers to TaskResult

### 1. Application Execution Layer

#### AIAssistant Interface
```python
class AIAssistant:
    """
    System entry point that serves as the primary interface for all task requests.
    
    Core Capabilities:
    - Request validation and preprocessing
    - ExecutionContext creation and management
    - High-level task coordination through ExecutionEngine
    - Response formatting and error handling
    - System-wide monitoring and logging integration
    
    Dependencies:
    - ExecutionEngine: Delegates all task execution operations
    
    Why it exists: Provides a clean, stable API facade that shields clients from
    internal system complexity while ensuring consistent request/response handling
    across all supported frameworks and execution modes.
    """
    
    def __init__(self, execution_engine: 'ExecutionEngine'):
        """Initialize with execution engine dependency"""
        pass
    
    async def process_request(self, task: TaskRequest) -> TaskResult:
        """Process incoming task request and coordinate execution"""
        pass
```

#### ExecutionEngine Interface
```python
class ExecutionEngine:
    """
    Central orchestration hub that coordinates strategy selection and framework execution.
    
    Core Capabilities:
    - Strategy-based framework routing via TaskRouter
    - Framework adapter lifecycle management
    - Cross-framework execution coordination
    - Performance monitoring and execution metrics
    - Error handling and recovery strategies
    - Execution context management
    - Live execution support with real-time interaction management
    
    Dependencies:
    - TaskRouter: Analyzes tasks and selects execution strategies
    - FrameworkRegistry: Provides access to framework adapters
    - FrameworkAdapter: Executes tasks using framework-specific logic
    
    Why it exists: Serves as the intelligent execution coordinator that abstracts
    multi-framework complexity while providing unified execution semantics,
    enabling optimal framework selection and consistent execution behavior.
    """
    
    def __init__(self, task_router: 'TaskRouter', framework_registry: 'FrameworkRegistry'):
        """Initialize with task router and framework registry dependencies"""
        pass
    
    async def execute_task(self, task: TaskRequest, context: ExecutionContext) -> TaskResult:
        """Execute task using strategy-based framework selection"""
        pass
    
    async def execute_task_live(
        self, task: TaskRequest, context: ExecutionContext
    ) -> LiveExecutionResult:
        """
        Execute task in live/interactive mode with real-time bidirectional
        communication through framework-agnostic routing.
        """
        pass
    
    def register_framework_adapter(self, framework_type: FrameworkType, adapter: 'FrameworkAdapter') -> None:
        """Register framework adapter in registry"""
        pass
```

#### TaskRouter Interface
```python
class TaskRouter:
    """
    Intelligent decision engine that analyzes tasks and selects optimal execution strategies.
    
    Core Capabilities:
    - Task complexity analysis and classification
    - Strategy matching based on task characteristics and requirements
    - Dynamic strategy registration and priority management
    - Performance-based strategy optimization over time
    - Multi-criteria decision making with conflict resolution
    
    Dependencies:
    - StrategyConfig: Configuration objects defining execution strategies
    - TaskRequest: Input for strategy analysis
    - ExecutionContext: Additional context for strategy decisions
    
    Why it exists: Eliminates manual framework selection by providing intelligent,
    automated routing that considers task complexity, resource requirements, and
    framework capabilities to optimize execution performance and resource utilization.
    """
    
    def __init__(self, available_strategies: List[StrategyConfig]):
        """Initialize with available strategy configurations"""
        pass
    
    async def select_strategy(self, task: TaskRequest, context: ExecutionContext) -> StrategyConfig:
        """Analyze task and select appropriate execution strategy"""
        pass
    
    def register_strategy(self, strategy_config: StrategyConfig) -> None:
        """Register new strategy configuration"""
        pass
```

### 2. Framework Abstraction Layer

#### Live Communication Protocol

##### LiveCommunicator Interface
```python
class LiveCommunicator(Protocol):
    """
    Protocol for bidirectional communication during live execution.
    
    Enables real-time interaction between executing agent and client during
    interactive workflows such as tool approval, user input requests, and
    session management.
    """
    
    async def send_user_response(self, response: InteractionResponse) -> None:
        """Send user response to interaction request"""
        pass
    
    async def send_cancellation(self, reason: str = "user_cancelled") -> None:
        """Send cancellation signal to stop execution"""
        pass
    
    async def send_user_message(self, message: str) -> None:
        """Send regular user message during live session"""
        pass
    
    def close(self) -> None:
        """Close communication channel and cleanup resources"""
        pass
```

#### FrameworkRegistry Interface
```python
class FrameworkRegistry:
    """
    Centralized registry that manages all framework adapter instances and their lifecycle.
    
    Core Capabilities:
    - Framework adapter registration and discovery
    - Adapter instance lifecycle management (creation, health monitoring, cleanup)
    - Framework capability enumeration and reporting
    - Dynamic framework registration at runtime
    - Adapter health monitoring and automatic recovery
    
    Dependencies:
    - FrameworkAdapter: Manages instances of framework-specific adapters
    - FrameworkType: Uses enum to identify and categorize frameworks
    
    Why it exists: Provides centralized framework management that enables dynamic
    framework registration, health monitoring, and clean abstraction between
    framework selection logic and adapter implementation details.
    """
    
    def register_adapter(self, framework_type: FrameworkType, adapter: FrameworkAdapter) -> None:
        """Register framework adapter instance"""
        pass
    
    def get_adapter(self, framework_type: FrameworkType) -> FrameworkAdapter:
        """Get registered adapter for framework type"""
        pass
    
    def list_available_frameworks(self) -> List[FrameworkType]:
        """List all registered framework types"""
        pass
```

#### FrameworkAdapter Interface
```python
class FrameworkAdapter(ABC):
    """
    Abstract bridge that encapsulates framework-specific execution logic and provides
    unified task execution interface regardless of underlying framework implementation.
    
    Core Capabilities:
    - Framework-native task execution coordination (ADK, AutoGen, LangGraph patterns)
    - Bidirectional data conversion (universal ↔ framework-specific formats)
    - Framework-specific error handling, recovery, and timeout management
    - Agent lifecycle delegation through framework-optimized AgentManager
    - Framework capability reporting and task compatibility validation
    - Performance monitoring and framework-specific optimization
    - Live execution support with real-time bidirectional communication
    
    Dependencies:
    - AgentManager: Delegates agent lifecycle operations to framework-optimized manager
    - TaskRequest/TaskResult: Converts between universal and framework-specific formats
    - ExecutionContext: Uses context for framework-specific execution decisions
    
    Why it exists: Enables seamless integration of heterogeneous agent frameworks
    by abstracting framework-specific implementation details while preserving each
    framework's unique execution patterns, allowing the system to leverage different
    frameworks' strengths without tight coupling.
    """
    
    @abstractmethod
    def get_framework_type(self) -> FrameworkType:
        """Return the framework type this adapter supports"""
        pass
    
    @abstractmethod
    async def execute_task(self, task: TaskRequest, context: ExecutionContext) -> TaskResult:
        """Execute complete task using framework-specific coordination"""
        pass
    
    @abstractmethod
    async def execute_task_live(
        self, task: TaskRequest, context: ExecutionContext
    ) -> LiveExecutionResult:
        """
        Execute task in live/interactive mode with real-time bidirectional communication.
        
        Returns tuple of (event_stream, communicator) where:
        - event_stream: AsyncIterator[TaskStreamChunk] for real-time events
        - communicator: LiveCommunicator for bidirectional communication
        """
        pass
    
    def supports_live_execution(self) -> bool:
        """Check if framework supports live/interactive execution mode"""
        return hasattr(self, "execute_task_live") and callable(
            getattr(self, "execute_task_live")
        )
    
    @abstractmethod
    def get_agent_manager(self) -> 'AgentManager':
        """Get framework-optimized agent manager for agent lifecycle operations"""
        pass
    
    @abstractmethod
    async def validate_task(self, task: TaskRequest) -> bool:
        """Validate if task can be executed by this framework"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return framework capabilities and limitations"""
        pass
```

### 3. Core Agent Layer

#### AgentManager Interface
```python
class AgentManager:
    """
    Session-based agent lifecycle coordinator that manages persistent agent instances
    for multi-turn conversations and long-running tasks.
    
    Core Capabilities:
    - Session-based agent lifecycle management with automatic cleanup
    - Long-lived agent instances for persistent conversations
    - Agent resource tracking and session health monitoring
    - Factory registration for framework-specific agent creation
    - Expired session cleanup and resource management
    
    Dependencies:
    - DomainAgent: Manages framework-specific agent instances
    - AgentConfig: Uses configuration for session agent creation
    - FrameworkType: Routes to appropriate agent factories for sessions
    
    Why it exists: Provides session-aware agent management for scenarios requiring
    persistent agent state across multiple task executions, while keeping the
    primary execution path (single-task agents) simple and direct through
    FrameworkAdapter direct creation.
    """
    
    async def get_or_create_session_agent(
        self, session_id: str, agent_factory: Callable, agent_config: AgentConfig
    ) -> DomainAgent:
        """Get existing session agent or create new one using provided factory"""
        pass
    
    async def cleanup_session(self, session_id: str) -> bool:
        """Clean up all resources for a session"""
        pass
    
    async def cleanup_expired_sessions(self, max_idle_time: timedelta) -> List[str]:
        """Clean up sessions that have been idle for too long"""
        pass
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of the agent manager"""
        pass
```

#### DomainAgent Interface
```python
class DomainAgent(ABC):
    """
    Abstract base for framework-specific agent implementations that provides unified
    agent behavior while supporting framework-specific extensions through hooks.
    
    Core Capabilities:
    - Framework-specific agent logic implementation (ADK, AutoGen, LangGraph)
    - Unified request processing flow with framework-agnostic interface
    - Hook-based extension system for framework-specific behaviors
    - Agent capability reporting and introspection
    - Resource management and cleanup with proper lifecycle handling
    
    Dependencies:
    - AgentHooks: Uses framework-specific hooks for pre/post processing
    - AgentRequest/AgentResponse: Processes standardized agent communication
    - AgentConfig: Uses configuration for agent initialization and behavior
    - ToolService: Integrates with tool layer for tool execution
    
    Why it exists: Provides a consistent agent interface that allows framework-specific
    implementations to plug into the unified system while maintaining their unique
    capabilities and execution patterns through the extensible hook system.
    """
    
    def __init__(self, agent_id: str, agent_config: AgentConfig):
        """Initialize domain agent with ID and configuration"""
        pass
    
    def set_hooks(self, hooks: 'AgentHooks'):
        """Inject framework-specific hooks implementation"""
        pass
    
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Unified processing flow with hook points"""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize agent resources and dependencies"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> bool:
        """Clean up agent resources and connections"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return agent capabilities and supported operations"""
        pass
```

#### AgentHooks Interface
```python
class AgentHooks:
    """
    Extension point system that enables framework-specific customizations to be
    injected into the unified agent processing flow.
    
    Core Capabilities:
    - Pre-processing hooks for request transformation and validation
    - Post-processing hooks for response enhancement and formatting
    - Error handling hooks for framework-specific error recovery
    - Framework-specific state management and context handling
    - Custom logging and monitoring integration points
    
    Dependencies:
    - AgentRequest/AgentResponse: Processes and transforms agent communication
    - Framework-specific components: Integrates with ADK, AutoGen, LangGraph specifics
    
    Why it exists: Enables framework-specific behaviors and optimizations to be
    cleanly integrated into the unified agent processing flow without compromising
    the framework-agnostic interface, allowing each framework to leverage its
    unique capabilities while maintaining system consistency.
    """
    
    async def pre_process(self, request: AgentRequest) -> AgentRequest:
        """Pre-processing hook - can modify request before core processing"""
        pass
    
    async def post_process(self, response: AgentResponse) -> AgentResponse:
        """Post-processing hook - can modify response after core processing"""
        pass
    
    async def on_error(self, error: Exception, request: AgentRequest) -> Optional[AgentResponse]:
        """Error handling hook - can provide fallback response"""
        pass
```

### 4. Tool Service Layer

#### ToolService Interface
```python
class ToolService:
    """
    Unified tool execution service that manages all tool types and provides both
    external API for agents and internal management capabilities.
    
    Core Capabilities:
    - Multi-type tool execution (MCP, ADK Native, External API, Builtin)
    - Permission-based access control with user context validation
    - Synchronous and streaming tool execution patterns
    - Auto-discovery and registration of tools from various sources
    - Tool lifecycle management (registration, discovery, cleanup)
    - Performance monitoring and execution metrics
    
    Dependencies:
    - Tool: Manages concrete tool implementations (MCPTool, ADKNativeTool, etc.)
    - MCPClientManager: Handles MCP server connections and tool discovery
    - ToolRequest/ToolResult: Processes tool communication protocols
    - ExecutionContext: Uses context for tool availability and permissions
    
    Why it exists: Provides a unified interface for all tool interactions while
    abstracting the complexity of different tool types, enabling agents to use
    tools consistently regardless of their underlying implementation or protocol.
    """
    
    # External API methods (for agents)
    async def execute_tool(self, request: ToolRequest) -> ToolResult:
        """Execute tool and return result with permission validation"""
        pass
    
    async def execute_tool_stream(self, request: ToolRequest) -> AsyncIterator[ToolStreamChunk]:
        """Execute tool with streaming response"""
        pass
    
    async def list_available_tools(self, context: ExecutionContext) -> List[ToolDefinition]:
        """List all available tools for the given execution context"""
        pass
    
    # Internal management methods
    async def register_tool(self, name: str, tool: Tool) -> bool:
        """Register tool implementation with the service"""
        pass
    
    async def discover_tools(self) -> None:
        """Auto-discovery of tools from various sources"""
        pass
    
    async def initialize(self) -> None:
        """Initialize tool service and discover all available tools"""
        pass
```

#### Tool Abstract Interface
```python
class Tool(ABC):
    """
    Abstract base class that defines the contract for all tool implementations,
    enabling polymorphic tool execution across different tool types.
    
    Core Capabilities:
    - Synchronous tool execution with complete result return
    - Streaming tool execution for long-running operations
    - Tool definition and schema introspection
    - Framework-agnostic execution interface
    - Error handling and status reporting
    
    Dependencies:
    - ToolRequest/ToolResult: Standard tool communication protocols
    - ToolStreamChunk: Streaming execution data format
    - ToolDefinition: Tool metadata and schema information
    
    Why it exists: Provides a unified interface that allows different tool types
    (MCP, ADK Native, External API, Builtin) to be used interchangeably by agents
    and the tool service, enabling polymorphic tool execution and consistent
    tool management regardless of underlying implementation.
    """
    
    @abstractmethod
    async def execute(self, request: ToolRequest) -> ToolResult:
        """Execute tool synchronously and return complete result"""
        pass
    
    @abstractmethod
    async def execute_stream(self, request: ToolRequest) -> AsyncIterator[ToolStreamChunk]:
        """Execute tool with streaming response"""
        pass
    
    @abstractmethod
    async def get_definition(self) -> ToolDefinition:
        """Get tool definition including schema and metadata"""
        pass
```

#### MCPClientManager Interface
```python
class MCPClientManager:
    """
    Specialized manager for Model Context Protocol (MCP) server connections that
    handles multiple MCP servers with namespace-aware tool discovery and execution.
    
    Core Capabilities:
    - Multi-server MCP connection management with health monitoring
    - Namespace-aware tool discovery (server_name:tool_name format)
    - Connection pooling and automatic reconnection handling
    - Tool routing based on namespace prefixes
    - Streaming execution support via application/x-ndjson protocol
    
    Dependencies:
    - MCPClient: Individual client connections to MCP servers
    - MCPServerConfig: Configuration for MCP server connections
    - ToolDefinition: MCP tool metadata with namespace information
    
    Why it exists: Enables integration with multiple MCP servers simultaneously
    while providing namespace isolation and unified tool discovery, allowing
    agents to access MCP tools from different providers without naming conflicts
    or connection complexity.
    """
    
    async def initialize(self) -> None:
        """Initialize connections to all configured MCP servers"""
        pass
    
    async def discover_all_tools(self) -> List[ToolDefinition]:
        """Discover tools from all connected MCP servers with namespace prefixes"""
        pass
    
    def get_client(self, server_name: str) -> MCPClient:
        """Get MCP client for specific server"""
        pass
    
    async def execute_tool(self, namespaced_tool_name: str, parameters: Dict[str, Any]) -> Any:
        """Execute tool on appropriate MCP server using namespace routing"""
        pass
```

#### Tool Implementation Types
```python
class MCPTool(Tool):
    """
    Model Context Protocol tool implementation that provides streaming HTTP-based
    tool execution through MCP server connections.
    
    Core Capabilities:
    - Streamable HTTP execution using application/x-ndjson protocol
    - Namespace-aware tool routing through MCPClientManager
    - Real-time streaming response handling
    - MCP server connection management and error recovery
    
    Dependencies:
    - MCPClientManager: Routes execution to appropriate MCP server
    - MCPClient: Handles actual MCP protocol communication
    
    Why it exists: Enables integration with MCP-based tools that support
    streaming execution, providing real-time tool interaction capabilities.
    """
    pass

class ADKNativeTool(Tool):
    """
    ADK framework native tool implementation that directly integrates with
    ADK's built-in tool system and execution patterns.
    
    Core Capabilities:
    - Direct ADK tool system integration
    - ADK-native data format handling
    - Framework-optimized execution paths
    - ADK-specific error handling and recovery
    
    Dependencies:
    - ADK Runtime: Direct integration with ADK tool execution system
    - ADK Tool Instance: Wraps existing ADK tool implementations
    
    Why it exists: Provides optimal performance integration with ADK framework
    tools while maintaining compatibility with the unified tool interface.
    """
    pass

class ExternalAPITool(Tool):
    """
    External API tool implementation that wraps REST/GraphQL APIs as tools
    with proper authentication and error handling.
    
    Core Capabilities:
    - RESTful and GraphQL API integration
    - Authentication handling (API keys, OAuth, etc.)
    - HTTP client management with connection pooling
    - API response transformation to tool result format
    
    Dependencies:
    - HTTP Client: Manages external API connections
    - API Configuration: Authentication and endpoint configuration
    
    Why it exists: Enables integration with external services and APIs as
    tools, expanding the tool ecosystem beyond framework-specific capabilities.
    """
    pass

class BuiltinTool(Tool):
    """
    Built-in tool implementation for system-level functions and utilities
    that don't require external dependencies or complex setup.
    
    Core Capabilities:
    - System utility functions (file operations, data processing)
    - Mathematical and text processing operations
    - Simple integration functions and helpers
    - Direct Python function wrapping
    
    Dependencies:
    - Python Runtime: Direct function execution
    - System Resources: File system, environment access
    
    Why it exists: Provides essential utility functions and system operations
    that agents commonly need without requiring external tool providers.
    """
    pass
```

## Key Design Decisions

### 1. Contract-First Design
- Define layer contracts before implementing interfaces
- Ensure data compatibility across framework boundaries
- Enable independent layer development and testing

### 2. ADK-Compatible Foundation
- Start with ADK-native structures for immediate compatibility
- Progressive abstraction maintains backward compatibility  
- Minimize conversion costs for primary runtime
- **Flexible User Identification**: Support multiple user identification methods while ensuring ADK compatibility
- **Unified Session Management**: Single session context adaptable to different framework requirements

### 3. Universal Data Structures
- Single message format adaptable to all frameworks
- Framework-specific fields as optional extensions
- Built-in conversion methods for framework adaptation

### 4. Strategy-Based Framework Selection
- Configuration-driven framework routing
- Task characteristics determine optimal framework
- Support for delegation to framework-native implementations

### 5. Unified Tool Service Architecture
- Single ToolService interface handles both management and execution
- Framework-agnostic tool execution with support for multiple tool types
- MCP integration with namespace-aware multi-server support
- Streaming execution capabilities through AsyncIterator pattern

### 6. Live Execution Architecture
- **Framework-Agnostic Streaming**: Live execution capabilities exposed through unified interfaces
- **Bidirectional Communication**: Real-time event streaming with user interaction support  
- **Event Standardization**: ADK events converted to unified TaskStreamChunk format for consistency
- **Interactive Workflow Support**: Built-in patterns for tool approval, user input, and cancellation
- **Protocol Abstraction**: LiveCommunicator protocol enables framework-specific implementations
- **Session Lifecycle**: Proper management of long-running interactive sessions with cleanup

## Implementation Strategy (Current Status)

### Current Implementation: ADK-First Complete

#### Phase 1: ADK Integration - ✅ Complete (September 2024)
- ✅ All data contracts implemented with ADK compatibility  
- ✅ TaskRequest/TaskResult with session management fields
- ✅ AdkFrameworkAdapter with three execution modes
- ✅ AgentManager + RunnerManager integration
- ✅ Bootstrap system with 5-phase initialization
- ✅ Complete agent lifecycle management
- ✅ Multi-turn conversation support

#### Phase 2: Tool and Live Execution - 🚧 In Progress  
- ✅ Basic ToolService with builtin tools
- 🚧 MCP tool integration (framework ready)
- 🚧 ADK native tool integration (planned)
- 🚧 Live execution framework (basic implementation)
- 📋 Interactive streaming features (future)

#### Phase 3: Multi-Framework Support - 📋 Future
- 📋 AutoGen framework adapter (architecture ready)
- 📋 LangGraph framework adapter (architecture ready)
- 📋 Multi-framework strategy routing (current: ADK-first)
- 📋 Framework-specific optimizations

### Progressive Framework Support Strategy (Updated)

#### Current: ADK-First Implementation ✅
- **Complete ADK Integration**: Full session management, agent lifecycle, tool integration
- **Session Architecture**: agent_id + session_id model for persistent conversations
- **Extensible Contracts**: Data structures ready for multi-framework expansion
- **Production Ready**: Stable ADK-based system with comprehensive testing

#### Next: Enhanced Tool Integration 🚧
- **MCP Integration**: Model Context Protocol tool support
- **ADK Native Tools**: Direct ADK tool system integration  
- **External API Tools**: REST/GraphQL API tool wrappers
- **Tool Security**: Permission system and sandboxing

#### Future: Multi-Framework Expansion 📋
- **AutoGen Integration**: Microsoft AutoGen framework support
- **LangGraph Integration**: LangChain LangGraph framework support
- **Intelligent Routing**: AI-driven framework selection based on task characteristics
- **Cross-Framework Features**: Unified capabilities across all supported frameworks

### Key Implementation Decisions

#### 1. ADK-First Strategy ✅ 
- Complete ADK implementation provides stable foundation
- Extensible architecture ready for additional frameworks
- Session management optimized for persistent conversations
- Tool integration architecture supports multiple tool types

#### 2. Session-Based Architecture ✅
- **Three Execution Modes**: Support for different conversation patterns
- **Agent Lifecycle**: Proper creation, management, and cleanup
- **State Persistence**: ADK session state managed by RunnerManager
- **Multi-turn Support**: Full conversation history and context

#### 3. Contract-Driven Design ✅
- **Stable Interfaces**: Well-defined data structures between layers
- **Framework Agnostic**: Contracts work across different implementations
- **Backward Compatibility**: Changes maintain existing functionality
- **Progressive Enhancement**: Easy to add new features and frameworks

#### 4. Bootstrap-Driven Initialization ✅  
- **5-Phase Startup**: Proper component initialization order
- **Dependency Management**: Clean dependency injection
- **Health Monitoring**: Comprehensive system health checks
- **Configuration**: Environment-based configuration management

## Implementation Notes (Updated)

### Current Architecture Status

- ✅ **Layer contracts implemented** with ADK optimization and future-framework compatibility
- ✅ **Each layer focused on specific responsibilities** with clear separation of concerns  
- ✅ **Framework adapters handle framework-specific conversions** between universal and ADK formats
- ✅ **Universal data structures provide foundation** for current ADK implementation and future frameworks
- ✅ **Session management architecture** supports persistent multi-turn conversations
- ✅ **Agent lifecycle management** with proper creation, tracking, and cleanup
- ✅ **Bootstrap system coordinates** component initialization and dependency management

### ADK-First Implementation Benefits

- **Production Ready**: Stable, tested system with complete ADK integration
- **Session Persistence**: Full support for multi-turn conversations and agent continuity  
- **Extensible Design**: Architecture ready for AutoGen and LangGraph integration
- **Tool Integration**: Unified tool service supporting multiple tool types
- **Comprehensive Testing**: E2E tests covering all execution modes and scenarios
- **Configuration Management**: Environment-based settings with capability management

### Next Development Priorities

1. **Enhanced Tool Integration**: Complete MCP and ADK native tool support
2. **Live Execution Features**: Interactive streaming with user intervention  
3. **Performance Optimization**: ADK session management and resource efficiency
4. **Multi-Framework Preparation**: AutoGen and LangGraph adapter implementation
5. **Security Enhancements**: Tool sandboxing and permission system

The current implementation provides a solid foundation for multi-agent applications with complete ADK support and an architecture designed for seamless multi-framework expansion.