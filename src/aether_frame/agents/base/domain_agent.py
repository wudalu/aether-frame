# -*- coding: utf-8 -*-
"""Domain Agent Abstract Base Class."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Tuple

from ...contracts import AgentRequest, LiveExecutionResult, TaskResult


class DomainAgent(ABC):
    """
    Abstract base class for domain agents.

    Domain agents are framework-specific implementations that handle
    task execution within their respective frameworks while providing
    a unified interface for the core agent layer.
    """

    def __init__(
        self,
        agent_id: str,
        config: Dict[str, Any],
        runtime_context: Dict[str, Any] = None,
    ):
        """Initialize domain agent with optional runtime context."""
        self.agent_id = agent_id
        self.config = config
        self.runtime_context = runtime_context or {}
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

    @abstractmethod
    async def execute_live(self, task_request) -> LiveExecutionResult:
        """
        Execute task in live/interactive mode with real-time streaming.

        Args:
            task_request: The task request to execute

        Returns:
            LiveExecutionResult: Tuple of (event_stream, communicator)
        """
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

    async def initialize_with_runtime(self):
        """
        Initialize domain agent with runtime context (default implementation).

        Calls the standard initialize() method. Domain agents can override
        this method to perform runtime-aware initialization.
        """
        await self.initialize()

    async def execute_with_runtime(
        self, agent_request: AgentRequest, runtime_context: Dict[str, Any]
    ) -> TaskResult:
        """
        Execute task with runtime context (default implementation).

        Falls back to standard execute() method. Domain agents can override
        this method to utilize runtime context for more efficient execution.

        Args:
            agent_request: The agent request containing task details
            runtime_context: Runtime context from framework adapter

        Returns:
            TaskResult: The result of task execution
        """
        return await self.execute(agent_request)

    async def execute_live_with_runtime(
        self, agent_request: AgentRequest, runtime_context: Dict[str, Any]
    ) -> LiveExecutionResult:
        """
        Execute task in live mode with runtime context (default implementation).

        Domain agents should override this method to provide live execution
        capabilities with bidirectional communication.

        Args:
            agent_request: The agent request containing task details
            runtime_context: Runtime context from framework adapter

        Returns:
            LiveExecutionResult: Tuple of (event_stream, communicator)
        """

        # Default implementation returns error
        async def error_stream():
            from ...contracts import TaskChunkType, TaskStreamChunk

            yield TaskStreamChunk(
                task_id=agent_request.task_request.task_id,
                chunk_type=TaskChunkType.ERROR,
                sequence_id=0,
                content="Live execution not implemented for this domain agent",
                is_final=True,
                metadata={"error_type": "not_implemented"},
            )

        class NotImplementedCommunicator:
            def send_user_response(self, approved: bool):
                pass

            def send_user_message(self, message: str):
                pass

            def send_cancellation(self, reason: str):
                pass

            def close(self):
                pass

        return (error_stream(), NotImplementedCommunicator())
