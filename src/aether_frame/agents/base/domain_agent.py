# -*- coding: utf-8 -*-
"""Domain Agent Abstract Base Class."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from ...contracts import AgentRequest, TaskResult


class DomainAgent(ABC):
    """
    Abstract base class for domain agents.

    Domain agents are framework-specific implementations that handle
    task execution within their respective frameworks while providing
    a unified interface for the core agent layer.
    """

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        """Initialize domain agent."""
        self.agent_id = agent_id
        self.config = config
        self._initialized = False

    @abstractmethod
    async def initialize(self):
        """Initialize the domain agent."""
        pass

    @abstractmethod
    async def execute(self, agent_request: AgentRequest) -> TaskResult:
        """
        Execute a task through this domain agent.

        Args:
            agent_request: The agent request containing task details

        Returns:
            TaskResult: The result of task execution
        """
        pass

    @abstractmethod
    async def get_state(self) -> Dict[str, Any]:
        """
        Get current agent state.

        Returns:
            Dict[str, Any]: Current agent state
        """
        pass

    @abstractmethod
    async def cleanup(self):
        """Cleanup agent resources."""
        pass

    @property
    def is_initialized(self) -> bool:
        """Check if agent is initialized."""
        return self._initialized

    async def validate_request(self, agent_request: AgentRequest) -> bool:
        """
        Validate agent request (default implementation).

        Args:
            agent_request: Request to validate

        Returns:
            bool: True if request is valid
        """
        if not agent_request.task_request:
            return False
        if not agent_request.task_request.task_id:
            return False
        return True
