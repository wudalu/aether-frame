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
        self._config_agents: Dict[str, List[str]] = {}  # config_hash -> [agent_ids]
        
        # ADK Session Manager for chat session coordination
        from .adk_session_manager import AdkSessionManager
        self.adk_session_manager = AdkSessionManager()
        
        # Runner Manager for correct session lifecycle
        from .runner_manager import RunnerManager
        self.runner_manager = RunnerManager(
            session_manager=self.adk_session_manager,
            agent_runner_mapping=self._agent_runners,
            agent_cleanup_callback=self._handle_agent_cleanup
        )
        
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
    
    async def cleanup_chat_session(self, chat_session_id: str) -> bool:
        """Cleanup chat session resources via session manager entrypoint."""
        if not chat_session_id:
            return False
        return await self.adk_session_manager.cleanup_chat_session(chat_session_id, self.runner_manager)

    async def _handle_agent_cleanup(self, agent_id: str) -> None:
        """Handle cleanup for agents tied 1:1 with runners."""
        if not agent_id:
            return

        self.logger.info(f"Cleaning up agent {agent_id} due to runner teardown")

        agent_config = self.agent_manager._agent_configs.get(agent_id)
        config_hash = None
        if agent_config:
            try:
                config_hash = self.runner_manager.compute_config_hash(agent_config)
            except Exception as exc:
                self.logger.warning(f"Failed to compute config hash for agent {agent_id}: {exc}")
                config_hash = None

        # Remove agent-to-runner mapping
        if agent_id in self._agent_runners:
            del self._agent_runners[agent_id]

        # Remove session tracking
        if agent_id in self._agent_sessions:
            del self._agent_sessions[agent_id]

        # Remove from config hash mapping
        if config_hash and config_hash in self._config_agents:
            self._config_agents[config_hash] = [
                existing_agent for existing_agent in self._config_agents[config_hash]
                if existing_agent != agent_id
            ]
            if not self._config_agents[config_hash]:
                del self._config_agents[config_hash]
        else:
            # Fallback: remove from any config list containing this agent
            for hash_key in list(self._config_agents.keys()):
                if agent_id in self._config_agents[hash_key]:
                    self._config_agents[hash_key] = [
                        existing_agent for existing_agent in self._config_agents[hash_key]
                        if existing_agent != agent_id
                    ]
                    if not self._config_agents[hash_key]:
                        del self._config_agents[hash_key]

        # Delegate to AgentManager for actual domain agent cleanup
        try:
            await self.agent_manager.cleanup_agent(agent_id)
        except Exception as exc:
            self.logger.warning(f"AgentManager cleanup failed for {agent_id}: {exc}")

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
        
        session_user_map = runner_context_dict.get("session_user_ids", {}) if runner_context_dict else {}
        resolved_user_id = session_user_map.get(session_id, self._get_default_user_id())
        
        runtime_context = RuntimeContext(
            session_id=session_id,
            user_id=resolved_user_id,
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

    async def _select_agent_for_config(
        self,
        config_hash: str,
        max_sessions: int,
    ) -> Optional[Tuple[str, "AdkDomainAgent", str]]:
        """Pick a reusable agent for the given config hash if capacity allows."""
        candidate_ids = self._config_agents.get(config_hash, [])
        if not candidate_ids:
            return None

        valid_candidates: List[str] = []
        selected: Optional[Tuple[str, "AdkDomainAgent", str]] = None

        for agent_id in candidate_ids:
            domain_agent = self.agent_manager._agents.get(agent_id)
            if not domain_agent:
                continue

            runner_id = self._agent_runners.get(agent_id)
            if not runner_id:
                continue

            runner_context = self.runner_manager.runners.get(runner_id)
            if not runner_context:
                continue

            valid_candidates.append(agent_id)

            session_count = await self.runner_manager.get_runner_session_count(runner_id)
            if selected is None and session_count < max_sessions:
                selected = (agent_id, domain_agent, runner_id)

        if valid_candidates:
            self._config_agents[config_hash] = valid_candidates
        else:
            self._config_agents.pop(config_hash, None)

        return selected

    async def _create_runtime_context_for_new_agent(self, task_request: TaskRequest) -> "RuntimeContext":
        """Create RuntimeContext for new agent and session (agent_config only)."""
        self.logger.info(f"Pattern 3: agent_config - Creating new agent for agent_type: {task_request.agent_config.agent_type}")
        # Preserve any business-level chat_session_id for later mapping
        chat_session_id = task_request.session_id
        if not chat_session_id and task_request.metadata:
            chat_session_id = task_request.metadata.get("chat_session_id")
        
        # Prepare session identifier (actual ADK session lazily created later)
        session_id = f"adk_session_{uuid4().hex[:12]}"
        runtime_metadata_chat_id = chat_session_id if chat_session_id else None

        config_hash = self.runner_manager.compute_config_hash(task_request.agent_config)
        max_sessions = getattr(self.runner_manager.settings, "max_sessions_per_agent", 100)

        reuse_candidate = await self._select_agent_for_config(config_hash, max_sessions)

        if reuse_candidate:
            agent_id, domain_agent, runner_id = reuse_candidate
            runner_context_dict = self.runner_manager.runners[runner_id]
            adk_session = runner_context_dict["sessions"].get(session_id)
            agent_config = self.agent_manager._agent_configs.get(agent_id, task_request.agent_config)

            metadata = self.agent_manager._agent_metadata.get(agent_id)
            if metadata is not None:
                metadata["last_activity"] = datetime.now()
            self._agent_sessions.setdefault(agent_id, [])

            self.logger.info(
                f"Reusing agent {agent_id} with runner {runner_id} for config hash {config_hash}"
            )

            runtime_context = self._create_runtime_context_from_data(
                task_request,
                session_id,
                agent_id,
                agent_config,
                runner_id,
                runner_context_dict,
                adk_session,
                domain_agent,
                "reuse_existing_agent",
            )

        else:
            agent_id = self.agent_manager.generate_agent_id()
            self.logger.info(f"Generated agent_id: {agent_id}, session_id: {session_id}")

            domain_agent = await self._create_domain_agent_for_config(task_request.agent_config, task_request)

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

            adk_agent = domain_agent.adk_agent

            runner_id, _ = await self.runner_manager.get_or_create_runner(
                task_request.agent_config,
                task_request,
                adk_agent,
                engine_session_id=session_id,
                create_session=False,
                allow_reuse=False,
            )

            self._agent_runners[agent_id] = runner_id
            self._agent_sessions[agent_id] = []
            self._config_agents.setdefault(config_hash, []).append(agent_id)

            runner_context_dict = self.runner_manager.runners[runner_id]
            adk_session = runner_context_dict["sessions"].get(session_id)

            self.logger.info(
                f"✅ Pattern 3: Created new agent {agent_id} with dedicated runner {runner_id} and session {session_id}"
            )

            runtime_context = self._create_runtime_context_from_data(
                task_request,
                session_id,
                agent_id,
                task_request.agent_config,
                runner_id,
                runner_context_dict,
                adk_session,
                domain_agent,
                "create_new_agent_and_session",
            )
        if runtime_metadata_chat_id:
            runtime_context.metadata["business_chat_session_id"] = runtime_metadata_chat_id
        runtime_context.metadata["adk_session_initialized"] = False
        return runtime_context

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

        agent_type = getattr(task_request.agent_config, "agent_type", None) if task_request.agent_config else None
        model_name = None
        if task_request.agent_config and getattr(task_request.agent_config, "model_config", None):
            model_name = task_request.agent_config.model_config.get("model")
        message_count = len(task_request.messages) if task_request.messages else 0

        if self.logger.isEnabledFor(logging.DEBUG):
            message_previews = []
            if task_request.messages:
                for idx, msg in enumerate(task_request.messages, start=1):
                    content = getattr(msg, "content", "")
                    if isinstance(content, str):
                        preview = content[:200] + ("..." if len(content) > 200 else "")
                    else:
                        preview = str(content)
                    message_previews.append({"index": idx, "role": msg.role, "preview": preview})
            self.logger.debug(
                "Agent creation request details",
                extra={
                    "task_id": task_request.task_id,
                    "message_previews": message_previews,
                },
            )

        self.logger.info(
            "Agent creation request received",
            extra={
                "task_id": task_request.task_id,
                "agent_type": agent_type,
                "model": model_name,
                "message_count": message_count,
            },
        )

        try:
            runtime_context = await self._create_runtime_context_for_new_agent(task_request)
        except Exception:
            self.logger.exception(
                "Failed to create runtime context for agent creation",
                extra={"task_id": task_request.task_id},
            )
            raise

        # Update activity timestamp
        runtime_context.update_activity()
        
        business_chat_session_id = runtime_context.metadata.get("business_chat_session_id")

        # Do not create an ADK session during agent creation; return a success placeholder
        result = TaskResult(
            task_id=task_request.task_id,
            status=TaskStatus.SUCCESS,
            agent_id=runtime_context.agent_id,
            session_id=business_chat_session_id or runtime_context.session_id,
            metadata={
                "framework": "adk",
                "agent_id": runtime_context.agent_id,
                "pattern": "agent_creation",
                "adk_session_initialized": False,
            },
        )
        
        # Ensure session_id and agent_id are included in result
        business_chat_session_id = runtime_context.metadata.get("business_chat_session_id")
        result.session_id = business_chat_session_id or runtime_context.session_id
        result.agent_id = runtime_context.agent_id
        result.metadata = result.metadata or {}
        result.metadata.update({
            "framework": "adk", 
            "agent_id": runtime_context.agent_id,
            "execution_id": runtime_context.execution_id,
            "pattern": "agent_creation"
        })
        result.metadata["session_id"] = None
        result.metadata["adk_session_id"] = None
        if business_chat_session_id:
            result.metadata["chat_session_id"] = business_chat_session_id
        
        if self.logger.isEnabledFor(logging.DEBUG):
            response_preview = None
            if result.messages:
                response_preview = result.messages[0].content
            self.logger.debug(
                "Agent creation response details",
                extra={
                    "task_id": task_request.task_id,
                    "agent_id": runtime_context.agent_id,
                    "business_session_id": business_chat_session_id,
                    "response_preview": response_preview[:200] + ("..." if response_preview and len(response_preview) > 200 else "") if isinstance(response_preview, str) else response_preview,
                    "metadata": result.metadata,
                },
            )

        self.logger.info(
            "Agent creation completed",
            extra={
                "task_id": task_request.task_id,
                "agent_id": runtime_context.agent_id,
                "business_session_id": business_chat_session_id,
                "execution_id": runtime_context.execution_id,
            },
        )
        return result

    async def _handle_conversation(self, task_request: TaskRequest, strategy: ExecutionStrategy) -> TaskResult:
        """Handle conversation mode with SessionManager coordination."""
        from ...contracts import RuntimeContext
        
        business_session_id = task_request.session_id
        if self.logger.isEnabledFor(logging.DEBUG):
            conversation_messages = []
            if task_request.messages:
                for idx, msg in enumerate(task_request.messages, start=1):
                    content = getattr(msg, "content", "")
                    if isinstance(content, str):
                        preview = content[:500] + ("..." if len(content) > 500 else "")
                    else:
                        preview = str(content)
                    conversation_messages.append({"index": idx, "role": msg.role, "preview": preview})
            self.logger.debug(
                "Conversation request details",
                extra={
                    "task_id": task_request.task_id,
                    "chat_session_id": business_session_id,
                    "agent_id": task_request.agent_id,
                    "messages": conversation_messages,
                },
            )

        self.logger.info(
            "Conversation request received",
            extra={
                "task_id": task_request.task_id,
                "agent_id": task_request.agent_id,
                "chat_session_id": business_session_id,
                "message_count": len(task_request.messages) if task_request.messages else 0,
            },
        )
        
        # === SessionManager Coordination ===
        try:
            coordination_result = await self.adk_session_manager.coordinate_chat_session(
                chat_session_id=task_request.session_id,
                target_agent_id=task_request.agent_id,
                user_id=task_request.user_context.get_adk_user_id(),
                task_request=task_request,
                runner_manager=self.runner_manager
            )
        except Exception as exc:
            self.logger.exception(
                "Session coordination failed",
                extra={
                    "task_id": task_request.task_id,
                    "chat_session_id": business_session_id,
                    "agent_id": task_request.agent_id,
                },
            )
            raise
        
        # Replace chat_session_id with adk_session_id
        original_session_id = task_request.session_id
        task_request.session_id = coordination_result.adk_session_id
        
        if coordination_result.switch_occurred:
            self.logger.info(f"Session switch completed: "
                           f"chat_session={original_session_id}, "
                           f"{coordination_result.previous_agent_id} -> "
                           f"{coordination_result.new_agent_id}, "
                           f"adk_session={coordination_result.adk_session_id}")
        else:
            self.logger.info(
                "Session coordination result",
                extra={
                    "chat_session_id": original_session_id,
                    "agent_id": task_request.agent_id,
                    "adk_session_id": coordination_result.adk_session_id,
                    "switch_occurred": coordination_result.switch_occurred,
                },
            )
        
        # Execute conversation (original Pattern 1 logic)
        try:
            runtime_context = await self._create_runtime_context_for_existing_session(task_request)
        except Exception as exc:
            self.logger.exception(
                "Failed to create runtime context for conversation",
                extra={
                    "task_id": task_request.task_id,
                    "chat_session_id": original_session_id,
                    "adk_session_id": coordination_result.adk_session_id,
                    "agent_id": task_request.agent_id,
                },
            )
            raise
        
        # Update activity timestamp
        runtime_context.update_activity()
        pattern = runtime_context.metadata.get("pattern")
        self.logger.info(
            "Runtime context prepared",
            extra={
                "chat_session_id": original_session_id,
                "adk_session_id": runtime_context.session_id,
                "agent_id": runtime_context.agent_id,
                "runner_id": runtime_context.runner_id,
                "pattern": pattern,
            },
        )
        
        # Execute task through domain agent with RuntimeContext
        domain_agent = runtime_context.metadata.get("domain_agent")
        try:
            result = await self._execute_with_domain_agent(task_request, runtime_context, domain_agent)
        except Exception:
            # _execute_with_domain_agent already logs details; add business session context here
            self.logger.exception(
                "Domain agent execution raised exception",
                extra={
                    "task_id": task_request.task_id,
                    "chat_session_id": original_session_id,
                    "adk_session_id": runtime_context.session_id,
                    "agent_id": runtime_context.agent_id,
                    "pattern": runtime_context.metadata.get("pattern"),
                },
            )
            raise
        
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
        
        if self.logger.isEnabledFor(logging.DEBUG):
            response_preview = None
            if result.messages:
                response_preview = result.messages[0].content
            self.logger.debug(
                "Conversation response details",
                extra={
                    "task_id": task_request.task_id,
                    "chat_session_id": original_session_id,
                    "adk_session_id": runtime_context.session_id,
                    "agent_id": runtime_context.agent_id,
                    "status": result.status.value if hasattr(result.status, "value") else result.status,
                    "response_preview": response_preview[:500] + ("..." if response_preview and len(response_preview) > 500 else "") if isinstance(response_preview, str) else response_preview,
                    "metadata": result.metadata,
                },
            )

        self.logger.info(
            "Conversation completed",
            extra={
                "task_id": task_request.task_id,
                "chat_session_id": original_session_id,
                "adk_session_id": runtime_context.session_id,
                "agent_id": runtime_context.agent_id,
                "pattern": runtime_context.metadata.get("pattern"),
                "status": result.status.value if hasattr(result.status, "value") else result.status,
                "response_count": len(result.messages) if result.messages else 0,
            },
        )
        if result.status != TaskStatus.SUCCESS:
            self.logger.warning(
                "Conversation finished with non-success status",
                extra={
                    "task_id": task_request.task_id,
                    "chat_session_id": original_session_id,
                    "adk_session_id": runtime_context.session_id,
                    "agent_id": runtime_context.agent_id,
                    "status": result.status.value if hasattr(result.status, "value") else result.status,
                    "error_message": result.error_message,
                },
            )
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
        return self._initialized

    # FIXME: As originally planned, this should return configuration details
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
