# -*- coding: utf-8 -*-
"""Framework Adapter Abstract Base Class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ...contracts import AgentRequest, FrameworkType, TaskRequest, TaskResult
from ...execution.task_router import ExecutionStrategy


class FrameworkAdapter(ABC):
    """
    Abstract base class for framework adapters.

    Each framework implementation must provide an adapter that implements
    this interface to enable unified task execution through the framework
    abstraction layer.
    """

    @property
    @abstractmethod
    def framework_type(self) -> FrameworkType:
        """Return the framework type this adapter supports."""
        pass

    @abstractmethod
    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the framework adapter with configuration.

        Args:
            config: Framework-specific configuration
        """
        pass

    @abstractmethod
    async def execute_task(
        self, task_request: TaskRequest, strategy: ExecutionStrategy
    ) -> TaskResult:
        """
        Execute a task through this framework with the given strategy.

        Args:
            task_request: The universal task request
            strategy: Execution strategy containing framework type and execution mode

        Returns:
            TaskResult: The result of task execution
        """
        pass

    def _convert_task_to_agent_request(
        self, task_request: TaskRequest, strategy: ExecutionStrategy
    ) -> "AgentRequest":
        """
        Convert TaskRequest to AgentRequest using Strategy guidance.

        This method handles the conversion from universal TaskRequest to
        framework-specific AgentRequest, using the strategy to determine
        agent type and configuration.

        Args:
            task_request: The universal task request
            strategy: Execution strategy with framework and execution mode info

        Returns:
            AgentRequest: Framework-specific agent request
        """
        # Map task type to agent type based on strategy
        agent_type = self._map_task_type_to_agent(
            task_request.task_type,
            strategy.runtime_options.get("complexity_level", "simple"),
        )

        # Import here to avoid circular imports
        from ...contracts import AgentConfig, AgentRequest

        # Extract agent config from strategy execution config
        execution_config = strategy.execution_config.copy()

        # Get timeout with fallback
        timeout = execution_config.get("timeout")
        if timeout is None and task_request.execution_context:
            timeout = task_request.execution_context.timeout

        # Create agent config using strategy guidance with proper types
        agent_config = AgentConfig(
            agent_type=agent_type,
            framework_type=strategy.framework_type,
            capabilities=execution_config.get("available_tools", []),
            max_iterations=execution_config.get("max_iterations", 10),
            timeout=timeout or 300,
            system_prompt=execution_config.get("system_prompt"),
            model_config=execution_config.get("model_config", {}),
            behavior_settings=execution_config.get("behavior_settings", {}),
            memory_config=execution_config.get("memory_config", {}),
            tool_permissions=execution_config.get("required_capabilities", []),
        )

        # Create agent request
        agent_request = AgentRequest(
            agent_type=agent_type,
            framework_type=strategy.framework_type,
            task_request=task_request,
            agent_config=agent_config,
            runtime_options=strategy.runtime_options,
        )

        return agent_request

    def _map_task_type_to_agent(
        self, task_type: str, complexity_level: str = "simple"
    ) -> str:
        """
        Map task type to agent type - Framework Layer responsibility.

        This logic was moved from TaskRouter to maintain proper layer separation.
        """
        # Default task type to agent type mapping
        task_to_agent_mapping = {
            "chat": "conversational_agent",
            "analysis": "analytical_agent",
            "code": "coding_agent",
            "research": "research_agent",
            "planning": "planning_agent",
            "orchestration": "orchestration_agent",
        }

        return task_to_agent_mapping.get(task_type, "general_agent")

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if the framework is available and ready to process tasks.

        Returns:
            bool: True if framework is available, False otherwise
        """
        pass

    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """
        Get list of capabilities supported by this framework.

        Returns:
            List[str]: List of capability names
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of the framework.

        Returns:
            Dict[str, Any]: Health status information
        """
        pass

    @abstractmethod
    async def shutdown(self):
        """Shutdown the framework adapter and cleanup resources."""
        pass

    async def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate framework-specific configuration.

        Args:
            config: Configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        # Default implementation - can be overridden
        return True

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get framework performance metrics.

        Returns:
            Dict[str, Any]: Performance metrics
        """
        # Default implementation - can be overridden
        return {}
