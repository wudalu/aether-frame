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
        # Session-based agent management following ADK architecture
        self._session_agents: Dict[str, "AdkDomainAgent"] = {}
        # Session contexts - each session has independent session service, runner, and ADK session
        self._session_contexts: Dict[str, Dict[str, Any]] = {}
        self._adk_available = False  # Initialize availability flag
        self.logger = logging.getLogger(__name__)

    @property
    def framework_type(self) -> FrameworkType:
        """Return ADK framework type."""
        return FrameworkType.ADK

    # === Core Interface Methods ===

    async def initialize(self, config: Optional[Dict[str, Any]] = None, tool_service = None):
        """
        Initialize ADK framework adapter with strong dependency checking.

        ADK is a core framework dependency. If initialization fails,
        the entire system should fail to start.

        Args:
            config: ADK-specific configuration including project, location, etc.
            tool_service: Tool service instance for tool integration

        Raises:
            RuntimeError: If ADK dependencies are not available or initialization fails
        """
        self.logger.info(f"ADK adapter initialization started - config_provided: {config is not None}")
        self._config = config or {}
        self._tool_service = tool_service

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
        Execute a task through session-based ADK domain agent coordination.

        Session-based execution flow:
        1. Extract session_id from task request
        2. Get or create ADK domain agent for the session
        3. Execute task through persistent session agent
        4. Return result (agent persists for future tasks in same session)

        Args:
            task_request: The universal task request
            strategy: Execution strategy containing framework type and execution mode

        Returns:
            TaskResult: The result of task execution
        """
        # Bootstrap ensures adapter is always initialized
        session_id = self._extract_session_id(task_request)
        self.logger.info(f"ADK task execution started - task_id: {task_request.task_id}, session_id: {session_id}")

        try:
            # Get or create domain agent for this session
            domain_agent = await self._get_or_create_session_agent(
                session_id, task_request, strategy
            )
            self.logger.info(f"Domain agent ready - session_id: {session_id}, agent_type: {type(domain_agent).__name__ if domain_agent else 'None'}")

            # Execute task through persistent session agent
            # Convert TaskRequest to AgentRequest as required by domain agent
            agent_request = self._convert_task_to_agent_request(task_request, strategy)
            
            # Log execution chain data
            from ...common.unified_logging import create_execution_context
            exec_context = create_execution_context(f"adk_{task_request.task_id}")
            exec_context.log_execution_chain({
                "task_request": {
                    "task_id": task_request.task_id,
                    "task_type": task_request.task_type,
                    "session_id": session_id
                },
                "agent_request": {
                    "agent_type": agent_request.agent_type,
                    "framework_type": agent_request.framework_type.value if agent_request.framework_type else None
                }
            })
            
            task_result = await domain_agent.execute(agent_request)
            
            result_status = task_result.status.value if task_result and task_result.status else "unknown"
            self.logger.info(f"Domain agent execution completed - task_id: {task_request.task_id}, status: {result_status}")
            
            # Log final execution chain result
            exec_context.log_execution_chain({
                "task_result": {
                    "task_id": task_result.task_id if task_result else None,
                    "status": result_status,
                    "messages_count": len(task_result.messages) if task_result and task_result.messages else 0,
                    "has_error": bool(task_result.error_message) if task_result else False
                }
            })

            # Return result based on actual execution status
            if task_result and task_result.status == TaskStatus.SUCCESS:
                self.logger.info(f"Task execution successful - task_id: {task_request.task_id}, session_id: {session_id}")
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.SUCCESS,
                    result_data=task_result.result_data,
                    messages=task_result.messages,
                    execution_context=task_request.execution_context,
                    error_message=None,
                    metadata={"framework": "adk", "session_id": session_id},
                )
            elif task_result and task_result.status == TaskStatus.ERROR:
                self.logger.warning(f"Task execution returned error - task_id: {task_request.task_id}, error: {task_result.error_message}")
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    result_data=task_result.result_data,
                    messages=task_result.messages,
                    execution_context=task_request.execution_context,
                    error_message=task_result.error_message,
                    metadata={"framework": "adk", "session_id": session_id},
                )
            else:
                error_msg = "No result returned from domain agent"
                self.logger.error(f"No result from domain agent - task_id: {task_request.task_id}, session_id: {session_id}")
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message=error_msg,
                    metadata={"framework": "adk", "session_id": session_id},
                )

        except Exception as e:
            self.logger.error(f"ADK task execution failed - task_id: {task_request.task_id}, session_id: {session_id}, error: {str(e)}")
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"ADK execution failed: {str(e)}",
                metadata={"framework": "adk", "session_id": session_id},
            )

    async def execute_task_live(
        self, task_request: TaskRequest, context: ExecutionContext
    ) -> LiveExecutionResult:
        """
        Execute a task in live/interactive mode using session-based agent coordination.

        Session-based live execution flow:
        1. Extract session_id from task request
        2. Get or create ADK domain agent for the session
        3. Execute task in live mode through persistent session agent
        4. Return event stream and communicator for real-time interaction

        Args:
            task_request: The universal task request
            context: Execution context with user and session information (unused currently)

        Returns:
            LiveExecutionResult: Tuple of (event_stream, communicator) where:
                - event_stream: AsyncIterator[TaskStreamChunk] for real-time events
                - communicator: LiveCommunicator for bidirectional communication

        Raises:
            RuntimeError: If ADK framework not initialized or execution fails
        """
        # Note: context parameter currently unused but kept for interface compatibility
        # Bootstrap ensures adapter is always initialized
        session_id = self._extract_session_id(task_request)

        try:
            # Get or create domain agent for this session
            domain_agent = await self._get_or_create_session_agent(
                session_id, task_request, None
            )

            # Execute task in live mode through persistent session agent
            event_stream, communicator = await domain_agent.execute_live(task_request)

            # Note: Don't cleanup agent on communicator close - session agent persists
            # Session cleanup happens when session explicitly ends or framework shuts down

            return (event_stream, communicator)

        except Exception as e:

            async def error_stream():
                yield TaskStreamChunk(
                    task_id=task_request.task_id,
                    chunk_type=TaskChunkType.ERROR,
                    sequence_id=0,
                    content=f"Live execution failed: {str(e)}",
                    is_final=True,
                    metadata={"error_type": "live_execution_error", "framework": "adk"},
                )

            # Create null communicator for error case
            class ErrorCommunicator:
                def send_user_response(self, approved: bool):
                    """Null implementation - unused parameter noted."""
                    pass

                def send_user_message(self, message: str):
                    """Null implementation - unused parameter noted."""
                    pass

                def send_cancellation(self, reason: str):
                    """Null implementation - unused parameter noted."""
                    pass

                def close(self):
                    pass

            return (error_stream(), ErrorCommunicator())

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
            "active_sessions": len(self._session_contexts),
        }

    async def shutdown(self):
        """Shutdown ADK framework adapter with independent session contexts."""
        # Cleanup all session agents and their independent contexts
        if self._session_agents:
            for session_id in list(self._session_agents.keys()):
                await self._cleanup_session(session_id)

        # Additional cleanup for any remaining session contexts
        if self._session_contexts:
            for session_id, session_context in list(self._session_contexts.items()):
                try:
                    # Cleanup Runner if it has shutdown method
                    runner = session_context.get("runner")
                    if runner and hasattr(runner, "shutdown"):
                        await runner.shutdown()

                    # Cleanup ADK session
                    adk_session = session_context.get("adk_session")
                    if adk_session and hasattr(adk_session, "close"):
                        await adk_session.close()

                    # Cleanup independent session service
                    session_service = session_context.get("session_service")
                    if session_service and hasattr(session_service, "shutdown"):
                        await session_service.shutdown()

                except Exception as e:
                    print(
                        f"Warning: Failed to shutdown session context {session_id}: {str(e)}"
                    )
            self._session_contexts.clear()

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
        # Extract user_id (required for isolation)
        user_id = "anonymous"
        if task_request.user_context and hasattr(task_request.user_context, "user_id"):
            user_id = task_request.user_context.user_id

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

    async def _get_or_create_session_agent(
        self,
        session_id: str,
        task_request: TaskRequest,
        strategy: Optional[ExecutionStrategy],
    ) -> "AdkDomainAgent":
        """
        Get existing session agent or create new one following ADK architecture.

        This implements the core ADK pattern: one persistent agent per conversation session.

        Args:
            session_id: Unique session identifier
            task_request: Task request containing context and configuration
            strategy: Execution strategy (optional)

        Returns:
            AdkDomainAgent: Persistent agent for this session
        """
        # Return existing agent if available
        if session_id in self._session_agents:
            return self._session_agents[session_id]

        # Create new session agent with proper ADK configuration
        agent_config = self._build_agent_config_from_task(task_request, strategy)

        # Create ADK session using context conversion
        session_config = self._convert_contexts_to_session_config(task_request)

        # Create domain agent with session context
        domain_agent = await self._create_session_domain_agent(
            session_id, agent_config, session_config
        )

        # Store agent for session persistence
        self._session_agents[session_id] = domain_agent

        return domain_agent

    async def _create_session_domain_agent(
        self, session_id: str, agent_config: AgentConfig, session_config: Dict[str, Any]
    ) -> "AdkDomainAgent":
        """
        Create ADK domain agent with session-specific configuration.

        This creates both the domain agent and its associated ADK Runner,
        following proper ADK session management patterns.

        Args:
            session_id: Unique session identifier
            agent_config: Agent configuration
            session_config: ADK session configuration

        Returns:
            AdkDomainAgent: Initialized domain agent with Runner
        """
        try:
            from ...agents.adk.adk_domain_agent import AdkDomainAgent

            # Build runtime context for ADK execution
            # Note: runner and session_service will be added after session context creation
            runtime_context = {
                "framework_type": self.framework_type,
                "config": dict(self._config),
                "session_id": session_id,
                "session_config": session_config,
                "tool_service": self._tool_service,
            }

            # Create domain agent with session context
            domain_agent = AdkDomainAgent(
                agent_id=session_id,
                config=agent_config.__dict__,
                runtime_context=runtime_context,
            )

            # Initialize the domain agent
            await domain_agent.initialize()

            # Create Runner for this session if ADK is available
            if self._adk_available:
                await self._create_independent_session_context(
                    session_id, domain_agent, session_config
                )
            else:
                pass  # ADK not available

                # Update domain agent's runtime context with session context
                if session_id in self._session_contexts:
                    session_context = self._session_contexts[session_id]
                    domain_agent.runtime_context.update(
                        {
                            "runner": session_context["runner"],
                            "session_service": session_context["session_service"],
                            "adk_session": session_context["adk_session"],
                            "user_id": session_context["user_id"],
                            "app_name": session_context["app_name"],
                        }
                    )

            return domain_agent

        except Exception as e:
            raise RuntimeError(
                f"Failed to create ADK session domain agent {session_id}: {str(e)}"
            )

    async def _create_independent_session_context(
        self,
        session_id: str,
        domain_agent: "AdkDomainAgent",
        session_config: Dict[str, Any],
    ):
        """
        Create independent session context with dedicated session service and runner.

        Following ADK best practices, each session gets its own:
        - InMemorySessionService (完全隔离)
        - ADK Session (在独立的session service中)
        - Runner (绑定到独立的session service)

        This ensures complete isolation between concurrent sessions and eliminates
        any potential race conditions or state leakage.

        Args:
            session_id: Our session identifier (also used as ADK session_id)
            domain_agent: Domain agent for this session
            session_config: Session configuration from context conversion
        """
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService

            # Get the actual ADK agent from Domain Agent for Runner
            if not hasattr(domain_agent, "adk_agent") or not domain_agent.adk_agent:
                # Skip session context creation if ADK agent not available
                return

            # Create independent session service for this session
            session_service = InMemorySessionService()

            # Create ADK session using our session_id in the independent service
            adk_session = await session_service.create_session(
                app_name=session_config.get("app_name", "aether_frame"),
                user_id=session_config.get("user_id", "anonymous"),
                session_id=session_id,  # Use our session_id as ADK session_id
            )

            # Create session-specific Runner bound to independent session service
            runner = Runner(
                agent=domain_agent.adk_agent,
                app_name=session_config.get("app_name", "aether_frame"),
                session_service=session_service,  # 👈 独立的session service
            )

            # Store session context (LiveRequestQueue now created in agent layer)
            self._session_contexts[session_id] = {
                "runner": runner,
                "session_service": session_service,  # 每个session独立的service
                "adk_session": adk_session,
                "user_id": session_config.get("user_id", "anonymous"),
                "app_name": session_config.get("app_name", "aether_frame"),
            }
            
            # Update domain agent's runtime context immediately
            domain_agent.runtime_context.update(
                {
                    "runner": runner,
                    "session_service": session_service,
                    "adk_session": adk_session,
                    "user_id": session_config.get("user_id", "anonymous"),
                    "app_name": session_config.get("app_name", "aether_frame"),
                    "session_id": session_id,
                }
            )

        except Exception as e:
            print(
                f"Warning: Failed to create independent session context for {session_id}: {str(e)}"
            )

    async def _cleanup_session(self, session_id: str) -> bool:
        """
        Cleanup session agent and associated ADK resources.

        This properly cleans up both our session agent and the corresponding
        ADK session to ensure no resource leaks.

        Args:
            session_id: Session identifier to cleanup

        Returns:
            bool: True if cleanup successful, False otherwise
        """
        success = True

        # Cleanup domain agent
        if session_id in self._session_agents:
            try:
                agent = self._session_agents[session_id]
                await agent.cleanup()
                del self._session_agents[session_id]
            except Exception as e:
                print(
                    f"Warning: Failed to cleanup session agent {session_id}: {str(e)}"
                )
                success = False

        # Cleanup independent session context
        if session_id in self._session_contexts:
            try:
                session_context = self._session_contexts[session_id]

                # Cleanup Runner if it has shutdown method
                runner = session_context.get("runner")
                if runner and hasattr(runner, "shutdown"):
                    await runner.shutdown()

                # Cleanup ADK session
                adk_session = session_context.get("adk_session")
                if adk_session and hasattr(adk_session, "close"):
                    await adk_session.close()

                # Cleanup independent session service
                session_service = session_context.get("session_service")
                if session_service and hasattr(session_service, "shutdown"):
                    await session_service.shutdown()

                del self._session_contexts[session_id]
            except Exception as e:
                print(
                    f"Warning: Failed to cleanup session context {session_id}: {str(e)}"
                )
                success = False

        return success

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

        # Extract core session parameters with proper user isolation
        user_id = "anonymous"
        if task_request.user_context:
            user_id = task_request.user_context.get_adk_user_id()

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
            "coding": "gemini-1.5-pro",
            "analysis": "gemini-1.5-pro",
            "creative": "gemini-1.5-flash",
            "chat": "gemini-1.5-flash",
        }

        return task_type_models.get(task_request.task_type, "gemini-1.5-flash")

    def _build_system_prompt_from_task(self, task_request: TaskRequest) -> str:
        """Build system prompt from task request context."""
        instruction_parts = []

        # Base instruction based on task type
        task_type_instructions = {
            "chat": "You are a conversational AI assistant designed to help users with their questions and tasks.",
            "analysis": "You are an analytical AI assistant specialized in data analysis and insights.",
            "coding": "You are a coding AI assistant that helps with programming tasks and technical questions.",
            "creative": "You are a creative AI assistant that helps with writing, brainstorming, and creative tasks.",
        }
        base_instruction = task_type_instructions.get(
            task_request.task_type,
            f"You are an AI assistant handling {task_request.task_type} tasks.",
        )
        instruction_parts.append(base_instruction)

        # Add task-specific context
        if task_request.description:
            instruction_parts.append(f"Current task: {task_request.description}")

        return "\n\n".join(instruction_parts)

    def _extract_tool_permissions(self, task_request: TaskRequest) -> list:
        """Extract tool permissions from task request."""
        permissions = []
        if task_request.available_tools:
            permissions = [tool.name for tool in task_request.available_tools]
        return permissions
