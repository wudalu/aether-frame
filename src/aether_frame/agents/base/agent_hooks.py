# -*- coding: utf-8 -*-
"""Agent Hooks Interface."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ...contracts import AgentRequest, TaskResult

if TYPE_CHECKING:
    pass


class AgentHooks(ABC):
    """
    Abstract interface for agent lifecycle hooks.

    Provides extension points for framework-specific functionality
    such as memory management, observability, and preprocessing.
    """

    @abstractmethod
    async def on_agent_created(self):
        """Hook called when agent is created."""
        pass

    @abstractmethod
    async def before_execution(self, agent_request: AgentRequest):
        """
        Hook called before task execution.

        Args:
            agent_request: The agent request being processed
        """
        pass

    @abstractmethod
    async def after_execution(self, agent_request: AgentRequest, result: TaskResult):
        """
        Hook called after task execution.

        Args:
            agent_request: The agent request that was processed
            result: The result of task execution
        """
        pass

    @abstractmethod
    async def on_error(self, agent_request: AgentRequest, error: Exception):
        """
        Hook called when execution error occurs.

        Args:
            agent_request: The agent request that failed
            error: The error that occurred
        """
        pass

    @abstractmethod
    async def on_agent_destroyed(self):
        """Hook called when agent is destroyed."""
        pass
