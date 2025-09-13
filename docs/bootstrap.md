# System Bootstrap Initialization Design

## Overview

This document defines the simplified system initialization approach for Aether Frame, using a single-file bootstrap manager to coordinate the startup of core system components.

## Design Principles

1. **Simplicity First**: Single file management instead of complex multi-layer initialization
2. **Focus on Essentials**: Initialize only the core components needed for operation
3. **Preserve Interfaces**: Maintain clean external APIs while simplifying internal complexity
4. **Future Extensibility**: Leave room for infrastructure expansion without breaking changes

## Current System Components

Based on the existing codebase analysis, the essential components requiring initialization are:

### Core Components to Initialize

1. **Framework Abstraction Layer**
   - FrameworkRegistry: Manages framework adapter registration and lifecycle
   - Framework Adapters: ADK adapter (auto-loaded), future AutoGen/LangGraph adapters

2. **Agent Management Layer**
   - AgentManager: Agent lifecycle and factory registration
   - Agent Factories: Framework-specific agent creation logic

3. **Execution Layer**
   - TaskRouter: Task analysis and strategy selection
   - ExecutionEngine: Central orchestration hub

4. **Tool Service Layer**
   - ToolService: Unified tool discovery and execution (optional)

## ADK Runtime Initialization

The ADK runtime initialization is already properly encapsulated within the `AdkFrameworkAdapter.initialize()` method:

### Current ADK Initialization Flow

```python
# In AdkFrameworkAdapter.initialize() (lines 60-111)
async def initialize(self, config: Optional[Dict[str, Any]] = None):
    # 1. Create InMemorySessionService 
    session_service = InMemorySessionService()
    
    # 2. Create Root Agent through AgentManager
    root_agent_config = self._build_root_agent_config()
    root_agent_id = await self._agent_manager.create_agent(root_agent_config)
    
    # 3. Create ADK Runner with Root Agent and SessionService
    self._runner = Runner(
        app_name=config.get("app_name", "aether_frame"),
        agent=root_domain_agent.adk_agent,
        session_service=session_service
    )
```

### ADK Dependencies Handling

- **Available**: Full ADK runtime initialization (Runner, SessionService, Agents)
- **Unavailable**: Graceful degradation, sets `_adk_available = False` but continues initialization
- **Error Recovery**: Proper error handling with descriptive messages

## Bootstrap Architecture

### File Structure

```
src/aether_frame/
├── bootstrap.py              # Single-file initialization manager  
├── execution/ai_assistant.py # Modified to use bootstrap
└── main.py                   # Modified to use bootstrap
```

### Bootstrap Implementation

#### Core Bootstrap Function

```python
# bootstrap.py
from typing import Optional, NamedTuple
from .config.settings import Settings
from .contracts import FrameworkType
from .execution import ExecutionEngine, TaskRouter
from .framework import FrameworkRegistry
from .agents import AgentManager
from .tools import ToolService


class SystemComponents(NamedTuple):
    """Container for initialized system components."""
    framework_registry: FrameworkRegistry
    agent_manager: AgentManager
    task_router: TaskRouter
    execution_engine: ExecutionEngine
    tool_service: Optional[ToolService] = None


async def initialize_system(settings: Optional[Settings] = None) -> SystemComponents:
    """
    Initialize all system components with proper dependency order.
    
    Args:
        settings: Application settings (loads defaults if None)
        
    Returns:
        SystemComponents: Container with all initialized components
        
    Raises:
        RuntimeError: If critical components fail to initialize
    """
    if settings is None:
        settings = Settings()
    
    try:
        # Phase 1: Framework Registry & Adapters
        framework_registry = FrameworkRegistry()
        
        # ADK adapter auto-initialization happens here
        # - FrameworkRegistry.get_adapter(ADK) triggers auto-load
        # - AdkFrameworkAdapter.initialize() handles ADK runtime setup
        adk_adapter = await framework_registry.get_adapter(FrameworkType.ADK)
        
        # Phase 2: Tool Service (optional)
        tool_service = None
        if settings.enable_tool_service:
            tool_service = ToolService()
            await tool_service.initialize({
                "enable_mcp": settings.enable_mcp_tools,
                "enable_adk_native": settings.enable_adk_native_tools,
                "enable_builtin": True
            })
        
        # Phase 3: Agent Manager with factory registration
        agent_manager = AgentManager()
        
        # Register agent factories for available frameworks
        if adk_adapter and await adk_adapter.is_available():
            await _register_adk_agent_factory(agent_manager)
        
        # Phase 4: Execution components
        task_router = TaskRouter(settings)
        execution_engine = ExecutionEngine(framework_registry, settings)
        
        return SystemComponents(
            framework_registry=framework_registry,
            agent_manager=agent_manager,
            task_router=task_router,
            execution_engine=execution_engine,
            tool_service=tool_service
        )
        
    except Exception as e:
        raise RuntimeError(f"System initialization failed: {str(e)}")


async def _register_adk_agent_factory(agent_manager: AgentManager):
    """Register ADK-specific agent factory with AgentManager."""
    from .agents.adk import AdkDomainAgent
    from .contracts import AgentConfig, FrameworkType
    
    def create_adk_agent(agent_config: AgentConfig) -> AdkDomainAgent:
        """Factory function for creating ADK domain agents."""
        return AdkDomainAgent(
            agent_id=agent_config.name,
            agent_config=agent_config
        )
    
    agent_manager.register_agent_factory(
        FrameworkType.ADK, 
        create_adk_agent
    )
```

#### External Interface Functions

```python
async def create_ai_assistant(settings: Optional[Settings] = None) -> AIAssistant:
    """
    Create fully initialized AI Assistant - primary external interface.
    
    This is the main function applications should use to get a ready-to-use
    AI Assistant instance with all dependencies properly initialized.
    
    Args:
        settings: Optional application settings
        
    Returns:
        AIAssistant: Fully initialized AI Assistant ready for use
        
    Example:
        >>> assistant = await create_ai_assistant()
        >>> result = await assistant.process_request(task_request)
    """
    # Initialize all system components
    components = await initialize_system(settings)
    
    # Create AI Assistant with initialized components
    # AIAssistant constructor should be updated to accept components
    return AIAssistant(
        execution_engine=components.execution_engine,
        settings=settings or Settings()
    )


async def create_system_components(settings: Optional[Settings] = None) -> SystemComponents:
    """
    Create system components for advanced usage or testing.
    
    This function provides direct access to system components for:
    - Advanced integrations that need component-level control
    - Testing scenarios that need to mock specific components
    - Custom applications that want to build their own orchestration
    
    Args:
        settings: Optional application settings
        
    Returns:
        SystemComponents: All initialized system components
        
    Example:
        >>> components = await create_system_components()
        >>> result = await components.execution_engine.execute_task(task_request)
    """
    return await initialize_system(settings)


async def health_check_system(components: SystemComponents) -> dict:
    """
    Perform comprehensive system health check.
    
    Args:
        components: System components to check
        
    Returns:
        dict: Health status of all components
    """
    health_status = {
        "overall_status": "healthy",
        "components": {}
    }
    
    try:
        # Framework registry health
        available_frameworks = await components.framework_registry.get_available_frameworks()
        health_status["components"]["framework_registry"] = {
            "status": "healthy",
            "available_frameworks": [fw.value for fw in available_frameworks]
        }
        
        # Tool service health (if enabled)
        if components.tool_service:
            tool_health = await components.tool_service.health_check()
            health_status["components"]["tool_service"] = tool_health
        
        # Agent manager health  
        agent_count = len(await components.agent_manager.list_agents())
        health_status["components"]["agent_manager"] = {
            "status": "healthy",
            "active_agents": agent_count
        }
        
    except Exception as e:
        health_status["overall_status"] = "unhealthy"
        health_status["error"] = str(e)
    
    return health_status
```

## Integration Points

### AIAssistant Integration

The `AIAssistant` class should be updated to use the bootstrap system:

```python
# ai_assistant.py modifications
class AIAssistant:
    def __init__(self, execution_engine: ExecutionEngine, settings: Optional[Settings] = None):
        """Initialize with pre-initialized execution engine."""
        self.execution_engine = execution_engine
        self.settings = settings or Settings()
    
    @classmethod
    async def create(cls, settings: Optional[Settings] = None) -> "AIAssistant":
        """Alternative constructor using bootstrap."""
        from ..bootstrap import create_ai_assistant
        return await create_ai_assistant(settings)
```

### Main Entry Point Integration

```python
# main.py modifications
async def main() -> None:
    """Main application entry point using bootstrap."""
    from aether_frame.bootstrap import create_ai_assistant
    
    # Load configuration
    settings = Settings()
    
    # Setup logging
    logging.basicConfig(level=getattr(logging, settings.log_level))
    logger = logging.getLogger(__name__)
    
    # Initialize AI Assistant using bootstrap
    assistant = await create_ai_assistant(settings)
    
    # Rest of application logic...
```

## Component Dependencies & Initialization Order

### Phase 1: Framework Foundation
- **FrameworkRegistry**: Creates and registers framework adapters
- **ADK Runtime**: Automatically initialized when ADK adapter is loaded
  - InMemorySessionService creation
  - Root Agent creation through AgentManager delegation  
  - ADK Runner instantiation with Root Agent

### Phase 2: Service Layer (Optional)
- **ToolService**: Tool discovery and registration (if enabled)
  - Builtin tools registration
  - MCP tools discovery (if configured)
  - ADK native tools loading (if configured)

### Phase 3: Agent Management
- **AgentManager**: Agent factory registration and lifecycle management
- **Agent Factories**: Registration of framework-specific agent creation functions

### Phase 4: Execution Layer  
- **TaskRouter**: Task analysis and strategy selection logic
- **ExecutionEngine**: Central orchestration using initialized components

## Error Handling & Graceful Degradation

### Initialization Failures
- **Critical Components**: Framework registry, execution engine failures cause startup failure
- **Optional Components**: Tool service, specific framework adapter failures logged but don't break startup
- **Partial Functionality**: System can operate with reduced capabilities (e.g., without tools or specific frameworks)

### ADK-Specific Error Handling
- **ADK Unavailable**: System continues with other frameworks (future AutoGen/LangGraph)
- **ADK Misconfiguration**: Detailed error messages for debugging
- **Runtime Errors**: Proper exception propagation with context

## Configuration Options

### Bootstrap Configuration
```python
# settings.py additions
class Settings(BaseSettings):
    # Bootstrap options
    enable_tool_service: bool = Field(default=True, env="ENABLE_TOOL_SERVICE")
    enable_mcp_tools: bool = Field(default=False, env="ENABLE_MCP_TOOLS") 
    enable_adk_native_tools: bool = Field(default=False, env="ENABLE_ADK_NATIVE_TOOLS")
    
    # Framework preferences
    preferred_frameworks: List[str] = Field(default=["adk"], env="PREFERRED_FRAMEWORKS")
    framework_timeout: int = Field(default=30, env="FRAMEWORK_TIMEOUT")
```

## Testing Integration

### Unit Testing
```python
# Test support for component isolation
async def test_individual_components():
    components = await create_system_components()
    # Test individual components with mocked dependencies
```

### Integration Testing  
```python
# Test full system initialization
async def test_full_system_bootstrap():
    assistant = await create_ai_assistant()
    health = await health_check_system(assistant._components)
    assert health["overall_status"] == "healthy"
```

## Future Extensions

### Infrastructure Layer Integration
When infrastructure components are needed:
```python
# Future extension point in bootstrap.py
async def _initialize_infrastructure(settings: Settings) -> InfrastructureComponents:
    """Initialize infrastructure components when needed."""
    # Session management, storage, monitoring, etc.
    pass
```

### Additional Framework Support
```python
# Future framework support
async def _register_autogen_agent_factory(agent_manager: AgentManager):
    """Register AutoGen agent factory when AutoGen support is added."""
    pass
```

## Summary

This bootstrap design provides:

1. **Single Point of Control**: All initialization logic in one place
2. **Proper Dependency Management**: Components initialized in correct order
3. **Clean External Interface**: Simple `create_ai_assistant()` for most use cases
4. **Advanced Access**: `create_system_components()` for complex scenarios
5. **ADK Runtime Handled**: Leverages existing `AdkFrameworkAdapter.initialize()`
6. **Future Ready**: Extensible for infrastructure and additional frameworks
7. **Error Resilient**: Graceful degradation and comprehensive error handling

The system remains simple while providing all necessary functionality for current needs and future growth.