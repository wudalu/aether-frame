# -*- coding: utf-8 -*-
"""Agent Manager Interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ...contracts import AgentConfig, AgentRequest, AgentResponse


class AgentManager(ABC):
    """
    Abstract interface for agent lifecycle management.

    Provides unified agent management capabilities across different frameworks,
    handling agent creation, configuration, execution, and cleanup.
    """

    @abstractmethod
    async def create_agent(self, agent_config: AgentConfig) -> str:
        """
        Create a new agent instance.

        Args:
            agent_config: Configuration for the agent

        Returns:
            str: Agent identifier
        """
        pass

    @abstractmethod
    async def configure_agent(self, agent_id: str, config: Dict[str, Any]):
        """
        Configure an existing agent.

        Args:
            agent_id: Agent identifier
            config: Configuration updates
        """
        pass

    @abstractmethod
    async def execute_agent(self, agent_request: AgentRequest) -> AgentResponse:
        """
        Execute an agent with the given request.

        Args:
            agent_request: Request containing execution details

        Returns:
            AgentResponse: Response from agent execution
        """
        pass

    @abstractmethod
    async def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """
        Get current status of an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Dict[str, Any]: Agent status information
        """
        pass

    @abstractmethod
    async def list_agents(self) -> List[str]:
        """
        List all active agent identifiers.

        Returns:
            List[str]: List of agent identifiers
        """
        pass

    @abstractmethod
    async def destroy_agent(self, agent_id: str):
        """
        Destroy an agent and cleanup resources.

        Args:
            agent_id: Agent identifier
        """
        pass

    @abstractmethod
    async def get_agent_metrics(self, agent_id: str) -> Dict[str, Any]:
        """
        Get performance metrics for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Dict[str, Any]: Agent performance metrics
        """
        pass

    async def restart_agent(self, agent_id: str):
        """
        Restart an agent (default implementation).

        Args:
            agent_id: Agent identifier
        """
        # Get current config
        status = await self.get_agent_status(agent_id)
        config = status.get("config", {})

        # Destroy and recreate
        await self.destroy_agent(agent_id)
        return await self.create_agent(AgentConfig(**config))
