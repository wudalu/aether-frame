# -*- coding: utf-8 -*-
"""ADK Runner Manager - Correct Session and Runner Management."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4
import hashlib
import json

try:
    from google.adk.memory import InMemoryMemoryService  # type: ignore
except ImportError:
    InMemoryMemoryService = None  # type: ignore[assignment]

from ...contracts import AgentConfig
from ...config.settings import Settings


class RunnerManager:
    """
    ADK Runner Manager implementing correct Runner-Session lifecycle.
    
    Key Design Principles:
    1. Runner binds to SessionService (one-time creation)
    2. Sessions are created within existing Runners 
    3. Session ID enables future session lookup
    4. Agent configs with same hash can share Runners
    """

    def __init__(self, settings: Settings = None, session_manager=None, agent_runner_mapping=None, agent_cleanup_callback=None):
        """Initialize runner manager."""
        self.logger = logging.getLogger(__name__)
        self.settings = settings or Settings()
        self.session_manager = session_manager  # SessionManager instance for creating session services
        self.agent_runner_mapping = agent_runner_mapping  # External agent_id -> runner_id mapping
        self.agent_cleanup_callback = agent_cleanup_callback  # Optional callback executed when runner is cleaned
        
        # Core storage
        self.runners = {}  # runner_id -> RunnerContext
        self.session_to_runner = {}  # session_id -> runner_id
        self.config_to_runner = {}  # config_hash -> runner_id
        
        # Runner availability check
        self.logger.info("RunnerManager initialized")


    def _hash_config(self, agent_config: AgentConfig) -> str:
        """Generate hash for agent configuration to enable Runner reuse."""
        config_dict = {
            "agent_type": agent_config.agent_type,
            "system_prompt": getattr(agent_config, 'system_prompt', ''),
            "model_config": getattr(agent_config, 'model_config', {}),
            "available_tools": getattr(agent_config, 'available_tools', []),
        }
        config_str = json.dumps(config_dict, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:16]

    def compute_config_hash(self, agent_config: AgentConfig) -> str:
        """Public helper to compute a stable hash for an agent configuration."""
        return self._hash_config(agent_config)

    async def get_or_create_runner(
        self,
        agent_config: AgentConfig,
        task_request = None,
        adk_agent = None,
        engine_session_id: str = None,
        create_session: bool = True,
        allow_reuse: bool = True,
    ) -> Tuple[str, Optional[str]]:
        """
        Get existing Runner or create new one, then create Session using Engine-provided session_id.
        
        H5 SESSION ID UNIFICATION: Use Engine-provided session_id instead of generating our own.
        
        Args:
            agent_config: Agent configuration for Runner creation
            task_request: TaskRequest containing context information for Session creation
            adk_agent: Optional pre-created ADK agent to use (if provided, skips agent creation)
            engine_session_id: Session ID provided by Engine (H5)
            allow_reuse: When False, forces creation of a new runner even if a config match exists
            
        Returns:
            Tuple[runner_id, session_id]: IDs for created/existing runner and session
        """
        config_hash = self._hash_config(agent_config)
        
        # Check if Runner exists for this config
        if allow_reuse and config_hash in self.config_to_runner:
            runner_id = self.config_to_runner[config_hash]
            self.logger.info(f"Reusing existing Runner {runner_id} for config hash {config_hash}")
        else:
            # Create new Runner
            runner_id = await self._create_new_runner(agent_config, config_hash, adk_agent)
            self.config_to_runner[config_hash] = runner_id
            self.logger.info(f"Created new Runner {runner_id} for config hash {config_hash}")
        
        session_id = None
        if create_session:
            # H5: Use Engine-provided session_id instead of generating our own
            session_id = engine_session_id or f"{self.settings.session_id_prefix}_{uuid4().hex[:12]}"
            created_session_id = await self._create_session_in_runner(
                runner_id, task_request, external_session_id=session_id
            )
            session_id = created_session_id
            
            # Record session-to-runner mapping
            self.session_to_runner[session_id] = runner_id
        
        return runner_id, session_id

    async def get_runner_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get Runner context by session ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            RunnerContext dict or None if not found
        """
        if session_id not in self.session_to_runner:
            self.logger.warning(f"Session {session_id} not found in mapping")
            return None
            
        runner_id = self.session_to_runner[session_id]
        runner_context = self.runners.get(runner_id)
        
        if not runner_context:
            self.logger.error(f"Runner {runner_id} not found for session {session_id}")
            return None
        return runner_context

    async def _create_new_runner(self, agent_config: AgentConfig, config_hash: str, adk_agent = None) -> str:
        """
        Create new ADK Runner with bound SessionService.
        
        Args:
            agent_config: Agent configuration
            config_hash: Configuration hash for tracking
            adk_agent: Optional pre-created ADK agent to use (if None, creates internal agent)
            
        Returns:
            runner_id: Unique identifier for the created Runner
        """
        runner_id = f"{self.settings.runner_id_prefix}_{uuid4().hex[:12]}"
        
        try:
            from google.adk.runners import Runner
            
            # Create dedicated SessionService for this Runner through SessionManager
            if self.session_manager:
                session_service = self.session_manager.create_session_service()
            else:
                # Fallback to direct creation if no session manager provided
                from google.adk.sessions import InMemorySessionService
                session_service = InMemorySessionService()
            
            if adk_agent is None:
                raise RuntimeError(
                    "ADK agent instance must be provided by the domain agent."
                )
            
            memory_service = None
            if InMemoryMemoryService:
                try:
                    memory_service = InMemoryMemoryService()
                    self.logger.debug("Initialized InMemoryMemoryService for runner %s", runner_id)
                except Exception as exc:
                    self.logger.warning(
                        "Failed to initialize InMemoryMemoryService: %s", exc
                    )
                    memory_service = None

            runner_kwargs = {
                "agent": adk_agent,
                "app_name": self.settings.default_app_name,
                "session_service": session_service,
            }
            if memory_service is not None:
                runner_kwargs["memory_service"] = memory_service

            runner = Runner(**runner_kwargs)
            
            now = datetime.now()

            # Store Runner context
            self.runners[runner_id] = {
                "runner": runner,
                "session_service": session_service,
                "agent_config": agent_config,
                "config_hash": config_hash,
                "sessions": {},  # session_id -> adk_session
                "session_user_ids": {},  # session_id -> user_id
                "created_at": now,
                "last_activity": now,
                "app_name": self.settings.default_app_name,  # Store app_name for session operations
                "user_id": self.settings.default_user_id,
                "memory_service": memory_service,
            }
            
            self.logger.info(f"Created ADK Runner {runner_id} with dedicated SessionService")
            return runner_id
            
        except Exception as e:
            self.logger.error(f"Failed to create Runner {runner_id}: {str(e)}")
            raise RuntimeError(f"Runner creation failed: {str(e)}")

    def mark_runner_activity(self, runner_id: str) -> None:
        """Update last_activity timestamp for the runner if it exists."""
        context = self.runners.get(runner_id)
        if context:
            context["last_activity"] = datetime.now()

    async def _create_session_in_runner(self, runner_id: str, task_request = None, external_session_id: str = None) -> str:
        """
        Create new Session within existing Runner using provided session_id.
        
        H5 SESSION ID UNIFICATION: Accept external session_id from Framework layer.
        
        Args:
            runner_id: Target Runner ID
            task_request: TaskRequest containing context information for Session
            external_session_id: Session ID provided by Framework (H5)
            
        Returns:
            session_id: The session ID used (external_session_id if provided, or generated)
        """
        runner_context = self.runners.get(runner_id)
        if not runner_context:
            raise ValueError(f"Runner {runner_id} not found")
        
        # H5: Use external session_id if provided, otherwise generate
        session_id = external_session_id or f"{self.settings.session_id_prefix}_{uuid4().hex[:12]}"
        user_id = None
        app_name = self.settings.default_app_name  # App name can use config default
        
        if task_request and task_request.user_context:
            # Use UserContext's method which handles fallbacks properly
            user_id = task_request.user_context.get_adk_user_id()
            self.logger.info(f"Extracted user_id from task_request: {user_id}")
        else:
            self.logger.warning(f"No user_context in task_request: {task_request}")
        
        # Only use config default as absolute fallback if no user context provided
        if not user_id:
            user_id = self.settings.default_user_id
            self.logger.info(f"Using default user_id: {user_id}")
        
        self.logger.info(f"Creating ADK session with app_name={app_name}, user_id={user_id}, session_id={session_id}")
        
        try:
            session_service = runner_context["session_service"]
                        
            # Create ADK Session in the Runner's SessionService with context
            adk_session = await session_service.create_session(
                app_name=app_name,  # Use consistent app_name that matches Runner
                user_id=user_id,  # Use extracted user_id
                session_id=session_id  # H5: Use provided/generated session_id
            )
            
            # Store session reference
            runner_context["sessions"][session_id] = adk_session
            runner_context.setdefault("session_user_ids", {})[session_id] = user_id
            runner_context["last_activity"] = datetime.now()
            self.session_to_runner[session_id] = runner_id
            
            self.logger.info(f"Created ADK Session {session_id} in Runner {runner_id}")
            return session_id
            
        except Exception as e:
            self.logger.error(f"Failed to create Session {session_id} in Runner {runner_id}: {str(e)}")
            raise RuntimeError(f"Session creation failed: {str(e)}")

    async def cleanup_runner(self, runner_id: str) -> bool:
        """
        Cleanup Runner and all its Sessions.
        
        Args:
            runner_id: Runner to cleanup
            
        Returns:
            bool: True if cleanup successful
        """
        runner_context = self.runners.get(runner_id)
        if not runner_context:
            return False
        
        try:
            # Cleanup all sessions in this runner
            session_ids = list(runner_context["sessions"].keys())
            for session_id in session_ids:
                if session_id in self.session_to_runner:
                    del self.session_to_runner[session_id]
                session_user_map = runner_context.get("session_user_ids")
                if session_user_map and session_id in session_user_map:
                    del session_user_map[session_id]
            
            # Cleanup Runner resources
            runner = runner_context.get("runner")
            if runner and hasattr(runner, "shutdown"):
                await runner.shutdown()
                
            session_service = runner_context.get("session_service")
            if session_service and hasattr(session_service, "shutdown"):
                await session_service.shutdown()
            
            # Remove from config mapping
            config_hash = runner_context["config_hash"]
            if config_hash in self.config_to_runner:
                del self.config_to_runner[config_hash]
            
            # Remove any agent mapping pointing to this runner
            agents_to_cleanup = []
            if self.agent_runner_mapping:
                stale_agents = [
                    agent_id
                    for agent_id, mapped_runner in self.agent_runner_mapping.items()
                    if mapped_runner == runner_id
                ]
                for agent_id in stale_agents:
                    del self.agent_runner_mapping[agent_id]
                agents_to_cleanup = stale_agents
            
            # Remove runner context
            del self.runners[runner_id]

            # Trigger agent cleanup callback if provided
            if agents_to_cleanup and self.agent_cleanup_callback:
                for agent_id in agents_to_cleanup:
                    try:
                        await self.agent_cleanup_callback(agent_id)
                    except Exception as exc:
                        self.logger.warning(f"Agent cleanup callback failed for {agent_id}: {exc}")
            
            self.logger.info(f"Successfully cleaned up Runner {runner_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup Runner {runner_id}: {str(e)}")
            return False

    async def get_runner_stats(self) -> Dict[str, Any]:
        """Get Runner manager statistics."""
        return {
            "total_runners": len(self.runners),
            "total_sessions": len(self.session_to_runner),
            "total_configs": len(self.config_to_runner),
            "runners": [
                {
                    "runner_id": rid,
                    "config_hash": ctx["config_hash"],
                    "session_count": len(ctx["sessions"]),
                    "created_at": ctx["created_at"].isoformat() if isinstance(ctx.get("created_at"), datetime) else ctx.get("created_at"),
                    "last_activity": ctx["last_activity"].isoformat() if isinstance(ctx.get("last_activity"), datetime) else ctx.get("last_activity"),
                }
                for rid, ctx in self.runners.items()
            ]
        }

    async def remove_session_from_runner(self, runner_id: str, session_id: str) -> bool:
        """
        Remove a specific session from a runner.
        
        Args:
            runner_id: The runner to remove session from
            session_id: The session to remove
            
        Returns:
            bool: True if session was removed successfully
        """
        runner_context = self.runners.get(runner_id)
        if not runner_context:
            self.logger.warning(f"Runner {runner_id} not found")
            return False
            
        if session_id not in runner_context["sessions"]:
            self.logger.warning(f"Session {session_id} not found in runner {runner_id}")
            return False
        
        try:
            # Get the session_service and session for this runner
            session_service = runner_context["session_service"]
            adk_session = runner_context["sessions"][session_id]
            
            # If this is a real ADK session (not mock), delete through SessionService
            if session_service and not isinstance(adk_session, dict):
                # Use the correct ADK API: session_service.delete_session(app_name, user_id, session_id)
                app_name = adk_session.app_name
                user_id = adk_session.user_id
                
                await session_service.delete_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id
                )
                    
                self.logger.info(f"Deleted ADK session {session_id} through SessionService")
            
            # Remove session from runner's sessions dict
            del runner_context["sessions"][session_id]
            session_user_map = runner_context.get("session_user_ids")
            if session_user_map and session_id in session_user_map:
                del session_user_map[session_id]
            
            # Remove from global session mapping
            if session_id in self.session_to_runner:
                del self.session_to_runner[session_id]

            runner_context["last_activity"] = datetime.now()
            
            self.logger.info(f"Removed session {session_id} from runner {runner_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove session {session_id} from runner {runner_id}: {e}")
            return False

    async def get_runner_session_count(self, runner_id: str) -> int:
        """
        Get the number of sessions in a runner.
        
        Args:
            runner_id: The runner to check
            
        Returns:
            int: Number of sessions in the runner (0 if runner not found)
        """
        runner_context = self.runners.get(runner_id)
        if not runner_context:
            return 0
            
        return len(runner_context["sessions"])

    async def get_runner_for_agent(self, agent_id: str) -> str:
        """
        Get runner ID for a specific agent.
        
        Args:
            agent_id: The agent identifier
            
        Returns:
            str: Runner ID for the agent
            
        Raises:
            RuntimeError: If no runner found for the agent
        """
        if not self.agent_runner_mapping:
            raise RuntimeError(
                f"No agent-runner mapping provided to RunnerManager. "
                f"Cannot find runner for agent_id: {agent_id}"
            )
        
        runner_id = self.agent_runner_mapping.get(agent_id)
        if not runner_id:
            raise RuntimeError(
                f"No runner found for agent_id: {agent_id}. "
                f"Available agents: {list(self.agent_runner_mapping.keys())}"
            )
        
        # Verify the runner actually exists
        if runner_id not in self.runners:
            raise RuntimeError(
                f"Runner {runner_id} mapped to agent {agent_id} does not exist. "
                f"Available runners: {list(self.runners.keys())}"
            )
        
        return runner_id
