# -*- coding: utf-8 -*-
"""Agent Manager Implementation - Session and Lifecycle Management."""

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from ..contracts import AgentConfig, FrameworkType
from .base.domain_agent import DomainAgent


class AgentManager:
    """
    Simplified Agent Manager focused on session-based lifecycle management.

    Refactored to focus solely on:
    - Session-based agent lifecycle management
    - Long-lived agent instances for persistent sessions
    - Agent resource tracking and cleanup
    - Health monitoring of managed agents

    No longer handles:
    - Direct task execution (moved to FrameworkAdapters)
    - Framework-specific agent creation (moved to FrameworkAdapters)
    - Request routing (moved to ExecutionEngine)
    """

    def __init__(self):
        """Initialize simplified agent manager."""
        self._session_agents: Dict[str, DomainAgent] = {}  # session_id -> agent
        self._agent_configs: Dict[str, AgentConfig] = {}  # session_id -> config
        self._session_metadata: Dict[str, Dict[str, Any]] = {}  # session_id -> metadata
        self._agent_factories: Dict[FrameworkType, Callable] = (
            {}
        )  # framework -> factory

    # Session-based Agent Lifecycle Management

    async def get_or_create_session_agent(
        self,
        session_id: str,
        agent_factory: Callable[[], DomainAgent],
        agent_config: Optional[AgentConfig] = None,
    ) -> DomainAgent:
        """
        Get existing session agent or create new one using provided factory.

        This is the primary interface for session-based agent management.

        Args:
            session_id: Unique session identifier
            agent_factory: Factory function to create agent if needed
            agent_config: Optional configuration for new agent

        Returns:
            DomainAgent: Existing or newly created agent for the session
        """
        if session_id in self._session_agents:
            # Update last activity time
            self._session_metadata[session_id]["last_activity"] = datetime.now()
            return self._session_agents[session_id]

        # Create new session agent using factory
        agent = await agent_factory()

        # Store agent and metadata
        self._session_agents[session_id] = agent
        if agent_config:
            self._agent_configs[session_id] = agent_config

        self._session_metadata[session_id] = {
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "agent_type": (
                getattr(agent_config, "agent_type", "unknown")
                if agent_config
                else "unknown"
            ),
            "framework_type": (
                getattr(agent_config, "framework_type", None) if agent_config else None
            ),
        }

        return agent

    async def get_session_agent(self, session_id: str) -> Optional[DomainAgent]:
        """
        Get existing session agent without creating new one.

        Args:
            session_id: Session identifier

        Returns:
            DomainAgent if exists, None otherwise
        """
        if session_id in self._session_agents:
            # Update last activity time
            self._session_metadata[session_id]["last_activity"] = datetime.now()
            return self._session_agents[session_id]
        return None

    async def cleanup_session(self, session_id: str) -> bool:
        """
        Cleanup all resources for a session.

        Args:
            session_id: Session identifier to cleanup

        Returns:
            bool: True if cleanup successful, False otherwise
        """
        if session_id not in self._session_agents:
            return False

        try:
            # Cleanup agent resources
            agent = self._session_agents[session_id]
            await agent.cleanup()

            # Remove from tracking
            del self._session_agents[session_id]
            if session_id in self._agent_configs:
                del self._agent_configs[session_id]
            if session_id in self._session_metadata:
                del self._session_metadata[session_id]

            return True
        except Exception as e:
            # Log but don't fail
            print(f"Warning: Failed to cleanup session {session_id}: {str(e)}")
            return False

    async def cleanup_expired_sessions(
        self, max_idle_time: timedelta = None
    ) -> List[str]:
        """
        Cleanup sessions that have been idle for too long.

        Args:
            max_idle_time: Maximum idle time before cleanup (default: 1 hour)

        Returns:
            List of session IDs that were cleaned up
        """
        if max_idle_time is None:
            max_idle_time = timedelta(hours=1)

        now = datetime.now()
        expired_sessions = []

        for session_id, metadata in self._session_metadata.items():
            last_activity = metadata.get(
                "last_activity", metadata.get("created_at", now)
            )
            if now - last_activity > max_idle_time:
                expired_sessions.append(session_id)

        # Cleanup expired sessions
        cleaned_sessions = []
        for session_id in expired_sessions:
            if await self.cleanup_session(session_id):
                cleaned_sessions.append(session_id)

        return cleaned_sessions

    # Health and Monitoring

    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status information for a session.

        Args:
            session_id: Session identifier

        Returns:
            Dict with session status or None if not found
        """
        if session_id not in self._session_agents:
            return None

        agent = self._session_agents[session_id]
        metadata = self._session_metadata.get(session_id, {})
        config = self._agent_configs.get(session_id)

        return {
            "session_id": session_id,
            "agent_type": metadata.get("agent_type"),
            "framework_type": metadata.get("framework_type"),
            "created_at": metadata.get("created_at"),
            "last_activity": metadata.get("last_activity"),
            "is_initialized": getattr(agent, "is_initialized", True),
            "config": config.__dict__ if config else None,
        }

    async def list_active_sessions(self) -> List[str]:
        """
        List all active session identifiers.

        Returns:
            List of active session IDs
        """
        return list(self._session_agents.keys())

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get overall health status of the agent manager.

        Returns:
            Dict containing health information
        """
        now = datetime.now()
        total_sessions = len(self._session_agents)

        # Calculate session age statistics
        if self._session_metadata:
            ages = [
                (now - meta.get("created_at", now)).total_seconds()
                for meta in self._session_metadata.values()
            ]
            avg_age = sum(ages) / len(ages) if ages else 0
            max_age = max(ages) if ages else 0
        else:
            avg_age = max_age = 0

        # Group by framework type
        framework_counts = {}
        for metadata in self._session_metadata.values():
            fw_type = metadata.get("framework_type")
            if fw_type:
                framework_counts[fw_type.value] = (
                    framework_counts.get(fw_type.value, 0) + 1
                )

        return {
            "status": "healthy",
            "total_sessions": total_sessions,
            "framework_distribution": framework_counts,
            "avg_session_age_seconds": avg_age,
            "max_session_age_seconds": max_age,
            "registered_factories": len(self._agent_factories),
        }

    # Factory Management (Future Enhancement)

    def register_agent_factory(
        self,
        framework_type: FrameworkType,
        factory: Callable[[AgentConfig], DomainAgent],
    ):
        """
        Register agent factory for a framework type.

        This enables the AgentManager to create agents for different frameworks
        when session-based management is needed.

        Args:
            framework_type: Framework type to register factory for
            factory: Factory function to create agents
        """
        self._agent_factories[framework_type] = factory

    async def create_agent_for_session(
        self, session_id: str, agent_config: AgentConfig
    ) -> Optional[DomainAgent]:
        """
        Create agent for session using registered factory.

        Args:
            session_id: Session identifier
            agent_config: Agent configuration

        Returns:
            DomainAgent if factory available, None otherwise
        """
        framework_type = agent_config.framework_type

        if framework_type not in self._agent_factories:
            print(f"Warning: No factory registered for framework {framework_type}")
            return None

        factory = self._agent_factories[framework_type]
        agent = await factory(agent_config)

        # Store in session management
        self._session_agents[session_id] = agent
        self._agent_configs[session_id] = agent_config
        self._session_metadata[session_id] = {
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "agent_type": agent_config.agent_type,
            "framework_type": framework_type,
        }

        return agent

    # Legacy Methods (Deprecated - For Compatibility)

    async def create_agent(self, agent_config: AgentConfig) -> str:
        """
        DEPRECATED: Use get_or_create_session_agent() instead.

        Legacy method for backward compatibility. Creates a temporary session.
        """
        import uuid

        session_id = f"legacy_{uuid.uuid4().hex[:8]}"

        if agent_config.framework_type in self._agent_factories:
            factory = self._agent_factories[agent_config.framework_type]
            await self.get_or_create_session_agent(
                session_id, lambda: factory(agent_config), agent_config
            )
            return session_id
        else:
            raise NotImplementedError(
                f"No factory registered for {agent_config.framework_type}. "
                f"Use FrameworkAdapter direct creation instead."
            )

    async def destroy_agent(self, agent_id: str):
        """
        DEPRECATED: Use cleanup_session() instead.

        Legacy method for backward compatibility.
        """
        await self.cleanup_session(agent_id)

    async def list_agents(self) -> List[str]:
        """
        DEPRECATED: Use list_active_sessions() instead.

        Legacy method for backward compatibility.
        """
        return await self.list_active_sessions()
