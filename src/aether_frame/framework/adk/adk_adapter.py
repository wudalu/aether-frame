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
                print(f"[ADK Adapter] Looking for existing session: {task_request.session_id}")
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
                print(f"[ADK Adapter] Creating new session for agent_type: {task_request.agent_config.agent_type}")
                runner_id, session_id = await self.runner_manager.get_or_create_runner(task_request.agent_config, task_request)
                print(f"[ADK Adapter] Got runner_id: {runner_id}, session_id: {session_id}")
                
                runner_context = self.runner_manager.runners[runner_id]
                adk_session = runner_context["sessions"][session_id]
                
                self.logger.info(f"Created session {session_id} in runner {runner_id}")
                print(f"[ADK Adapter] Created session {session_id} in runner {runner_id}")

            # Execute task through ADK Runner directly instead of domain agent
            result = await self._execute_with_adk_runner_directly(task_request, session_id, runner_context)
            
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

    async def _execute_with_adk_runner_directly(
        self, task_request: TaskRequest, session_id: str, runner_context: Dict[str, Any]
    ) -> TaskResult:
        """
        Execute task directly using ADK Runner from RunnerManager.
        
        This bypasses the domain agent layer and uses the Runner created by RunnerManager directly,
        avoiding the session management conflicts.
        
        Args:
            task_request: Original task request
            session_id: Session ID for this execution
            runner_context: Runner context from RunnerManager
            
        Returns:
            TaskResult: Result from direct ADK Runner execution
        """
        try:
            # Get the ADK Runner and session from RunnerManager
            runner = runner_context.get("runner")
            adk_session = runner_context.get("sessions", {}).get(session_id)
            
            # Extract the user_id that was used to create this session
            user_id = runner_context.get("user_id", "anonymous")
            
            if not runner:
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message="ADK Runner not available in runner context",
                    session_id=session_id
                )
            
            if not adk_session:
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message=f"ADK Session {session_id} not found in runner context",
                    session_id=session_id
                )
            
            # Get the actual ADK session ID (might be different from our session_id)
            actual_adk_session_id = getattr(adk_session, 'id', session_id)
            
            print(f"[ADK Adapter] Executing directly with ADK Runner, session_id: {session_id}, adk_session_id: {actual_adk_session_id}, user_id: {user_id}")
            
            # Convert messages to ADK format
            if task_request.messages:
                # Use the first message for now
                user_message = task_request.messages[0].content
            else:
                user_message = task_request.description or "Hello"
            
            # Import ADK types for content creation
            from google.genai import types
            
            # Create ADK content
            content = types.Content(role="user", parts=[types.Part(text=user_message)])
            
            # Execute through ADK Runner directly using the actual ADK session ID
            print(f"[ADK Adapter] Calling runner.run_async with user_id: {user_id}, session_id: {actual_adk_session_id}")
            events = runner.run_async(
                user_id=user_id,  # Use the same user_id that was used to create the session
                session_id=actual_adk_session_id,  # Use the actual ADK session ID
                new_message=content
            )
            
            # Process events to get response
            all_responses = []
            async for event in events:
                if event.content:
                    # Extract text from parts
                    if hasattr(event.content, 'parts') and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                text = part.text.strip()
                                if text and len(text) > 10:
                                    all_responses.append({
                                        'text': text,
                                        'is_final': event.is_final_response(),
                                        'length': len(text)
                                    })
                    
                    # Extract text directly from content
                    if hasattr(event.content, 'text') and event.content.text:
                        text = event.content.text.strip()
                        if text and len(text) > 10:
                            all_responses.append({
                                'text': text,
                                'is_final': event.is_final_response(),
                                'length': len(text)
                            })
            
            # Select best response
            if all_responses:
                # Sort by length and prefer final responses
                best_response = max(all_responses, key=lambda r: (r['is_final'], r['length']))
                response_text = best_response['text']
                
                # Create response message
                from ...contracts import UniversalMessage
                response_message = UniversalMessage(
                    role="assistant",
                    content=response_text,
                    metadata={"framework": "adk", "session_id": session_id}
                )
                
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.SUCCESS,
                    messages=[response_message],
                    session_id=session_id,
                    metadata={"framework": "adk", "execution_method": "direct_runner"}
                )
            else:
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message="No response received from ADK Runner",
                    session_id=session_id
                )
                
        except Exception as e:
            self.logger.error(f"Direct ADK Runner execution failed - session_id: {session_id}, error: {str(e)}")
            print(f"[ADK Adapter] Direct execution failed: {str(e)}")
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"ADK Runner execution failed: {str(e)}",
                session_id=session_id
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
            
            # Create AgentRequest with session_id for domain agent
            agent_request = AgentRequest(
                agent_type="adk_domain_agent",
                framework_type=FrameworkType.ADK,
                task_request=task_request,
                session_id=session_id,  # Ensure session_id propagates to domain agent
                runtime_options={
                    "runner_context": runner_context,
                    "session_id": session_id
                }
            )
            
            # Get or create domain agent for this session
            domain_agent = await self._get_domain_agent_for_session(session_id, runner_context)
            
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
        self, session_id: str, runner_context: Dict[str, Any]
    ) -> "AdkDomainAgent":
        """
        Get or create domain agent for session with proper runtime context.
        
        Args:
            session_id: Session identifier
            runner_context: Runtime context from RunnerManager
            
        Returns:
            AdkDomainAgent: Domain agent for this session
        """
        # Check if we already have a domain agent for this session
        if session_id in self._session_agents:
            # Update runtime context with latest runner context
            existing_agent = self._session_agents[session_id]
            existing_agent.runtime_context.update({
                "runner": runner_context.get("runner"),
                "session_service": runner_context.get("session_service"),
                "session_id": session_id,
                "user_id": runner_context.get("user_id", "anonymous"),
                "adk_session": runner_context.get("sessions", {}).get(session_id)
            })
            return existing_agent
        
        # Create new domain agent with runtime context
        from ...agents.adk.adk_domain_agent import AdkDomainAgent
        
        # Extract agent config from runner context if available
        agent_config = runner_context.get("agent_config")
        if agent_config:
            config_dict = {
                "agent_type": agent_config.agent_type,
                "system_prompt": getattr(agent_config, 'system_prompt', "You are a helpful AI assistant."),
                "model": getattr(agent_config, 'model_config', {}).get('model', 'gemini-1.5-flash')
            }
        else:
            # Fallback configuration
            config_dict = {
                "agent_type": "adk_domain_agent",
                "system_prompt": "You are a helpful AI assistant.",
                "model": "gemini-1.5-flash"
            }
        
        # Create runtime context with session data from RunnerManager
        runtime_context = {
            "framework_type": FrameworkType.ADK,
            "session_id": session_id,
            "runner": runner_context.get("runner"),
            "session_service": runner_context.get("session_service"),
            "adk_session": runner_context.get("sessions", {}).get(session_id),
            "user_id": runner_context.get("user_id", "anonymous"),
            "tool_service": getattr(self, '_tool_service', None)
        }
        
        # Create domain agent
        domain_agent = AdkDomainAgent(
            agent_id=f"adk_agent_{session_id}",
            config=config_dict,
            runtime_context=runtime_context
        )
        
        # Initialize domain agent
        await domain_agent.initialize()
        
        # Store for future use
        self._session_agents[session_id] = domain_agent
        
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
            "coding": "gpt-4o",
            "analysis": "gpt-4o",
            "creative": "gpt-4.1",
            "chat": "gpt-4.1",
        }

        return task_type_models.get(task_request.task_type, "gpt-4o")

    # === Context and Configuration Helpers ===
    # NOTE: Agent config building methods removed as TaskRequest now provides 
    # agent_config directly. Context handling migrated to RunnerManager.
