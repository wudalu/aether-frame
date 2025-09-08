# Framework Abstraction Layer Design

## Overview

The Framework Abstraction Layer provides a unified interface for multiple agent frameworks (ADK, AutoGen, LangGraph) while maintaining framework-agnostic execution capabilities. This design enables seamless framework switching without application logic changes through a strategy-based routing approach.

The design follows a **layered contract approach**, starting with ADK-compatible foundation and evolving toward universal framework support through progressive abstraction.

## Design Goals

- **Framework Agnostic**: Unified interfaces that work consistently across different frameworks
- **ADK-First Compatibility**: Initial implementation optimized for ADK runtime with extensibility to other frameworks
- **Progressive Abstraction**: Evolve from ADK-specific to universal data contracts without breaking changes
- **Layered Architecture**: Clear separation following the established system architecture layers
- **Contract-Driven Design**: Well-defined data contracts between architectural layers

## Architecture Layers and Design Strategy

### Layer-by-Layer Design Approach

Following the established architecture in `docs/architecture.md`, we design interfaces layer by layer:

```
1. Application Execution Layer → 2. Framework Abstraction Layer → 3. Core Agent Layer → 4. Tool Service Layer
```

**Design Philosophy**: 
- **Contract-First**: Define data contracts between layers before implementing interfaces
- **ADK-Compatible Foundation**: Start with ADK-native data structures, progressively abstract
- **Top-Down Design**: Begin with execution layer requirements, derive lower layer contracts

## Layer Data Contracts

### Type System Overview and Dependencies

The framework abstraction uses a hierarchical type system with clear dependency relationships:

```
Core Request/Response Flow:
TaskRequest → ExecutionEngine → FrameworkAdapter → AgentRequest → ToolRequest
    ↓              ↓                   ↓              ↓           ↓
TaskResult  ← ExecutionMetadata ← AgentResponse ← ToolResult ← ToolError

Primary Data Types:
├── TaskRequest
│   ├── UserContext → UserPermissions, UserPreferences  
│   ├── SessionContext → UniversalMessage
│   ├── UniversalMessage → ContentPart → ToolCall, FileReference, ImageReference
│   ├── KnowledgeSource
│   ├── UniversalTool
│   └── ExecutionConfig → FrameworkType, ExecutionMode
│
├── AgentRequest  
│   ├── AgentConfig → AdkAgentConfig
│   ├── RuntimeConfig
│   └── KnowledgeSource, UniversalTool (inherited)
│
├── ToolRequest
│   ├── ToolConfig → UserPermissions
│   └── UserContext, SessionContext (inherited)
│
└── Framework Management
    ├── FrameworkAdapter → AgentHandle  
    ├── ExecutionContext
    ├── StrategyConfig → TaskComplexity, FrameworkType
    └── ToolDefinition

Status and Metadata Types:
├── TaskStatus, ToolStatus (enums)
├── ExecutionMetadata → FrameworkType
├── ToolUsage
├── ContextUpdate
├── ReasoningStep, AgentState
└── ToolError

Multi-modal Content:
ContentPart → FileReference, ImageReference, ToolCall
```

#### Key Dependency Patterns

1. **Inheritance Pattern**: Lower layer contracts inherit and extend upper layer data
   - `AgentRequest` includes `KnowledgeSource` and `UniversalTool` from `TaskRequest`
   - `ToolRequest` includes `UserContext` and `SessionContext` for permission propagation

2. **Composition Pattern**: Complex types compose simpler types
   - `TaskRequest` composes `UserContext`, `SessionContext`, `ExecutionConfig`
   - `UniversalMessage` composes `ContentPart` for multi-modal support

3. **Status Flow**: Status types flow upward through the execution stack
   - `ToolStatus` → `AgentResponse` → `TaskResult`
   - Error information bubbles up through `ToolError` → `AgentResponse` → `TaskResult`

4. **Framework Adaptation**: Framework-specific types adapt universal types
   - `AdkAgentConfig` extends `AgentConfig` for ADK-specific settings
   - `FrameworkAdapter` manages framework-specific `AgentHandle` instances

5. **Context Propagation**: Context flows down through execution layers
   - `ExecutionContext` → `TaskRequest` → `AgentRequest` → `ToolRequest`
   - User permissions and session state maintained throughout execution chain

### 1. Execution Layer ↔ Framework Abstraction Layer Contract

#### TaskRequest (Downward Contract)
```python
@dataclass
class TaskRequest:
    # Core identification
    task_id: str  # Unique identifier for task tracking and monitoring
    task_type: str  # Task category for strategy routing (e.g., "chat", "analysis", "search")
    
    # Flexible user identification (framework adaptable)
    user_context: UserContext  # User identification and permissions
    
    # Unified session management
    session_context: SessionContext  # Session tracking across frameworks
    
    # Universal message format (extensible to other frameworks)
    messages: List[UniversalMessage]  # Conversation messages in universal format
    
    # Available resources
    available_tools: List[UniversalTool]  # Tools accessible during execution
    available_knowledge: List[KnowledgeSource]  # Knowledge sources (databases, files, APIs, embeddings)
    
    # Execution configuration (unified)
    execution_config: ExecutionConfig  # Runtime settings and framework selection

@dataclass
class UserContext:
    """Flexible user identification supporting different frameworks"""
    # Optional user_id (required by ADK, optional for others)
    user_id: Optional[str] = None  # Explicit user identifier (ADK required)
    
    # Alternative identification methods
    user_name: Optional[str] = None  # Human-readable username
    session_token: Optional[str] = None  # Session-based identification
    
    # User-specific settings
    permissions: Optional[UserPermissions] = None  # User access permissions
    preferences: Optional[UserPreferences] = None  # User preference settings
    
    def get_adk_user_id(self) -> str:
        """Get or generate user_id for ADK compatibility"""
        if self.user_id:
            return self.user_id
        # Generate from user_name or session_token
        return self._generate_user_id()
    
    def _generate_user_id(self) -> str:
        """Generate ADK-compatible user_id when not provided"""
        if self.user_name:
            return f"user_{hash(self.user_name) % 100000}"
        if self.session_token:
            return f"session_{hash(self.session_token) % 100000}"
        return f"anonymous_{uuid.uuid4().hex[:8]}"

@dataclass
class SessionContext:
    """Unified session management across frameworks"""
    # Session identification
    session_id: Optional[str] = None  # ADK-compatible session identifier
    conversation_id: Optional[str] = None  # Alternative session tracking ID
    
    # Session state
    conversation_history: List[UniversalMessage] = field(default_factory=list)  # Message history for context
    session_state: Dict[str, Any] = field(default_factory=dict)  # Framework-specific session data
    
    # Session metadata
    created_at: Optional[datetime] = None  # Session creation timestamp
    last_activity: Optional[datetime] = None  # Last interaction timestamp
    
    def get_adk_session_id(self) -> Optional[str]:
        """Get ADK-compatible session_id"""
        return self.session_id or self.conversation_id
    
    def ensure_session_id(self) -> str:
        """Ensure session_id exists for ADK"""
        if not self.session_id and not self.conversation_id:
            self.session_id = f"session_{uuid.uuid4().hex[:12]}"
        return self.get_adk_session_id()

@dataclass
class UniversalMessage:
    """Framework-agnostic message format with ADK compatibility"""
    role: str  # Message role: "user", "assistant", "system", "tool"
    content: Union[str, List[ContentPart]]  # Message content (text or multi-modal)
    
    # Optional framework-specific fields
    author: Optional[str] = None  # ADK uses 'author' instead of 'role'
    name: Optional[str] = None    # AutoGen agent name identifier
    tool_calls: Optional[List[ToolCall]] = None  # Tool invocation requests
    
    def to_adk_format(self) -> Dict[str, Any]:
        """Convert to ADK native format"""
        return {
            'author': self.author or self.role,
            'content': {'parts': self._to_content_parts()}
        }
    
    def to_autogen_format(self) -> Dict[str, Any]:
        """Convert to AutoGen format (future extension)"""
        return {
            'role': self.role,
            'content': str(self.content),
            'name': self.name
        }

@dataclass
class ContentPart:
    """Multi-modal content part compatible with ADK parts structure"""
    text: Optional[str] = None  # Plain text content
    function_call: Optional[ToolCall] = None  # Tool/function call request
    file_reference: Optional[FileReference] = None  # File attachment reference
    image_reference: Optional[ImageReference] = None  # Image content reference

@dataclass
class ExecutionConfig:
    """Unified execution configuration combining runtime and framework settings"""
    # Runtime execution settings
    timeout: Optional[int] = None  # Maximum execution time in seconds
    max_retries: int = 3  # Retry attempts on failure
    streaming: bool = False  # Enable streaming response
    parallel_execution: bool = False  # Allow parallel agent execution
    
    # Framework selection and configuration
    preferred_framework: Optional[FrameworkType] = None  # Override strategy-based selection
    framework_settings: Dict[str, Any] = field(default_factory=dict)  # Framework-specific parameters
    
    # Performance and monitoring
    enable_tracing: bool = True  # Enable execution tracing
    enable_metrics: bool = True  # Enable performance metrics collection
    log_level: str = "INFO"  # Logging verbosity level
```

#### TaskResult (Upward Contract)
```python
@dataclass
class TaskResult:
    task_id: str  # Matching task identifier from request
    status: TaskStatus  # Execution status: success, error, partial, timeout
    
    # Universal response format
    response: UniversalResponse  # Standardized response content
    
    # Execution metadata
    execution_metadata: ExecutionMetadata  # Performance and timing data
    tool_usage: List[ToolUsage]  # Tools used during execution
    
    # Updated context
    context_updates: Optional[ContextUpdate] = None  # Context changes from execution

@dataclass
class UniversalResponse:
    """Framework-agnostic response with ADK compatibility"""
    content: UniversalMessage  # Main response content
    
    # ADK-specific fields (optional for other frameworks)
    actions: Optional[AdkActions] = None  # ADK artifact_delta, state_delta
    
    # Extensible for other frameworks
    framework_specific: Dict[str, Any] = field(default_factory=dict)  # Framework-native response data

@dataclass
class AdkActions:
    """ADK-specific action structure"""
    artifact_delta: Dict[str, Any] = field(default_factory=dict)  # Changes to artifacts
    requested_auth_configs: Dict[str, Any] = field(default_factory=dict)  # Auth requests
    state_delta: Dict[str, Any] = field(default_factory=dict)  # State changes
```

### 2. Framework Abstraction Layer ↔ Agent Layer Contract

#### AgentRequest (Downward Contract)
```python
@dataclass
class AgentRequest:
    agent_id: str  # Unique agent identifier for tracking
    agent_type: str  # Agent type mapping to framework classes (e.g., "llm", "workflow", "reactive")
    
    # Standardized message sequence
    messages: List[UniversalMessage]  # Conversation messages for agent processing
    
    # Agent resources
    tools: List[UniversalTool]  # Available tools for agent use
    knowledge_bases: List[KnowledgeSource]  # Available knowledge sources
    
    # Agent configuration (framework-adaptable)
    agent_config: AgentConfig  # Agent-specific configuration
    runtime_config: RuntimeConfig  # Agent runtime parameters

@dataclass
class RuntimeConfig:
    """Agent runtime execution parameters"""
    timeout: Optional[int] = None  # Agent execution timeout in seconds
    max_iterations: Optional[int] = None  # Maximum reasoning iterations
    enable_streaming: bool = False  # Enable streaming agent responses
    memory_limit: Optional[int] = None  # Memory usage limit in MB

@dataclass
class AgentConfig:
    """Framework-adaptable agent configuration"""
    # Universal fields
    name: str  # Agent display name
    model: str  # LLM model identifier (e.g., "gemini-pro", "gpt-4")
    temperature: Optional[float] = None  # Response randomness (0.0-1.0)
    max_tokens: Optional[int] = None  # Maximum response length
    
    # ADK-specific fields
    adk_config: Optional[AdkAgentConfig] = None  # ADK framework configuration
    
    # Future framework configs
    autogen_config: Optional[Dict[str, Any]] = None  # AutoGen-specific settings
    langgraph_config: Optional[Dict[str, Any]] = None  # LangGraph-specific settings

@dataclass
class AdkAgentConfig:
    """ADK-specific agent configuration"""
    agent_class: str  # ADK agent class: "Agent", "SequentialAgent", "ParallelAgent"
    generate_content_config: Optional[Dict[str, Any]] = None  # ADK generation parameters
    enable_tracing: bool = True  # Enable ADK execution tracing

@dataclass
class KnowledgeSource:
    """Various types of knowledge sources available to agents"""
    source_id: str  # Unique identifier for the knowledge source
    source_type: str  # Type: "vector_db", "sql_db", "file_system", "api", "graph_db", "memory"
    connection_info: Dict[str, Any]  # Connection parameters specific to source type
    
    # Access configuration
    permissions: Optional[List[str]] = None  # Required permissions to access
    cache_ttl: Optional[int] = None  # Cache time-to-live in seconds
    
    # Metadata
    description: Optional[str] = None  # Human-readable description
    schema_info: Optional[Dict[str, Any]] = None  # Structure/schema information
```

#### AgentResponse (Upward Contract)
```python
@dataclass
class AgentResponse:
    agent_id: str  # Matching agent identifier from request
    
    # Response content
    content: UniversalMessage  # Agent's response message
    
    # Agent execution info
    tool_usage: List[ToolUsage]  # Tools invoked during processing
    reasoning_trace: Optional[List[ReasoningStep]] = None  # Agent's reasoning steps
    agent_state: Optional[AgentState] = None  # Updated agent internal state
    
    # Framework-specific responses
    framework_response: Optional[Dict[str, Any]] = None  # Raw framework response data
```

### 3. Agent Layer ↔ Tool Layer Contract

#### ToolRequest (Downward Contract)
```python
@dataclass
class ToolRequest:
    tool_name: str  # Tool identifier for invocation
    parameters: Dict[str, Any]  # Tool input parameters
    
    # Execution context
    user_context: UserContext  # User identification and permissions
    session_context: SessionContext  # Session state for context
    
    # Tool-specific configuration
    tool_config: ToolConfig  # Tool execution settings

@dataclass
class ToolConfig:
    timeout: Optional[int] = None  # Maximum execution time in seconds
    retry_count: int = 3  # Number of retry attempts on failure
    user_permissions: Optional[UserPermissions] = None  # User access level for tool
```

#### ToolResult (Upward Contract)
```python
@dataclass
class ToolResult:
    tool_name: str  # Matching tool identifier from request
    status: ToolStatus  # Execution status: success, error, timeout, unauthorized
    
    # Result content (multi-format support)
    result: Union[str, Dict[str, Any], bytes]  # Tool output in appropriate format
    
    # Execution metadata
    execution_time: float  # Tool execution duration in seconds
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional tool-specific data
    
    # Error information (if applicable)
    error: Optional[ToolError] = None  # Error details when status indicates failure
```

## Layer Interface Design (Following Architecture Layers)

### 1. Application Execution Layer Interfaces

Based on the architecture design, the Execution Layer contains AI Assistant and Execution Engine components with their sub-components.

#### AIAssistant Interface
```python
class AIAssistant:
    """Entry point for task analysis and routing"""
    
    def __init__(self, execution_engine: 'ExecutionEngine'):
        """Initialize with execution engine dependency"""
        self.execution_engine = execution_engine
    
    async def process_request(self, task: TaskRequest) -> TaskResult:
        """Process incoming task request and coordinate execution"""
        # Create execution context
        context = ExecutionContext(
            request_id=str(uuid.uuid4()),
            start_time=datetime.now(),
            environment=self._determine_environment()
        )
        
        # Delegate to execution engine
        return await self.execution_engine.execute_task(task, context)
    
    def _determine_environment(self) -> str:
        """Determine execution environment based on configuration"""
        pass

@dataclass
class ExecutionContext:
    """Runtime context for task execution"""
    request_id: str  # Unique request identifier for tracing
    start_time: datetime  # Task execution start timestamp
    correlation_id: Optional[str] = None  # Cross-service correlation identifier
    client_info: Optional[Dict[str, Any]] = None  # Client application metadata
    environment: str = "development"  # Execution environment: development, staging, production
```

#### ExecutionEngine Interface
```python
class ExecutionEngine:
    """Unified execution engine with strategy-based framework selection"""
    
    def __init__(self, task_router: 'TaskRouter', framework_registry: 'FrameworkRegistry'):
        """Initialize with task router and framework registry dependencies"""
        self.task_router = task_router
        self.framework_registry = framework_registry
    
    async def execute_task(self, task: TaskRequest, context: ExecutionContext) -> TaskResult:
        """Execute task using strategy-based framework selection
        - Select execution strategy based on task characteristics
        - Get framework adapter from strategy configuration
        - Execute task using selected framework adapter
        """
        # Select strategy based on task
        strategy_config = await self.task_router.select_strategy(task, context)
        
        # Get framework adapter based on strategy's target framework
        framework_adapter = self.framework_registry.get_adapter(strategy_config.target_framework)
        
        # Execute task using framework adapter
        return await framework_adapter.execute_task(task, context)
    
    def register_framework_adapter(self, framework_type: FrameworkType, adapter: 'FrameworkAdapter') -> None:
        """Register framework adapter in registry"""
        self.framework_registry.register_adapter(framework_type, adapter)
    
    def get_available_strategies(self) -> List[StrategyConfig]:
        """Get list of available execution strategies"""
        return self.task_router.list_available_strategies()
```

#### TaskRouter Interface
```python
class TaskRouter:
    """Task analysis and strategy selection"""
    
    def __init__(self, available_strategies: List[StrategyConfig]):
        """Initialize with available strategy configurations"""
        self.available_strategies = available_strategies
    
    async def select_strategy(self, task: TaskRequest, context: ExecutionContext) -> StrategyConfig:
        """Analyze task and select appropriate execution strategy
        - Analyze task complexity and characteristics
        - Match against available strategies
        - Return best matching strategy configuration (includes target_framework)
        """
        # Analyze task complexity
        complexity = self._analyze_task_complexity(task)
        
        # Find matching strategies
        matching_strategies = self._find_matching_strategies(
            task_type=task.task_type,
            complexity=complexity
        )
        
        # Select best strategy based on priority
        return self._select_best_strategy(matching_strategies, task, context)
    
    def register_strategy(self, strategy_config: StrategyConfig) -> None:
        """Register new strategy configuration"""
        self.available_strategies.append(strategy_config)
    
    def list_available_strategies(self) -> List[StrategyConfig]:
        """List all available strategies"""
        return self.available_strategies.copy()
    
    def _analyze_task_complexity(self, task: TaskRequest) -> TaskComplexity:
        """Analyze task to determine complexity level"""
        pass
    
    def _find_matching_strategies(self, task_type: str, complexity: TaskComplexity) -> List[StrategyConfig]:
        """Find strategies that can handle the given task type and complexity"""
        pass
    
    def _select_best_strategy(self, strategies: List[StrategyConfig], task: TaskRequest, context: ExecutionContext) -> StrategyConfig:
        """Select best strategy from matching candidates based on priority and context"""
        pass
```

## 数据契约调整

基于简化的执行流程，我们需要确保StrategyConfig包含足够的信息用于框架选择：

```python
@dataclass
class StrategyConfig:
    """Strategy configuration for framework selection"""
    strategy_name: str  # Unique strategy identifier
    applicable_task_types: List[str]  # Task types this strategy can handle
    complexity_levels: List[TaskComplexity]  # Supported complexity levels  
    execution_modes: List[ExecutionMode]  # Supported execution patterns
    target_framework: FrameworkType  # Target framework for execution
    priority: int  # Selection priority when multiple strategies match
    
    # Additional strategy metadata
    description: Optional[str] = None  # Human-readable description
    resource_requirements: Optional[Dict[str, Any]] = None  # Resource needs (memory, CPU, etc.)
    performance_characteristics: Optional[Dict[str, Any]] = None  # Expected performance metrics
```

### 2. Framework Abstraction Layer Interfaces

Based on the architecture design, the Framework Abstraction Layer provides unified execution interfaces for different frameworks. This layer receives framework selection decisions from the Execution Layer and focuses on framework-specific execution.

#### FrameworkRegistry (Core Component)
```python
class FrameworkRegistry:
    """Central registry for framework adapters
    - Manages framework adapter instances
    - Provides adapter lifecycle management
    - Handles framework discovery and capabilities
    """
    
    def __init__(self):
        """Initialize empty registry"""
        self._adapters: Dict[FrameworkType, FrameworkAdapter] = {}
        self._adapter_configs: Dict[FrameworkType, Dict[str, Any]] = {}
    
    def register_adapter(self, framework_type: FrameworkType, adapter: FrameworkAdapter) -> None:
        """Register framework adapter instance"""
        self._adapters[framework_type] = adapter
    
    def get_adapter(self, framework_type: FrameworkType) -> FrameworkAdapter:
        """Get registered adapter for framework type"""
        if framework_type not in self._adapters:
            raise ValueError(f"No adapter registered for framework: {framework_type}")
        return self._adapters[framework_type]
    
    def list_available_frameworks(self) -> List[FrameworkType]:
        """List all registered framework types"""
        return list(self._adapters.keys())
    
    def create_and_register_adapter(self, framework_type: FrameworkType, config: Dict[str, Any]) -> FrameworkAdapter:
        """Create and register new adapter instance with configuration"""
        adapter = self._create_adapter(framework_type, config)
        self.register_adapter(framework_type, adapter)
        return adapter
    
    def get_framework_capabilities(self, framework_type: FrameworkType) -> Dict[str, Any]:
        """Get capabilities of specific framework"""
        adapter = self.get_adapter(framework_type)
        return adapter.get_capabilities()
    
    def _create_adapter(self, framework_type: FrameworkType, config: Dict[str, Any]) -> FrameworkAdapter:
        """Factory method for creating framework adapters"""
        if framework_type == FrameworkType.ADK:
            return AdkFrameworkAdapter(AdkConfig(**config))
        # Add other framework types as needed
        raise ValueError(f"Unsupported framework type: {framework_type}")
```

#### FrameworkAdapter Interface
```python
from abc import ABC, abstractmethod

class FrameworkAdapter(ABC):
    """Abstract base for framework-specific execution implementations
    - Provides unified interface for TaskRequest/TaskResult execution
    - Handles framework-specific request/response conversion
    - Encapsulates framework runtime integration
    """
    
    @abstractmethod
    def get_framework_type(self) -> FrameworkType:
        """Return the framework type this adapter supports"""
        pass
    
    @abstractmethod
    async def execute_task(self, task: TaskRequest, context: ExecutionContext) -> TaskResult:
        """Execute TaskRequest using framework-specific implementation
        - Convert TaskRequest to framework-native format
        - Execute using framework runtime
        - Convert framework response to TaskResult
        """
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

#### AdkFrameworkAdapter (Concrete Implementation)
```python
class AdkFrameworkAdapter(FrameworkAdapter):
    """ADK framework adapter implementation"""
    
    def __init__(self, adk_config: AdkConfig):
        """Initialize with ADK-specific configuration"""
        pass
    
    def get_framework_type(self) -> FrameworkType:
        """Return FrameworkType.ADK"""
        pass
    
    async def execute_task(self, task: TaskRequest, context: ExecutionContext) -> TaskResult:
        """Execute task using ADK runtime
        - Convert to ADK format using user_id, session_id from TaskRequest
        - Execute through ADK Agent Engine
        - Convert ADK response back to TaskResult
        """
        pass
    
    async def validate_task(self, task: TaskRequest) -> bool:
        """Validate task compatibility with ADK requirements"""
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return ADK-specific capabilities (supported models, features, limits)"""
        pass
```

#### Supporting Configuration Classes
```python
@dataclass
class AdkConfig:
    """ADK framework configuration"""
    project_id: str  # Google Cloud project ID
    region: str = "us-central1"  # Google Cloud region
    model_name: str = "gemini-pro"  # Default LLM model
    enable_tracing: bool = True  # Enable execution tracing
    timeout_seconds: int = 300  # Request timeout
    max_retries: int = 3  # Maximum retry attempts

@dataclass
class FrameworkCapabilities:
    """Framework capability description"""
    supported_task_types: List[str]  # Task types this framework can handle
    supported_execution_modes: List[ExecutionMode]  # Execution modes supported
    max_concurrent_tasks: int  # Maximum concurrent task execution
    supports_streaming: bool  # Whether framework supports streaming responses
    supports_tool_calling: bool  # Whether framework supports tool execution
    model_providers: List[str]  # Supported model providers (e.g., "google", "openai")
```

#### Supporting Classes
```python
# No additional supporting classes needed at this layer
# AgentHandle and other agent management concepts belong to Core Agent Layer
```

# Additional Supporting Data Structures

## Detailed Type Definitions

@dataclass
class UniversalTool:
    """Universal tool definition across frameworks"""
    name: str  # Tool identifier
    description: str  # Tool functionality description
    parameters_schema: Dict[str, Any]  # JSON Schema for tool parameters
    framework_specific: Dict[str, Any] = field(default_factory=dict)  # Framework-specific tool data
    version: str = "1.0"  # Tool version for compatibility

@dataclass
class TaskStatus(Enum):
    """Task execution status enumeration"""
    SUCCESS = "success"  # Task completed successfully
    ERROR = "error"  # Task failed with error
    PARTIAL = "partial"  # Task partially completed
    TIMEOUT = "timeout"  # Task exceeded time limit
    CANCELLED = "cancelled"  # Task was cancelled by user

@dataclass
class ToolStatus(Enum):
    """Tool execution status enumeration"""
    SUCCESS = "success"  # Tool executed successfully
    ERROR = "error"  # Tool execution failed
    TIMEOUT = "timeout"  # Tool execution timed out
    UNAUTHORIZED = "unauthorized"  # User lacks required permissions
    NOT_FOUND = "not_found"  # Tool not found

@dataclass
class FrameworkType(Enum):
    """Supported framework types"""
    ADK = "adk"  # Google Agent Development Kit
    AUTOGEN = "autogen"  # Microsoft AutoGen
    LANGGRAPH = "langgraph"  # LangGraph from LangChain

@dataclass
class TaskComplexity(Enum):
    """Task complexity levels for strategy selection"""
    SIMPLE = "simple"  # Single-turn, basic operations
    MODERATE = "moderate"  # Multi-turn, tool usage
    COMPLEX = "complex"  # Multi-agent, planning required
    ADVANCED = "advanced"  # Long-running, complex workflows

@dataclass
class ExecutionMode(Enum):
    """Execution mode patterns"""
    SYNC = "sync"  # Synchronous execution
    ASYNC = "async"  # Asynchronous execution
    STREAMING = "streaming"  # Real-time streaming
    BATCH = "batch"  # Batch processing

@dataclass
class ExecutionMetadata:
    """Metadata about task execution"""
    start_time: datetime  # Execution start timestamp
    end_time: datetime  # Execution completion timestamp
    duration_seconds: float  # Total execution duration
    framework_used: FrameworkType  # Framework that handled the task
    strategy_applied: str  # Strategy name that was selected
    resource_usage: Dict[str, Any] = field(default_factory=dict)  # Resource consumption metrics
    error_count: int = 0  # Number of errors encountered

@dataclass
class ToolUsage:
    """Information about tool usage during execution"""
    tool_name: str  # Tool identifier
    invocation_count: int  # Number of times tool was called
    total_duration: float  # Total time spent in tool execution
    success_rate: float  # Percentage of successful invocations
    parameters_used: List[Dict[str, Any]] = field(default_factory=list)  # Parameters passed to tool

@dataclass
class ContextUpdate:
    """Updates to context from task execution"""
    session_state_changes: Dict[str, Any] = field(default_factory=dict)  # Changes to session state
    user_preference_updates: Dict[str, Any] = field(default_factory=dict)  # Updates to user preferences
    conversation_summary: Optional[str] = None  # Summary of conversation for context
    learned_facts: List[str] = field(default_factory=list)  # New facts learned during execution

@dataclass
class ToolCall:
    """Tool invocation request structure"""
    tool_name: str  # Tool to invoke
    parameters: Dict[str, Any]  # Tool parameters
    call_id: Optional[str] = None  # Unique call identifier for tracking
    expected_format: Optional[str] = None  # Expected response format

@dataclass
class FileReference:
    """Reference to file content"""
    file_id: str  # Unique file identifier
    file_name: str  # Original file name
    file_type: str  # File MIME type
    file_size: int  # File size in bytes
    storage_location: str  # Storage location reference
    access_permissions: List[str] = field(default_factory=list)  # Required permissions

@dataclass
class ImageReference:
    """Reference to image content"""
    image_id: str  # Unique image identifier
    image_url: Optional[str] = None  # Image URL if accessible
    image_format: str = "png"  # Image format (png, jpg, webp)
    dimensions: Optional[Tuple[int, int]] = None  # Image width and height
    description: Optional[str] = None  # Alternative text description

@dataclass
class UserPermissions:
    """User access permissions"""
    roles: List[str] = field(default_factory=list)  # User roles
    permissions: List[str] = field(default_factory=list)  # Specific permissions
    restrictions: List[str] = field(default_factory=list)  # Access restrictions
    expires_at: Optional[datetime] = None  # Permission expiration time

@dataclass
class UserPreferences:
    """User preference settings"""
    language: str = "en"  # Preferred language code
    timezone: str = "UTC"  # User timezone
    response_format: str = "text"  # Preferred response format
    verbosity_level: str = "normal"  # Response verbosity: minimal, normal, detailed
    custom_settings: Dict[str, Any] = field(default_factory=dict)  # Custom user settings

@dataclass
class ReasoningStep:
    """Agent reasoning step information"""
    step_id: str  # Unique step identifier
    step_type: str  # Step type: observe, think, act, reflect
    description: str  # Human-readable step description
    input_data: Dict[str, Any] = field(default_factory=dict)  # Step input
    output_data: Dict[str, Any] = field(default_factory=dict)  # Step output
    confidence: Optional[float] = None  # Confidence level (0.0-1.0)
    timestamp: datetime = field(default_factory=datetime.now)  # Step execution time

@dataclass
class AgentState:
    """Agent internal state information"""
    state_id: str  # Unique state identifier
    agent_memory: Dict[str, Any] = field(default_factory=dict)  # Agent working memory
    conversation_context: List[str] = field(default_factory=list)  # Recent conversation context
    active_goals: List[str] = field(default_factory=list)  # Current agent objectives
    learned_patterns: Dict[str, Any] = field(default_factory=dict)  # Patterns learned from interactions
    last_updated: datetime = field(default_factory=datetime.now)  # State last modified time

@dataclass
class ToolError:
    """Tool execution error information"""
    error_code: str  # Error code identifier
    error_message: str  # Human-readable error message
    error_type: str  # Error category: validation, execution, timeout, permission
    stack_trace: Optional[str] = None  # Detailed error stack trace
    retry_suggestion: Optional[str] = None  # Suggestion for retry or resolution
```

## Framework Adaptation Examples

### ADK Framework Adapter
```python
class AdkFrameworkAdapter(FrameworkAdapter):
    async def execute_task(self, task: TaskRequest, context: ExecutionContext) -> TaskResult:
        # Ensure ADK required fields exist
        user_id = task.user_context.get_adk_user_id()  # Required by ADK
        session_id = task.session_context.get_adk_session_id()  # Optional
        
        # Convert to ADK format
        adk_request = {
            'user_id': user_id,
            'session_id': session_id,
            'message': self._extract_main_message(task.messages)
        }
        
        return await self._execute_adk_request(adk_request)

class AutoGenFrameworkAdapter(FrameworkAdapter):
    async def execute_task(self, task: TaskRequest, context: ExecutionContext) -> TaskResult:
        # AutoGen doesn't require user_id, focuses on conversation flow
        return await self._execute_autogen_conversation(task.messages)

class LangGraphFrameworkAdapter(FrameworkAdapter):
    async def execute_task(self, task: TaskRequest, context: ExecutionContext) -> TaskResult:
        # LangGraph can optionally use session_id for state management
        state = {
            'messages': [msg.to_langgraph_format() for msg in task.messages],
            'session_id': task.session_context.get_adk_session_id()
        }
        return await self._execute_langgraph_workflow(state)
```

## Usage Examples

### Web Application Scenario
```python
# User with explicit ID
task_request = TaskRequest(
    task_id="web_task_123",
    task_type="chat",
    user_context=UserContext(user_id="web_user_123"),
    session_context=SessionContext(session_id="web_session_456"),
    messages=[UniversalMessage(role="user", content="Hello")],
    available_knowledge=[
        KnowledgeSource(
            source_id="user_docs",
            source_type="vector_db",
            connection_info={"index": "user_documents", "endpoint": "pinecone://..."}
        )
    ],
    execution_config=ExecutionConfig(
        streaming=True,
        enable_tracing=True,
        preferred_framework=FrameworkType.ADK
    )
)
```

### Anonymous Testing Scenario
```python
# Anonymous user (auto-generates user_id for ADK)
task_request = TaskRequest(
    task_id="test_task_123", 
    task_type="chat",
    user_context=UserContext(),  # Will auto-generate user_id
    session_context=SessionContext(),  # Will auto-generate session_id if needed
    messages=[UniversalMessage(role="user", content="Test message")],
    available_knowledge=[
        KnowledgeSource(
            source_id="test_memory",
            source_type="memory",
            connection_info={"type": "in_memory_cache"}
        )
    ],
    execution_config=ExecutionConfig(timeout=30, log_level="DEBUG")
)
```

### Complex Analysis Scenario
```python
# Multi-source knowledge with database and API access
task_request = TaskRequest(
    task_id="analysis_task_456",
    task_type="analysis", 
    user_context=UserContext(user_name="data_analyst"),
    session_context=SessionContext(conversation_id="analysis_session_789"),
    messages=[UniversalMessage(role="user", content="Analyze Q3 sales data")],
    available_knowledge=[
        KnowledgeSource(
            source_id="sales_db",
            source_type="sql_db",
            connection_info={"host": "postgres://...", "database": "sales"}
        ),
        KnowledgeSource(
            source_id="market_api",
            source_type="api",
            connection_info={"base_url": "https://api.market-data.com", "auth_type": "bearer"}
        )
    ],
    execution_config=ExecutionConfig(
        parallel_execution=True,
        preferred_framework=FrameworkType.LANGGRAPH,
        framework_settings={"max_graph_depth": 5}
    )
)
```

## Progressive Framework Support Strategy

### Phase 1: ADK-First Implementation
- Implement all contracts with native ADK compatibility
- Universal data structures optimized for ADK runtime
- Minimal conversion overhead for ADK operations

### Phase 2: AutoGen Extension
- Extend `UniversalMessage` and `AgentConfig` for AutoGen compatibility
- Add AutoGen-specific adapter implementation
- Maintain backward compatibility with ADK implementations

### Phase 3: LangGraph Extension
- Further extend universal contracts for LangGraph patterns
- Implement LangGraph adapter with state management support
- Unified interface supporting all three frameworks

### Phase 4: Framework-Agnostic Evolution
- Optimize universal contracts based on multi-framework experience
- Remove framework-specific fields where possible
- Achieve true framework independence in application layer

## Implementation Benefits

### 1. Immediate ADK Compatibility
- Native ADK data structures and execution patterns
- Minimal performance overhead
- Direct integration with Vertex AI Agent Engine

### 2. Extensibility Without Refactoring
- Universal contracts designed for multi-framework support
- Progressive enhancement rather than breaking changes
- Contract-driven development ensures interface stability

### 3. Clear Layer Separation
- Well-defined responsibilities at each layer
- Contract-driven interfaces reduce coupling
- Easy testing and debugging through layer isolation

### 4. Configuration-Driven Architecture
- Strategy selection through configuration
- Framework capabilities declared statically
- Runtime behavior controlled through config files

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

## Implementation Notes

- Layer contracts defined independently of framework specifics
- Each layer focuses on its specific responsibilities
- Framework adapters handle all framework-specific conversions
- Universal data structures provide common foundation for all frameworks
- Progressive enhancement strategy enables smooth evolution from ADK-only to multi-framework support