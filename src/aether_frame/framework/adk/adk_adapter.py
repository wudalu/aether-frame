# -*- coding: utf-8 -*-
"""ADK Framework Adapter Implementation."""

import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Optional, Tuple, Union
from datetime import datetime
from uuid import uuid4

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
        
        # Agent Manager for agent lifecycle management
        from ...agents.manager import AgentManager
        self.agent_manager = AgentManager()
        
        # Agent to Runner mapping management (initialize before RunnerManager)
        self._agent_runners: Dict[str, str] = {}  # agent_id -> runner_id
        self._agent_sessions: Dict[str, List[str]] = {}  # agent_id -> [session_ids]
        
        # ADK Session Manager for chat session coordination
        from .adk_session_manager import AdkSessionManager
        self.adk_session_manager = AdkSessionManager()
        
        # Runner Manager for correct session lifecycle
        from .runner_manager import RunnerManager
        self.runner_manager = RunnerManager(
            session_manager=self.adk_session_manager,
            agent_runner_mapping=self._agent_runners
        )
        
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
        
        # Update RunnerManager settings if provided (avoid data loss from rebuild)
        if settings:
            # Update settings without rebuilding to preserve existing runners/sessions
            self.runner_manager.settings = settings
            self.logger.info(f"Updated RunnerManager settings without rebuild to preserve data")

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

    # === Execution Pattern Handler Methods ===
    
    class ExecutionError(Exception):
        """Exception raised during execution pattern handling."""
        def __init__(self, message: str, task_request: TaskRequest):
            super().__init__(message)
            self.message = message
            self.task_request = task_request
    
    def _get_agent_and_runner(self, agent_id: str, task_request: TaskRequest):
        """Get domain agent and runner for given agent_id. Raises ExecutionError if not found."""
        try:
            # Check if agent exists
            domain_agent = self.agent_manager._agents.get(agent_id)
            if not domain_agent:
                raise self.ExecutionError(f"Agent {agent_id} not found", task_request)
            
            # Get runner_id from agent mapping
            runner_id = self._agent_runners.get(agent_id)
            if not runner_id:
                raise self.ExecutionError(f"No runner found for agent {agent_id}", task_request)
            
            # Get runner context
            runner_context_dict = self.runner_manager.runners.get(runner_id)
            if not runner_context_dict:
                raise self.ExecutionError(f"Runner {runner_id} not found", task_request)
            
            return domain_agent, runner_id, runner_context_dict
            
        except self.ExecutionError:
            raise
        except Exception as e:
            raise self.ExecutionError(f"Error getting agent/runner: {str(e)}", task_request)
    
    def _create_runtime_context_from_data(self, task_request: TaskRequest, session_id: str, agent_id: str, 
                                         agent_config: "AgentConfig", runner_id: str, runner_context_dict: Dict[str, Any],
                                         adk_session: Any, domain_agent: "AdkDomainAgent", pattern: str) -> "RuntimeContext":
        """Create RuntimeContext from validated data."""
        from ...contracts import RuntimeContext
        from datetime import datetime
        
        runtime_context = RuntimeContext(
            session_id=session_id,
            user_id=runner_context_dict.get("user_id", self._get_default_user_id()),
            framework_type=FrameworkType.ADK,
            agent_id=agent_id,
            agent_config=agent_config,
            runner_id=runner_id,
            runner_context=runner_context_dict,
            framework_session=adk_session,
            tool_service=getattr(self, '_tool_service', None),
            execution_id=f"exec_{task_request.task_id}",
            created_at=datetime.now(),
            last_activity=datetime.now()
        )
        runtime_context.metadata.update({
            "domain_agent": domain_agent,
            "pattern": pattern
        })
        return runtime_context
    
    async def _create_runtime_context_for_existing_session(self, task_request: TaskRequest) -> "RuntimeContext":
        """Create RuntimeContext for existing session (agent_id + session_id)."""
        self.logger.info(f"Pattern 1: agent_id + session_id - Continuing existing session {task_request.session_id} for agent {task_request.agent_id}")
        
        # Get agent and runner data (may raise ExecutionError)
        domain_agent, runner_id, runner_context_dict = self._get_agent_and_runner(task_request.agent_id, task_request)
        
        # Verify session exists in runner
        adk_session = runner_context_dict["sessions"].get(task_request.session_id)
        if not adk_session:
            raise self.ExecutionError(
                f"Session {task_request.session_id} not found in agent {task_request.agent_id}",
                task_request
            )
        
        self.logger.info(f"✅ Pattern 1: Found existing session {task_request.session_id} in runner {runner_id} for agent {task_request.agent_id}")
        
        # Create RuntimeContext with existing session information
        agent_config = self.agent_manager._agent_configs.get(task_request.agent_id)
        return self._create_runtime_context_from_data(
            task_request, task_request.session_id, task_request.agent_id, 
            agent_config, runner_id, runner_context_dict, adk_session, 
            domain_agent, "continue_existing_session"
        )

    async def _create_runtime_context_for_new_session(self, task_request: TaskRequest) -> "RuntimeContext":
        """Create RuntimeContext for new session with existing agent (agent_id only)."""
        self.logger.info(f"Pattern 2: agent_id only - Creating new session for existing agent {task_request.agent_id}")
        
        # Get agent and runner data (may raise ExecutionError)
        domain_agent, runner_id, runner_context_dict = self._get_agent_and_runner(task_request.agent_id, task_request)
        agent_config = self.agent_manager._agent_configs.get(task_request.agent_id)
        
        # Create new session in existing runner
        session_id = f"adk_session_{uuid4().hex[:12]}"
        
        try:
            returned_session_id = await self.runner_manager._create_session_in_runner(
                runner_id, task_request, session_id
            )
            session_id = returned_session_id
            
            # Update agent sessions mapping
            if task_request.agent_id not in self._agent_sessions:
                self._agent_sessions[task_request.agent_id] = []
            self._agent_sessions[task_request.agent_id].append(session_id)
            
            # Get updated runner context and ADK session
            runner_context_dict = self.runner_manager.runners.get(runner_id)
            adk_session = runner_context_dict["sessions"].get(session_id)
            
            self.logger.info(f"✅ Pattern 2: Created new session {session_id} in existing runner {runner_id} for agent {task_request.agent_id}")
            
            # Create RuntimeContext with new session information
            return self._create_runtime_context_from_data(
                task_request, session_id, task_request.agent_id, 
                agent_config, runner_id, runner_context_dict, adk_session, 
                domain_agent, "new_session_existing_agent"
            )
            
        except Exception as e:
            raise self.ExecutionError(
                f"Failed to create session for agent {task_request.agent_id}: {str(e)}", 
                task_request
            )

    async def _create_runtime_context_for_new_agent(self, task_request: TaskRequest) -> "RuntimeContext":
        """Create RuntimeContext for new agent and session (agent_config only)."""
        from datetime import datetime
        
        self.logger.info(f"Pattern 3: agent_config - Creating new agent for agent_type: {task_request.agent_config.agent_type}")
        
        # Generate agent_id and session_id
        agent_id = f"agent_{uuid4().hex[:12]}"
        session_id = f"adk_session_{uuid4().hex[:12]}"
        self.logger.info(f"Generated agent_id: {agent_id}, session_id: {session_id}")
        
        # Create domain agent first
        domain_agent = await self._create_domain_agent_for_config(task_request.agent_config, task_request)
        
        # Register agent with AgentManager
        try:
            self.agent_manager._agents[agent_id] = domain_agent
            self.agent_manager._agent_configs[agent_id] = task_request.agent_config
            self.agent_manager._agent_metadata[agent_id] = {
                "created_at": datetime.now(),
                "last_activity": datetime.now(),
                "agent_type": task_request.agent_config.agent_type,
                "framework_type": FrameworkType.ADK,
            }
            
            self.logger.info(f"✅ Agent {agent_id} registered with AgentManager")
            
        except Exception as e:
            raise self.ExecutionError(
                f"Failed to register agent with AgentManager: {str(e)}", 
                task_request
            )
        
        # ADK agent is already created by domain_agent.initialize()
        adk_agent = domain_agent.adk_agent
        
        # Create runner and session
        runner_id, returned_session_id = await self.runner_manager.get_or_create_runner(
            task_request.agent_config, task_request, adk_agent, engine_session_id=session_id
        )
        
        # Store agent to runner mapping
        self._agent_runners[agent_id] = runner_id
        self._agent_sessions[agent_id] = [returned_session_id]
        
        # Use returned session_id for consistency
        if returned_session_id != session_id:
            self.logger.warning(f"RunnerManager returned different session_id: {session_id} -> {returned_session_id}")
            session_id = returned_session_id
        
        runner_context_dict = self.runner_manager.runners[runner_id]
        adk_session = runner_context_dict["sessions"].get(session_id)
        
        self.logger.info(f"✅ Pattern 3: Created new agent {agent_id} with runner {runner_id} and session {session_id}")
        
        # Create RuntimeContext with new agent and session information
        return self._create_runtime_context_from_data(
            task_request, session_id, agent_id, task_request.agent_config,
            runner_id, runner_context_dict, adk_session, 
            domain_agent, "create_new_agent_and_session"
        )

    async def execute_task(
        self, task_request: TaskRequest, strategy: ExecutionStrategy
    ) -> TaskResult:
        """
        Execute task with two distinct modes:
        1. Creation Mode: agent_config provided -> create new agent
        2. Conversation Mode: agent_id + session_id provided -> execute conversation

        Args:
            task_request: The universal task request
            strategy: Execution strategy containing framework type and execution mode

        Returns:
            TaskResult: The result with agent_id and session_id for follow-up requests
        """
        from ...contracts import RuntimeContext
        
        self.logger.info(f"ADK task execution started - task_id: {task_request.task_id}, agent_id: {task_request.agent_id}, session_id: {task_request.session_id}")

        try:
            # === Creation Mode - agent_config provided ===
            if task_request.agent_config and not task_request.agent_id:
                return await self._handle_agent_creation(task_request, strategy)
            
            # === Conversation Mode - agent_id + session_id provided ===
            elif task_request.agent_id and task_request.session_id:
                return await self._handle_conversation(task_request, strategy)
            
            # === Invalid request ===
            else:
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message="Invalid request: must provide either agent_config "\
                         "(creation) or agent_id+session_id (conversation)",
                    agent_id=task_request.agent_id,
                )

        except self.ExecutionError as e:
            # Handle our custom execution errors
            self.logger.error(f"ADK execution error - task_id: {task_request.task_id}, error: {e.message}")
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=e.message,
                session_id=getattr(e.task_request, 'session_id', None),
                agent_id=getattr(e.task_request, 'agent_id', None),
            )
        except Exception as e:
            self.logger.error(f"ADK task execution failed - task_id: {task_request.task_id}, error: {str(e)}")
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"ADK execution failed: {str(e)}",
                session_id=task_request.session_id,  # Keep original session_id if any
                agent_id=task_request.agent_id,  # Keep original agent_id if any
            )

    async def _handle_agent_creation(self, task_request: TaskRequest, strategy: ExecutionStrategy) -> TaskResult:
        """Handle agent creation mode (original Pattern 3)."""
        from ...contracts import RuntimeContext
        
        runtime_context = await self._create_runtime_context_for_new_agent(task_request)
        
        # Update activity timestamp
        runtime_context.update_activity()
        
        # Execute task through domain agent with RuntimeContext
        domain_agent = runtime_context.metadata.get("domain_agent")
        result = await self._execute_with_domain_agent(task_request, runtime_context, domain_agent)
        
        # Ensure session_id and agent_id are included in result
        result.session_id = runtime_context.session_id
        result.agent_id = runtime_context.agent_id
        result.metadata = result.metadata or {}
        result.metadata.update({
            "framework": "adk", 
            "session_id": runtime_context.session_id, 
            "agent_id": runtime_context.agent_id,
            "execution_id": runtime_context.execution_id,
            "pattern": "agent_creation"
        })
        
        self.logger.info(f"Agent creation completed - task_id: "
                        f"{task_request.task_id}, agent_id: "
                        f"{runtime_context.agent_id}, session_id: "
                        f"{runtime_context.session_id}")
        return result

    async def _handle_conversation(self, task_request: TaskRequest, strategy: ExecutionStrategy) -> TaskResult:
        """Handle conversation mode with SessionManager coordination."""
        from ...contracts import RuntimeContext
        
        # === SessionManager Coordination ===
        coordination_result = await self.adk_session_manager.coordinate_chat_session(
            chat_session_id=task_request.session_id,
            target_agent_id=task_request.agent_id,
            user_id=task_request.user_context.get_adk_user_id(),
            task_request=task_request,
            runner_manager=self.runner_manager
        )
        
        # Replace chat_session_id with adk_session_id
        original_session_id = task_request.session_id
        task_request.session_id = coordination_result.adk_session_id
        
        if coordination_result.switch_occurred:
            self.logger.info(f"Session switch completed: "
                           f"chat_session={original_session_id}, "
                           f"{coordination_result.previous_agent_id} -> "
                           f"{coordination_result.new_agent_id}, "
                           f"adk_session={coordination_result.adk_session_id}")
        
        # Execute conversation (original Pattern 1 logic)
        runtime_context = await self._create_runtime_context_for_existing_session(task_request)
        
        # Update activity timestamp
        runtime_context.update_activity()
        
        # Execute task through domain agent with RuntimeContext
        domain_agent = runtime_context.metadata.get("domain_agent")
        result = await self._execute_with_domain_agent(task_request, runtime_context, domain_agent)
        
        # Ensure session_id and agent_id are included in result
        # IMPORTANT: Return original_session_id (business chat_session_id) not ADK session_id
        # This allows business layer to continue using the same chat_session_id for agent switching
        result.session_id = original_session_id  # Return business chat_session_id
        result.agent_id = runtime_context.agent_id
        result.metadata = result.metadata or {}
        result.metadata.update({
            "framework": "adk", 
            "chat_session_id": original_session_id,  # Business chat session ID
            "adk_session_id": runtime_context.session_id,  # Internal ADK session ID
            "agent_id": runtime_context.agent_id,
            "execution_id": runtime_context.execution_id,
            "pattern": "conversation"
        })
        
        self.logger.info(f"Conversation completed - task_id: "
                        f"{task_request.task_id}, agent_id: "
                        f"{runtime_context.agent_id}, session_id: "
                        f"{runtime_context.session_id}")
        return result


    async def _execute_with_domain_agent(
        self, task_request: TaskRequest, runtime_context: "RuntimeContext", domain_agent: "AdkDomainAgent"
    ) -> TaskResult:
        """
        Execute task through domain agent with RuntimeContext.
        
        This creates an AgentRequest with RuntimeContext and forwards to the ADK domain agent,
        following the correct execution chain architecture.
        
        Args:
            task_request: Original task request
            runtime_context: RuntimeContext with all execution state
            domain_agent: Domain agent to execute the task
            
        Returns:
            TaskResult: Result from domain agent execution
        """
        try:
            # Import contracts
            from ...contracts import AgentRequest, FrameworkType
            
            # Create AgentRequest with RuntimeContext for domain agent
            agent_request = AgentRequest(
                agent_type=self._get_default_agent_type(),
                framework_type=FrameworkType.ADK,
                task_request=task_request,
                session_id=runtime_context.session_id,  # Ensure session_id propagates to domain agent
                runtime_options=runtime_context.get_runtime_dict()  # Use runtime dict for backward compatibility
            )
            
            # Update domain agent runtime context using RuntimeContext
            domain_agent.runtime_context.update(runtime_context.get_runtime_dict())
            
            # Execute through domain agent
            result = await domain_agent.execute(agent_request)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Domain agent execution failed - session_id: {runtime_context.session_id}, error: {str(e)}")
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"Domain agent execution failed: {str(e)}",
                session_id=runtime_context.session_id,
                agent_id=runtime_context.agent_id
            )

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
