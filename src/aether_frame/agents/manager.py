# -*- coding: utf-8 -*-
"""Agent Manager Implementation."""

from typing import Any, Dict, List, Optional

from ..contracts import AgentConfig, AgentRequest, AgentResponse, FrameworkType
from ..framework.base.agent_manager import AgentManager as AgentManagerInterface
from .base.domain_agent import DomainAgent


class AgentManager(AgentManagerInterface):
    """
    Unified agent lifecycle management implementation.

    Provides agent creation, configuration, execution, and cleanup
    capabilities across different frameworks through the domain agent
    abstraction layer.
    """

    def __init__(self):
        """Initialize agent manager."""
        self._agents: Dict[str, DomainAgent] = {}
        self._agent_configs: Dict[str, AgentConfig] = {}
        self._agent_counter = 0

    async def create_agent(self, agent_config: AgentConfig) -> str:
        """
        Create a new agent instance.

        Args:
            agent_config: Configuration for the agent

        Returns:
            str: Agent identifier
        """
        # Generate unique agent ID
        agent_id = f"{agent_config.framework_type.value}_agent_{self._agent_counter}"
        self._agent_counter += 1

        # Create framework-specific domain agent
        domain_agent = await self._create_domain_agent(agent_id, agent_config)

        # Store agent and config
        self._agents[agent_id] = domain_agent
        self._agent_configs[agent_id] = agent_config

        return agent_id

    async def configure_agent(self, agent_id: str, config: Dict[str, Any]):
        """
        Configure an existing agent.

        Args:
            agent_id: Agent identifier
            config: Configuration updates
        """
        if agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")

        # Update stored config
        if agent_id in self._agent_configs:
            # Update existing config
            for key, value in config.items():
                setattr(self._agent_configs[agent_id], key, value)

        # Apply configuration to domain agent
        agent = self._agents[agent_id]
        agent.config.update(config)

    async def execute_agent(self, agent_request: AgentRequest) -> AgentResponse:
        """
        Execute an agent with the given request.

        Args:
            agent_request: Request containing execution details

        Returns:
            AgentResponse: Response from agent execution
        """
        agent_id = agent_request.agent_id
        if not agent_id or agent_id not in self._agents:
            raise ValueError(f"Agent {agent_id} not found")

        try:
            # Execute through domain agent
            agent = self._agents[agent_id]
            task_result = await agent.execute(agent_request)

            # Get agent state for response
            agent_state = await agent.get_state()

            return AgentResponse(
                agent_id=agent_id,
                agent_type=agent_request.agent_type,
                task_result=task_result,
                agent_state=agent_state,
                metadata=agent_request.metadata,
            )

        except Exception as e:
            return AgentResponse(
                agent_id=agent_id,
                agent_type=agent_request.agent_type,
                error_details=f"Agent execution failed: {str(e)}",
                metadata=agent_request.metadata,
            )

    async def get_agent_status(self, agent_id: str) -> Dict[str, Any]:
        """
        Get current status of an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Dict[str, Any]: Agent status information
        """
        if agent_id not in self._agents:
            return {"status": "not_found"}

        agent = self._agents[agent_id]
        agent_state = await agent.get_state()

        return {
            "agent_id": agent_id,
            "status": "active" if agent.is_initialized else "inactive",
            "config": (
                self._agent_configs.get(agent_id, {}).__dict__
                if agent_id in self._agent_configs
                else {}
            ),
            "state": agent_state,
        }

    async def list_agents(self) -> List[str]:
        """
        List all active agent identifiers.

        Returns:
            List[str]: List of agent identifiers
        """
        return list(self._agents.keys())

    async def destroy_agent(self, agent_id: str):
        """
        Destroy an agent and cleanup resources.

        Args:
            agent_id: Agent identifier
        """
        if agent_id not in self._agents:
            return

        # Cleanup domain agent
        agent = self._agents[agent_id]
        await agent.cleanup()

        # Remove from registry
        del self._agents[agent_id]
        if agent_id in self._agent_configs:
            del self._agent_configs[agent_id]

    async def get_agent_metrics(self, agent_id: str) -> Dict[str, Any]:
        """
        Get performance metrics for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Dict[str, Any]: Agent performance metrics
        """
        if agent_id not in self._agents:
            return {}

        # Get metrics from domain agent state
        agent_state = await self._agents[agent_id].get_state()
        return agent_state.get("metrics", {})

    async def _create_domain_agent(
        self, agent_id: str, agent_config: AgentConfig
    ) -> DomainAgent:
        """Create framework-specific domain agent."""
        framework_type = agent_config.framework_type

        if framework_type == FrameworkType.ADK:
            from .adk.adk_domain_agent import AdkDomainAgent

            agent = AdkDomainAgent(agent_id=agent_id, config=agent_config.__dict__)
        elif framework_type == FrameworkType.AUTOGEN:
            # TODO: Implement AutoGen domain agent
            raise NotImplementedError("AutoGen framework not yet implemented")
        elif framework_type == FrameworkType.LANGGRAPH:
            # TODO: Implement LangGraph domain agent
            raise NotImplementedError("LangGraph framework not yet implemented")
        else:
            raise ValueError(f"Unsupported framework type: {framework_type}")

        # Initialize the domain agent
        await agent.initialize()

        return agent
