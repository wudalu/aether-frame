# -*- coding: utf-8 -*-
"""Agent Manager Implementation - Agent Lifecycle Management."""

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from ..contracts import AgentConfig, FrameworkType
from .base.domain_agent import DomainAgent


class AgentManager:
    """
    Agent Manager focused on agent lifecycle management.

    Responsibilities:
    - Agent lifecycle management (create, store, cleanup)
    - Agent ID generation and mapping
    - Agent resource tracking and cleanup
    - Health monitoring of managed agents

    No longer handles:
    - Direct task execution (moved to FrameworkAdapters)
    - Framework-specific agent creation (moved to FrameworkAdapters)
    - Request routing (moved to ExecutionEngine)
    - Session management (moved to FrameworkAdapters)
    """

    def __init__(self):
        """Initialize agent manager."""
        self._agents: Dict[str, DomainAgent] = {}  # agent_id -> agent
        self._agent_configs: Dict[str, AgentConfig] = {}  # agent_id -> config
        self._agent_metadata: Dict[str, Dict[str, Any]] = {}  # agent_id -> metadata
        self._agent_factories: Dict[FrameworkType, Callable] = (
            {}
        )  # framework -> factory

    # Agent Lifecycle Management

    def generate_agent_id(self, prefix: str = "agent") -> str:
        """Generate unique agent ID."""
        return f"{prefix}_{uuid4().hex[:12]}"

    async def create_agent(
        self,
        agent_factory: Callable[[], DomainAgent],
        agent_config: Optional[AgentConfig] = None,
        agent_id: Optional[str] = None,
    ) -> str:
        """
        Create new agent using provided factory.

        Args:
            agent_factory: Factory function to create agent
            agent_config: Configuration for new agent
            agent_id: Optional specific agent ID to use

        Returns:
            str: Agent ID for the created agent
        """
        if agent_id is None:
            agent_id = self.generate_agent_id()
        
        if agent_id in self._agents:
            raise ValueError(f"Agent ID {agent_id} already exists")

        # Create agent using factory
        agent = await agent_factory()

        # Store agent and metadata
        self._agents[agent_id] = agent
        if agent_config:
            self._agent_configs[agent_id] = agent_config

        self._agent_metadata[agent_id] = {
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

        return agent_id

    async def get_agent(self, agent_id: str) -> Optional[DomainAgent]:
        """
        Get agent by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            DomainAgent: Agent instance or None if not found
        """
        if agent_id in self._agents:
            # Update last activity time
            self._agent_metadata[agent_id]["last_activity"] = datetime.now()
            return self._agents[agent_id]
        return None

    async def cleanup_agent(self, agent_id: str) -> bool:
        """
        Cleanup all resources for an agent.

        Args:
            agent_id: Agent identifier to cleanup

        Returns:
            bool: True if cleanup successful, False otherwise
        """
        if agent_id not in self._agents:
            return False

        try:
            # Cleanup agent resources
            agent = self._agents[agent_id]
            await agent.cleanup()

            # Remove from tracking
            del self._agents[agent_id]
            if agent_id in self._agent_configs:
                del self._agent_configs[agent_id]
            if agent_id in self._agent_metadata:
                del self._agent_metadata[agent_id]

            return True
        except Exception as e:
            # Log but don't fail
            print(f"Warning: Failed to cleanup agent {agent_id}: {str(e)}")
            return False

    async def cleanup_expired_agents(
        self, max_idle_time: timedelta = None
    ) -> List[str]:
        """
        Cleanup agents that have been idle for too long.

        Args:
            max_idle_time: Maximum idle time before cleanup (default: 1 hour)

        Returns:
            List of agent IDs that were cleaned up
        """
        if max_idle_time is None:
            max_idle_time = timedelta(hours=1)

        now = datetime.now()
        expired_agents = []

        for agent_id, metadata in self._agent_metadata.items():
            last_activity = metadata.get(
                "last_activity", metadata.get("created_at", now)
            )
            if now - last_activity > max_idle_time:
                expired_agents.append(agent_id)

        # Cleanup expired agents
        cleaned_agents = []
        for agent_id in expired_agents:
            if await self.cleanup_agent(agent_id):
                cleaned_agents.append(agent_id)

        return cleaned_agents

    # Health and Monitoring

    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status information for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Dict with agent status or None if not found
        """
        if agent_id not in self._agents:
            return None

        metadata = self._agent_metadata[agent_id]
        agent = self._agents[agent_id]
        
        return {
            "agent_id": agent_id,
            "agent_type": metadata.get("agent_type", "unknown"),
            "framework_type": metadata.get("framework_type", "unknown"),
            "created_at": metadata.get("created_at"),
            "last_activity": metadata.get("last_activity"),
            "is_healthy": await agent.health_check() if hasattr(agent, "health_check") else True,
        }

    def get_active_agent_ids(self) -> List[str]:
        """Get list of all active agent IDs."""
        return list(self._agents.keys())

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get manager statistics.

        Returns:
            Dict with current statistics
        """
        total_agents = len(self._agents)
        
        # Count by agent type
        agent_types = {}
        for metadata in self._agent_metadata.values():
            agent_type = metadata.get("agent_type", "unknown")
            agent_types[agent_type] = agent_types.get(agent_type, 0) + 1

        # Count by framework type  
        framework_types = {}
        for metadata in self._agent_metadata.values():
            framework_type = metadata.get("framework_type", "unknown")
            framework_types[str(framework_type)] = framework_types.get(str(framework_type), 0) + 1

        return {
            "total_agents": total_agents,
            "agent_types": agent_types,
            "framework_types": framework_types,
            "registered_factories": len(self._agent_factories),
        }

    # Framework Factory Management

    def register_agent_factory(
        self, framework_type: FrameworkType, factory: Callable
    ):
        """Register an agent factory for a framework type."""
        self._agent_factories[framework_type] = factory

    def get_agent_factory(self, framework_type: FrameworkType) -> Optional[Callable]:
        """Get agent factory for a framework type."""
        return self._agent_factories.get(framework_type)

    # Lifecycle Management

    async def health_check(self) -> bool:
        """
        Check health of all managed agents.

        Returns:
            bool: True if all agents are healthy
        """
        try:
            for agent_id, agent in self._agents.items():
                if hasattr(agent, "health_check"):
                    is_healthy = await agent.health_check()
                    if not is_healthy:
                        print(f"Agent {agent_id} failed health check")
                        return False
            return True
        except Exception as e:
            print(f"Health check failed: {str(e)}")
            return False

    async def shutdown(self):
        """Shutdown all agents and cleanup resources."""
        try:
            agent_ids = list(self._agents.keys())
            for agent_id in agent_ids:
                await self.cleanup_agent(agent_id)
            
            self._agent_factories.clear()
            print(f"Successfully shutdown {len(agent_ids)} agents")
        except Exception as e:
            print(f"Warning: Shutdown encountered errors: {str(e)}")