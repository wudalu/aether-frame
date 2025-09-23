# -*- coding: utf-8 -*-
"""ADK Framework Adapter Implementation."""

import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional, Tuple
from datetime import datetime

from ...contracts import (
    AgentConfig,
    ExecutionContext,
    FrameworkType,
    LiveExecutionResult,
    TaskChunkType,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskStreamChunk,
)
from ...execution.task_router import ExecutionStrategy
from ..base.framework_adapter import FrameworkAdapter
from .live_communicator import AdkLiveCommunicator

if TYPE_CHECKING:
    # ADK imports for type checking only
    try:
        from google.adk.agents.run_config import RunConfig
        from google.adk.events import Event as AdkEvent
        from google.adk.runners import InMemoryRunner, LiveRequestQueue
        from google.adk.sessions import Session
    except ImportError:
        InMemoryRunner = Any
        LiveRequestQueue = Any
        Session = Any
        RunConfig = Any
        AdkEvent = Any

    # Internal type imports
    from ...agents.adk.adk_domain_agent import AdkDomainAgent


class AdkFrameworkAdapter(FrameworkAdapter):
    """
    Framework adapter for Google Cloud Agent Development Kit (ADK).

    Provides integration with ADK's agent execution, memory management,
    and observability features through the unified framework interface.
    """

    def __init__(self):
        """Initialize ADK framework adapter."""
        self._initialized = False
        self._config = {}
        self._client = None
        
        # Runner Manager for correct session lifecycle
        from .runner_manager import RunnerManager
        self.runner_manager = RunnerManager()
        
        self._adk_available = False  # Initialize availability flag
        self.logger = logging.getLogger(__name__)

    @property
    def framework_type(self) -> FrameworkType:
        """Return ADK framework type."""
        return FrameworkType.ADK
    
    def _get_default_user_id(self) -> str:
        """Get default user ID from settings or fallback."""
        if hasattr(self, 'runner_manager') and hasattr(self.runner_manager, 'settings'):
            return self.runner_manager.settings.default_user_id
        return "anonymous"
    
    def _get_default_agent_type(self) -> str:
        """Get default agent type from settings or fallback.""" 
        if hasattr(self, 'runner_manager') and hasattr(self.runner_manager, 'settings'):
            return self.runner_manager.settings.default_agent_type
        return "adk_domain_agent"
    
    def _get_default_adk_model(self) -> str:
        """Get default ADK model from settings or fallback."""
        if hasattr(self, 'runner_manager') and hasattr(self.runner_manager, 'settings'):
            return self.runner_manager.settings.default_adk_model
        return "gemini-1.5-flash"
    
    def _get_domain_agent_prefix(self) -> str:
        """Get domain agent ID prefix from settings or fallback."""
        if hasattr(self, 'runner_manager') and hasattr(self.runner_manager, 'settings'):
            return self.runner_manager.settings.domain_agent_id_prefix
        return "temp_domain_agent"

    # === Core Interface Methods ===

    async def initialize(self, config: Optional[Dict[str, Any]] = None, tool_service = None, settings = None):
        """
        Initialize ADK framework adapter with strong dependency checking.

        ADK is a core framework dependency. If initialization fails,
        the entire system should fail to start.

        Args:
            config: ADK-specific configuration including project, location, etc.
            tool_service: Tool service instance for tool integration
            settings: Application settings for configuration

        Raises:
            RuntimeError: If ADK dependencies are not available or initialization fails
        """
        self.logger.info(f"ADK adapter initialization started - config_provided: {config is not None}")
        self._config = config or {}
        self._tool_service = tool_service
        
        # Re-initialize RunnerManager with settings if provided
        if settings:
            from .runner_manager import RunnerManager
            self.runner_manager = RunnerManager(settings)

        # Strong dependency check - ADK must be available
        try:
            # Test ADK availability by importing required components
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService

            # ADK is available
            self._adk_available = True
            self._initialized = True
            self.logger.info("ADK dependencies verified - Runner and InMemorySessionService available")

        except ImportError as e:
            # ADK is a core dependency - system should not start without it
            error_msg = f"ADK framework is required but not available. Please install ADK dependencies: {str(e)}"
            self.logger.error(f"ADK dependency check failed - {error_msg}")
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Failed to initialize ADK framework: {str(e)}"
            self.logger.error(f"ADK initialization failed - {error_msg}")
            raise RuntimeError(error_msg)

    async def execute_task(
        self, task_request: TaskRequest, strategy: ExecutionStrategy
    ) -> TaskResult:
        """
        Execute a task using RunnerManager for correct Runner-Session lifecycle.

        NEW Correct Flow:
        1. Check if TaskRequest has session_id (existing session) or agent_config (new session)
        2. Use RunnerManager to get/create Runner and Session
        3. Execute task in the ADK Session
        4. Return TaskResult with session_id for future requests

        Args:
            task_request: The universal task request
            strategy: Execution strategy containing framework type and execution mode

        Returns:
            TaskResult: The result with session_id for follow-up requests
        """
        self.logger.info(f"ADK task execution started - task_id: {task_request.task_id}, has_session_id: {bool(task_request.session_id)}")

        try:
            runner_context = None
            session_id = None
            adk_session = None

            if task_request.session_id:
                # Existing session - find Runner by session_id
                self.logger.info(f"Using existing session: {task_request.session_id}")
                runner_context = await self.runner_manager.get_runner_by_session(task_request.session_id)
                
                if not runner_context:
                    return TaskResult(
                        task_id=task_request.task_id,
                        status=TaskStatus.ERROR,
                        error_message=f"Session {task_request.session_id} not found",
                    )
                
                session_id = task_request.session_id
                adk_session = runner_context["sessions"].get(session_id)
                
                if not adk_session:
                    return TaskResult(
                        task_id=task_request.task_id,
                        status=TaskStatus.ERROR,
                        error_message=f"ADK Session {session_id} not found in Runner",
                    )
                    
            else:
                # New session - create Runner if needed
                if not task_request.agent_config:
                    return TaskResult(
                        task_id=task_request.task_id,
                        status=TaskStatus.ERROR,
                        error_message="No session_id or agent_config provided for new session",
                    )
                
                self.logger.info(f"Creating new session for agent_type: {task_request.agent_config.agent_type}")
                
                # Create domain agent first to get its ADK agent
                domain_agent = await self._create_domain_agent_for_config(task_request.agent_config, task_request)
                
                # Get the ADK agent from domain agent
                await domain_agent._create_adk_agent()
                adk_agent = domain_agent.adk_agent
                
                # Pass domain agent's ADK agent to RunnerManager
                runner_id, session_id = await self.runner_manager.get_or_create_runner(task_request.agent_config, task_request, adk_agent)
                
                runner_context = self.runner_manager.runners[runner_id]
                adk_session = runner_context["sessions"][session_id]
                
                # Store domain agent for this session
                if not hasattr(self, '_session_agents'):
                    self._session_agents = {}
                self._session_agents[session_id] = domain_agent
                
                self.logger.info(f"Created session {session_id} in runner {runner_id}")

            # Execute task through domain agent (correct architectural flow)
            result = await self._execute_with_domain_agent(task_request, session_id, runner_context)
            
            # Ensure session_id is included in result
            result.session_id = session_id
            result.metadata = result.metadata or {}
            result.metadata.update({"framework": "adk", "session_id": session_id})
            
            self.logger.info(f"Task execution completed - task_id: {task_request.task_id}, session_id: {session_id}, status: {result.status.value if result.status else 'unknown'}")
            return result

        except Exception as e:
            self.logger.error(f"ADK task execution failed - task_id: {task_request.task_id}, error: {str(e)}")
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"ADK execution failed: {str(e)}",
                session_id=task_request.session_id,  # Keep original session_id if any
            )


    async def _execute_with_domain_agent(
        self, task_request: TaskRequest, session_id: str, runner_context: Dict[str, Any]
    ) -> TaskResult:
        """
        Execute task through domain agent with proper session_id propagation.
        
        This creates an AgentRequest with session_id and forwards to the ADK domain agent,
        following the correct execution chain architecture.
        
        Args:
            task_request: Original task request
            session_id: Session ID for this execution
            runner_context: Runner context from RunnerManager
            
        Returns:
            TaskResult: Result from domain agent execution
        """
        try:
            # Import contracts
            from ...contracts import AgentRequest, FrameworkType
            
            # Create comprehensive runtime context for domain agent
            runtime_context = {
                # RunnerManager context
                "runner": runner_context.get("runner"),
                "session_service": runner_context.get("session_service"),
                "adk_session": runner_context.get("sessions", {}).get(session_id),
                "user_id": runner_context.get("user_id", self._get_default_user_id()),
                
                # Session and framework context
                "session_id": session_id,
                "framework_type": FrameworkType.ADK,
                "tool_service": getattr(self, '_tool_service', None),
                
                # Additional context from runner
                "agent_config": runner_context.get("agent_config"),
                "runner_context": runner_context
            }
            
            # Create AgentRequest with session_id for domain agent
            agent_request = AgentRequest(
                agent_type=self._get_default_agent_type(),
                framework_type=FrameworkType.ADK,
                task_request=task_request,
                session_id=session_id,  # Ensure session_id propagates to domain agent
                runtime_options=runtime_context
            )
            
            # Get or create domain agent for this session
            domain_agent = await self._get_domain_agent_for_session(session_id, runner_context, runtime_context)
            
            # Execute through domain agent
            result = await domain_agent.execute(agent_request)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Domain agent execution failed - session_id: {session_id}, error: {str(e)}")
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"Domain agent execution failed: {str(e)}",
                session_id=session_id
            )

    async def _get_domain_agent_for_session(
        self, session_id: str, runner_context: Dict[str, Any], runtime_context: Dict[str, Any] = None
    ) -> "AdkDomainAgent":
        """
        Get or create domain agent for session with proper runtime context.
        
        Args:
            session_id: Session identifier
            runner_context: Runtime context from RunnerManager
            runtime_context: Additional runtime context for domain agent
            
        Returns:
            AdkDomainAgent: Domain agent for this session
        """
        # Initialize session agents cache if not exists
        if not hasattr(self, '_session_agents'):
            self._session_agents = {}
        
        # Check if we already have a domain agent for this session
        if session_id in self._session_agents:
            # Update runtime context with latest runner context
            existing_agent = self._session_agents[session_id]
            
            # Update with provided runtime context or create new one
            updated_context = runtime_context or {
                "runner": runner_context.get("runner"),
                "session_service": runner_context.get("session_service"),
                "session_id": session_id,
                "user_id": runner_context.get("user_id", self._get_default_user_id()),
                "adk_session": runner_context.get("sessions", {}).get(session_id),
                "framework_type": FrameworkType.ADK,
                "tool_service": getattr(self, '_tool_service', None)
            }
            
            existing_agent.runtime_context.update(updated_context)
            return existing_agent
        
        # Create new domain agent with runtime context
        from ...agents.adk.adk_domain_agent import AdkDomainAgent
        
        # Extract agent config from runner context if available
        agent_config = runner_context.get("agent_config")
        if agent_config:
            config_dict = {
                "agent_type": agent_config.agent_type,
                "system_prompt": getattr(agent_config, 'system_prompt', "You are a helpful AI assistant."),
                "model": getattr(agent_config, 'model_config', {}).get('model', self._get_default_adk_model())
            }
        else:
            # Fallback configuration
            config_dict = {
                "agent_type": self._get_default_agent_type(),
                "system_prompt": "You are a helpful AI assistant.",
                "model": self._get_default_adk_model()
            }
        
        # Use provided runtime context or create new one
        final_runtime_context = runtime_context or {
            "framework_type": FrameworkType.ADK,
            "session_id": session_id,
            "runner": runner_context.get("runner"),
            "session_service": runner_context.get("session_service"),
            "adk_session": runner_context.get("sessions", {}).get(session_id),
            "user_id": runner_context.get("user_id", self._get_default_user_id()),
            "tool_service": getattr(self, '_tool_service', None)
        }
        
        # Create domain agent
        domain_agent = AdkDomainAgent(
            agent_id=f"adk_agent_{session_id}",
            config=config_dict,
            runtime_context=final_runtime_context
        )
        
        # Initialize domain agent
        await domain_agent.initialize()
        
        # Store for future use
        self._session_agents[session_id] = domain_agent
        
        return domain_agent

    async def _create_domain_agent_for_config(
        self, agent_config: AgentConfig, task_request: TaskRequest = None
    ) -> "AdkDomainAgent":
        """
        Create a new domain agent for given configuration without session binding.
        
        This is used during the new session creation flow to create the domain agent first,
        get its ADK agent, and then pass that to RunnerManager.
        
        Args:
            agent_config: Agent configuration
            task_request: Optional task request for additional context
            
        Returns:
            AdkDomainAgent: Newly created domain agent
        """
        from ...agents.adk.adk_domain_agent import AdkDomainAgent
        
        # Build config dict from agent_config
        config_dict = {
            "agent_type": agent_config.agent_type,
            "system_prompt": getattr(agent_config, 'system_prompt', "You are a helpful AI assistant."),
            "model": getattr(agent_config, 'model_config', {}).get('model', self._get_default_adk_model())
        }
        
        # Create basic runtime context
        runtime_context = {
            "framework_type": FrameworkType.ADK,
            "tool_service": getattr(self, '_tool_service', None),
            "agent_config": agent_config,
            "task_request": task_request
        }
        
        # Create domain agent with configurable ID prefix
        domain_agent = AdkDomainAgent(
            agent_id=f"{self._get_domain_agent_prefix()}_{task_request.task_id if task_request else 'unknown'}",
            config=config_dict,
            runtime_context=runtime_context
        )
        
        # Initialize domain agent
        await domain_agent.initialize()
        
        return domain_agent

    async def _execute_tool(self, tool_call) -> Any:
        """
        Execute tool call (placeholder implementation).
        
        Args:
            tool_call: Tool call from ADK
            
        Returns:
            Tool execution result
        """
        # TODO: Integrate with ToolService
        self.logger.info(f"Tool call: {getattr(tool_call, 'name', 'unknown')}")
        return {"result": "mock_tool_result"}

    async def execute_task_live(
        self, task_request: TaskRequest, context: ExecutionContext
    ) -> LiveExecutionResult:
        """
        Execute a task in live/interactive mode.

        TODO: This method needs to be updated to use RunnerManager pattern 
        instead of legacy session management. Currently commented out to avoid 
        breaking changes during Phase 1 cleanup.

        Args:
            task_request: The universal task request
            context: Execution context with user and session information (unused currently)

        Returns:
            LiveExecutionResult: Tuple of (event_stream, communicator)
        """
        # TODO: Implement live execution using RunnerManager pattern
        # This requires integration with agents/adk/ code which will be done separately
        
        async def placeholder_stream():
            yield TaskStreamChunk(
                task_id=task_request.task_id,
                chunk_type=TaskChunkType.ERROR,
                sequence_id=0,
                content="Live execution temporarily disabled during refactoring",
                is_final=True,
                metadata={"error_type": "not_implemented", "framework": "adk"},
            )

        # Create null communicator for placeholder
        class PlaceholderCommunicator:
            def send_user_response(self, approved: bool):
                """Placeholder implementation."""
                pass

            def send_user_message(self, message: str):
                """Placeholder implementation."""
                pass

            def send_cancellation(self, reason: str):
                """Placeholder implementation."""
                pass

            def close(self):
                pass

        return (placeholder_stream(), PlaceholderCommunicator())

    def is_ready(self) -> bool:
        """
        Check if ADK adapter is ready for task execution.

        Unlike availability checking, this verifies the adapter is properly
        initialized and ready to handle tasks.

        Returns:
            bool: True if adapter is ready for execution
        """
        return self._initialized and self._adk_available

    # FIXME: 如我们一开始设计，这个应该是返回配置
    async def get_capabilities(self) -> List[str]:
        """Get ADK framework capabilities."""
        return [
            "conversational_agents",
            "memory_management",
            "observability",
            "tool_integration",
            "session_management",
            "state_persistence",
        ]

    async def health_check(self) -> Dict[str, Any]:
        """Perform ADK framework health check."""
        return {
            "framework": "adk",
            "status": "healthy" if self._initialized else "not_initialized",
            "version": "1.0.0",  # TODO: Get actual ADK version
            "capabilities": await self.get_capabilities(),
            "active_sessions": len(self.runner_manager.runners),
        }

    async def shutdown(self):
        """Shutdown ADK framework adapter and RunnerManager."""
        # Cleanup RunnerManager sessions
        if hasattr(self.runner_manager, 'cleanup_all'):
            await self.runner_manager.cleanup_all()
        
        # No global session service to cleanup (each session has its own)
        self._initialized = False

    # === Session Management ===

    def _extract_session_id(self, task_request: TaskRequest) -> str:
        """
        Extract session_id from task request with proper user isolation and descriptive context.

        CRITICAL: Session ID must include user_id to ensure proper multi-user isolation.
        Multiple users should NEVER share the same session, even if they provide
        the same session_context.session_id.

        Enhanced Session ID format: "{user_id}:{framework_type}_{test_framework}_{test_case}" 
        Fallback format: "{user_id}:{session_id}" or "{user_id}:default"

        Args:
            task_request: Task request containing session context and metadata

        Returns:
            str: User-isolated, descriptive session ID
        """
        # Extract user_id (required for isolation) - MUST come from request
        user_id = None
        if task_request.user_context:
            user_id = task_request.user_context.get_adk_user_id()
        
        # Only use fallback if no user context provided
        if not user_id:
            user_id = self._get_default_user_id()

        # Try to build descriptive session_id from metadata first
        base_session_id = None
        if task_request.metadata:
            framework_type = task_request.metadata.get("framework_type")
            test_framework = task_request.metadata.get("test_framework") 
            test_case = task_request.metadata.get("test_case")
            
            # Build descriptive session ID if we have framework context
            if framework_type and test_framework:
                session_parts = [framework_type, test_framework]
                if test_case:
                    session_parts.append(test_case)
                base_session_id = "_".join(session_parts)

        # Fallback to explicit session_id if no metadata context
        if not base_session_id and task_request.session_context and hasattr(
            task_request.session_context, "session_id"
        ):
            base_session_id = task_request.session_context.session_id

        # If no explicit session_id, use default
        if not base_session_id:
            base_session_id = "default"

        # CRITICAL: Always prefix with user_id for proper isolation
        isolated_session_id = f"{user_id}:{base_session_id}"

        return isolated_session_id

    # === Context and Configuration Helpers ===

    def _convert_contexts_to_session_config(
        self, task_request: TaskRequest
    ) -> Dict[str, Any]:
        """
        Convert TaskRequest contexts to comprehensive ADK Session configuration.

        CURRENT STATUS: Used by session management methods in framework adapter.
        This is correctly placed as it handles ADK-specific session creation.

        Builds complete initial state by integrating all context information:
        user preferences, session history, execution metadata, and knowledge sources.

        Args:
            task_request: The task request containing multiple contexts

        Returns:
            Dict containing comprehensive session configuration
        """
        # Build comprehensive initial state integrating all contexts
        initial_state = {
            # Core task information
            "task_id": task_request.task_id,
            "task_type": task_request.task_type,
            "task_description": task_request.description or "",
        }

        # User context integration
        if task_request.user_context:
            user_context = task_request.user_context
            initial_state.update(
                {
                    "user_id": user_context.user_id,
                    "user_name": getattr(user_context, "user_name", ""),
                }
            )

            # User preferences with prefix to avoid conflicts
            user_prefs = getattr(user_context, "preferences", None)
            if user_prefs:
                initial_state.update(
                    {f"user_pref_{k}": v for k, v in user_prefs.items()}
                )

            # User permissions for tool access control
            user_permissions = getattr(user_context, "permissions", None)
            if user_permissions:
                initial_state["user_permissions"] = user_permissions

        # Session context integration
        if task_request.session_context:
            session_ctx = task_request.session_context
            initial_state.update(
                {
                    "session_id": session_ctx.session_id,
                }
            )

            # Existing session state (safely)
            if hasattr(session_ctx, "session_state") and session_ctx.session_state:
                initial_state.update(session_ctx.session_state)

            # Conversation history for context continuity
            if (
                hasattr(session_ctx, "conversation_history")
                and session_ctx.conversation_history
            ):
                initial_state["conversation_history"] = [
                    {"role": msg.role, "content": msg.content}
                    for msg in session_ctx.conversation_history
                ]

            # Session context variables (safely)
            context_vars = getattr(session_ctx, "context_variables", None)
            if context_vars:
                initial_state.update(
                    {f"session_{k}": v for k, v in context_vars.items()}
                )

        # Execution context integration
        if task_request.execution_context:
            exec_ctx = task_request.execution_context
            initial_state.update(
                {
                    "execution_id": exec_ctx.execution_id,
                    "trace_id": exec_ctx.trace_id or "",
                    "execution_mode": exec_ctx.execution_mode,
                    # Execution metadata
                    **{f"exec_{k}": v for k, v in exec_ctx.metadata.items()},
                }
            )

        # Knowledge sources integration
        if task_request.available_knowledge:
            initial_state["knowledge_sources"] = [
                {
                    "id": kb.knowledge_id,
                    "type": kb.knowledge_type,
                    "source": kb.source,
                    "metadata": kb.metadata,
                }
                for kb in task_request.available_knowledge
            ]

        # Task metadata integration
        if task_request.metadata:
            initial_state.update(
                {f"meta_{k}": v for k, v in task_request.metadata.items()}
            )

        # Extract core session parameters with proper user isolation - MUST come from request
        user_id = None
        if task_request.user_context:
            user_id = task_request.user_context.get_adk_user_id()
        
        # Only use fallback if no user context provided
        if not user_id:
            user_id = self._get_default_user_id()

        # Use our extracted session_id (already includes user isolation)
        isolated_session_id = self._extract_session_id(task_request)

        return {
            "app_name": f"aether_frame_{task_request.task_id}",
            "user_id": user_id,
            "session_id": isolated_session_id,  # User-isolated session_id
            "initial_state": initial_state,
        }

    def _build_agent_config_from_task(
        self, task_request: TaskRequest, strategy: Optional[ExecutionStrategy]
    ) -> AgentConfig:
        """
        Build agent configuration from task request and execution strategy.

        This method creates a comprehensive agent configuration by extracting
        relevant information from the task request and applying framework-specific
        optimizations based on the execution strategy.

        Args:
            task_request: Universal task request with context information
            strategy: Execution strategy with framework and mode information (unused currently)

        Returns:
            AgentConfig: Complete configuration for agent creation
        """
        # Note: strategy parameter currently unused but kept for future extensibility
        # Build agent configuration based on task requirements
        return AgentConfig(
            framework_type=self.framework_type,
            agent_type=task_request.task_type or "conversational_agent",
            name=f"task_agent_{task_request.task_id}",
            description=f"ADK agent for task {task_request.task_id}",
            model_config={
                "model": self._extract_model_configuration(task_request),
                "temperature": task_request.metadata.get("temperature", 0.7),
                "max_tokens": task_request.metadata.get("max_tokens", 1000),
            },
            capabilities=task_request.metadata.get("required_capabilities", []),
            system_prompt=self._build_system_prompt_from_task(task_request),
            tool_permissions=self._extract_tool_permissions(task_request),
            memory_config=task_request.metadata.get("memory_config", {}),
            max_iterations=task_request.metadata.get("max_iterations", 20),
            timeout=task_request.metadata.get("timeout", 300),
        )

    def _extract_model_configuration(self, task_request: TaskRequest) -> str:
        """
        Extract model configuration from task request and execution config.

        Priority order:
        1. execution_config.model
        2. task metadata model
        3. user preferences model
        4. default model
        """
        # Check execution config first
        if (
            task_request.execution_config
            and isinstance(task_request.execution_config, dict)
            and task_request.execution_config.get("model")
        ):
            return task_request.execution_config["model"]

        # Check task metadata
        if task_request.metadata and task_request.metadata.get("preferred_model"):
            return task_request.metadata["preferred_model"]

        # Check user preferences
        if (
            task_request.user_context
            and hasattr(task_request.user_context, "preferences")
            and task_request.user_context.preferences.get("preferred_model")
        ):
            return task_request.user_context.preferences["preferred_model"]

        # FIXME: need to align with our model
        # Default model based on task type
        task_type_models = {
            "coding": "gpt-4o",
            "analysis": "gpt-4o",
            "creative": "gpt-4.1",
            "chat": "gpt-4.1",
        }

        return task_type_models.get(task_request.task_type, "gpt-4o")
