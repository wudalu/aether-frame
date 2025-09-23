# -*- coding: utf-8 -*-
"""ADK Runner Manager - Correct Session and Runner Management."""

import logging
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4
import hashlib
import json

from ...contracts import AgentConfig


class RunnerManager:
    """
    ADK Runner Manager implementing correct Runner-Session lifecycle.
    
    Key Design Principles:
    1. Runner binds to SessionService (one-time creation)
    2. Sessions are created within existing Runners 
    3. Session ID enables future session lookup
    4. Agent configs with same hash can share Runners
    """

    def __init__(self):
        """Initialize runner manager."""
        self.logger = logging.getLogger(__name__)
        
        # Core storage
        self.runners = {}  # runner_id -> RunnerContext
        self.session_to_runner = {}  # session_id -> runner_id
        self.config_to_runner = {}  # config_hash -> runner_id
        
        # Runner availability check
        self._adk_available = False
        self._check_adk_availability()

    def _check_adk_availability(self):
        """Check if ADK dependencies are available."""
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            self._adk_available = True
            self.logger.info("✅ ADK dependencies verified - RunnerManager ready")
            print(f"[RunnerManager] ✅ ADK dependencies verified - RunnerManager ready")
        except ImportError as e:
            self.logger.warning(f"❌ ADK not available - RunnerManager in mock mode: {e}")
            print(f"[RunnerManager] ❌ ADK not available - RunnerManager in mock mode: {e}")
            self._adk_available = False

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

    async def get_or_create_runner(self, agent_config: AgentConfig, task_request = None) -> Tuple[str, str]:
        """
        Get existing Runner or create new one, then create Session.
        
        Args:
            agent_config: Agent configuration for Runner creation
            task_request: TaskRequest containing context information for Session creation
            
        Returns:
            Tuple[runner_id, session_id]: IDs for created/existing runner and new session
        """
        print(f"[RunnerManager] get_or_create_runner called - ADK available: {self._adk_available}")
        config_hash = self._hash_config(agent_config)
        
        # Check if Runner exists for this config
        if config_hash in self.config_to_runner:
            runner_id = self.config_to_runner[config_hash]
            self.logger.info(f"Reusing existing Runner {runner_id} for config hash {config_hash}")
            print(f"[RunnerManager] Reusing existing Runner {runner_id}")
        else:
            # Create new Runner
            runner_id = await self._create_new_runner(agent_config, config_hash)
            self.config_to_runner[config_hash] = runner_id
            self.logger.info(f"Created new Runner {runner_id} for config hash {config_hash}")
            print(f"[RunnerManager] Created new Runner {runner_id}")
        
        # Create Session in the Runner
        session_id = await self._create_session_in_runner(runner_id, agent_config, task_request)
        print(f"[RunnerManager] Created session {session_id} in runner {runner_id}")
        
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
        print(f"[RunnerManager] Looking for session {session_id}")
        print(f"[RunnerManager] Available sessions: {list(self.session_to_runner.keys())}")
        
        if session_id not in self.session_to_runner:
            self.logger.warning(f"Session {session_id} not found in mapping")
            print(f"[RunnerManager] ❌ Session {session_id} not found in mapping")
            return None
            
        runner_id = self.session_to_runner[session_id]
        runner_context = self.runners.get(runner_id)
        
        if not runner_context:
            self.logger.error(f"Runner {runner_id} not found for session {session_id}")
            print(f"[RunnerManager] ❌ Runner {runner_id} not found for session {session_id}")
            return None
            
        print(f"[RunnerManager] ✅ Found runner {runner_id} for session {session_id}")
        return runner_context

    async def _create_new_runner(self, agent_config: AgentConfig, config_hash: str) -> str:
        """
        Create new ADK Runner with bound SessionService.
        
        Args:
            agent_config: Agent configuration
            config_hash: Configuration hash for tracking
            
        Returns:
            runner_id: Unique identifier for the created Runner
        """
        runner_id = f"runner_{uuid4().hex[:8]}"
        
        if not self._adk_available:
            # Mock mode for testing without ADK
            self.runners[runner_id] = {
                "runner": None,  # Mock runner
                "session_service": None,  # Mock session service
                "agent_config": agent_config,
                "config_hash": config_hash,
                "sessions": {},  # session_id -> mock_session
                "created_at": "mock_time"
            }
            self.logger.info(f"Created mock Runner {runner_id} - ADK not available")
            return runner_id
        
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            
            # Create dedicated SessionService for this Runner
            session_service = InMemorySessionService()
            
            # Build ADK Agent (simplified for now)
            adk_agent = await self._build_adk_agent(agent_config)
            
            # Create Runner bound to SessionService with consistent app_name
            runner = Runner(
                agent=adk_agent,
                app_name="aether_frame",  # Use consistent app_name for both Runner and sessions
                session_service=session_service  # Key: binding relationship
            )
            
            # Store Runner context
            self.runners[runner_id] = {
                "runner": runner,
                "session_service": session_service,
                "agent_config": agent_config,
                "config_hash": config_hash,
                "sessions": {},  # session_id -> adk_session
                "created_at": "datetime_now",  # TODO: actual datetime
                "user_id": "anonymous",  # Default user_id, will be updated when creating sessions
            }
            
            self.logger.info(f"Created ADK Runner {runner_id} with dedicated SessionService")
            return runner_id
            
        except Exception as e:
            self.logger.error(f"Failed to create Runner {runner_id}: {str(e)}")
            raise RuntimeError(f"Runner creation failed: {str(e)}")

    async def _create_session_in_runner(self, runner_id: str, agent_config: AgentConfig, task_request = None) -> str:
        """
        Create new Session within existing Runner.
        
        Args:
            runner_id: Target Runner ID
            agent_config: Agent configuration for session context
            task_request: TaskRequest containing context information for Session
            
        Returns:
            session_id: Unique identifier for the created Session
        """
        runner_context = self.runners.get(runner_id)
        if not runner_context:
            raise ValueError(f"Runner {runner_id} not found")
        
        session_id = f"session_{uuid4().hex[:8]}"
        
        if not self._adk_available:
            # Mock session
            runner_context["sessions"][session_id] = {"mock": True}
            self.logger.info(f"Created mock Session {session_id} in Runner {runner_id} - ADK not available")
            return session_id
        
        try:
            session_service = runner_context["session_service"]
            
            # Extract user context from task_request
            user_id = "anonymous"  # Default
            app_name = "aether_frame"  # Use consistent app_name that matches Runner
            
            if task_request and task_request.user_context:
                # Extract user_id from user context
                if hasattr(task_request.user_context, 'user_id'):
                    user_id = task_request.user_context.user_id
                elif hasattr(task_request.user_context, 'get_adk_user_id'):
                    user_id = task_request.user_context.get_adk_user_id()
            
            # Create ADK Session in the Runner's SessionService with context
            adk_session = await session_service.create_session(
                app_name=app_name,  # Use consistent app_name that matches Runner
                user_id=user_id,  # Use extracted user_id
                session_id=session_id
            )
            
            # Debug: Check what ADK session actually created
            print(f"[RunnerManager] ADK Session created: {adk_session}")
            print(f"[RunnerManager] ADK Session type: {type(adk_session)}")
            if hasattr(adk_session, 'session_id'):
                print(f"[RunnerManager] ADK Session ID: {adk_session.session_id}")
            if hasattr(adk_session, 'user_id'):
                print(f"[RunnerManager] ADK Session user_id: {adk_session.user_id}")
            
            # Store session reference
            runner_context["sessions"][session_id] = adk_session
            
            # Update runner context with the user_id used for this session
            runner_context["user_id"] = user_id
            
            self.logger.info(f"Created ADK Session {session_id} in Runner {runner_id}")
            print(f"[RunnerManager] Created ADK Session {session_id} with user_id: {user_id} in Runner {runner_id}")
            return session_id
            
        except Exception as e:
            self.logger.error(f"Failed to create Session {session_id} in Runner {runner_id}: {str(e)}")
            raise RuntimeError(f"Session creation failed: {str(e)}")

    async def _build_adk_agent(self, agent_config: AgentConfig) -> Any:
        """
        Build ADK Agent from AgentConfig.
        
        Args:
            agent_config: Agent configuration
            
        Returns:
            ADK Agent instance
        """
        try:
            from google.adk.agents import Agent
            from .model_factory import AdkModelFactory
            
            # Extract model from agent config
            model_config = getattr(agent_config, 'model_config', {})
            model_name = model_config.get('model', 'gemini-1.5-flash')
            
            print(f"[RunnerManager] Creating ADK Agent with model: {model_name}")
            
            # Use AdkModelFactory to create the appropriate model
            adk_model = AdkModelFactory.create_model(model_name, settings=None, enable_streaming=False)
            print(f"[RunnerManager] Created model via factory: {type(adk_model).__name__} - {adk_model}")
            
            # Create the real ADK agent with proper parameters
            adk_agent = Agent(
                name=getattr(agent_config, 'name', None) or agent_config.agent_type,
                description=getattr(agent_config, 'description', None) or f"ADK agent for {agent_config.agent_type}",
                instruction=getattr(agent_config, 'system_prompt', "You are a helpful AI assistant."),
                model=adk_model,  # Use factory-created model
                tools=[]  # TODO: Add tools from agent_config if needed
            )
            
            self.logger.info(f"Created real ADK Agent with model {model_name} via AdkModelFactory")
            print(f"[RunnerManager] Created real ADK Agent with model {model_name} via AdkModelFactory")
            return adk_agent
            
        except Exception as e:
            self.logger.error(f"Failed to build real ADK Agent: {str(e)}")
            print(f"[RunnerManager] Failed to build real ADK Agent: {str(e)}")
            
            # Fallback to mock agent
            class MockAdkAgent:
                def __init__(self, config):
                    self.config = config
                    
            self.logger.warning("Using MockAdkAgent as fallback")
            print(f"[RunnerManager] Using MockAdkAgent as fallback")
            return MockAdkAgent(agent_config)

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
            
            # Cleanup Runner resources
            if self._adk_available and runner_context["runner"]:
                runner = runner_context["runner"]
                if hasattr(runner, "shutdown"):
                    await runner.shutdown()
                    
                session_service = runner_context["session_service"]
                if hasattr(session_service, "shutdown"):
                    await session_service.shutdown()
            
            # Remove from config mapping
            config_hash = runner_context["config_hash"]
            if config_hash in self.config_to_runner:
                del self.config_to_runner[config_hash]
            
            # Remove runner context
            del self.runners[runner_id]
            
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
            "adk_available": self._adk_available,
            "runners": [
                {
                    "runner_id": rid,
                    "config_hash": ctx["config_hash"],
                    "session_count": len(ctx["sessions"]),
                    "created_at": ctx["created_at"]
                }
                for rid, ctx in self.runners.items()
            ]
        }