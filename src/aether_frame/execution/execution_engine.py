# -*- coding: utf-8 -*-
"""Execution Engine - Central orchestration for task processing."""

from typing import Optional

from ..config.settings import Settings
from ..contracts import TaskRequest, TaskResult, TaskStatus
from ..framework.framework_registry import FrameworkRegistry
from .task_router import TaskRouter


class ExecutionEngine:
    """
    ExecutionEngine orchestrates task execution by routing tasks to appropriate
    frameworks and managing the execution lifecycle.
    """

    def __init__(
        self, framework_registry: FrameworkRegistry, settings: Optional[Settings] = None
    ):
        """Initialize execution engine with framework registry and settings."""
        self.framework_registry = framework_registry
        self.task_router = TaskRouter(settings)
        self.settings = settings or Settings()

    async def execute_task(self, task_request: TaskRequest) -> TaskResult:
        """
        Execute a task by routing it to the appropriate framework.

        Args:
            task_request: The task to be executed

        Returns:
            TaskResult: The result of task execution
        """
        try:
            # Route task to determine execution strategy
            strategy = await self.task_router.route_task(task_request)

            # Get the appropriate framework adapter
            framework_adapter = await self.framework_registry.get_adapter(
                strategy.framework_type
            )

            if not framework_adapter:
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message=f"Framework {strategy.framework_type} not available",
                )

            # Pass TaskRequest and Strategy to framework adapter
            result = await framework_adapter.execute_task(task_request, strategy)
            return result

        except Exception as e:
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"Execution failed: {str(e)}",
            )

    async def get_execution_status(self, task_id: str) -> Optional[TaskResult]:
        """Get the status of a running or completed task."""
        # Implementation for task status tracking
        # TODO: Implement task status tracking
        return None

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        # Implementation for task cancellation
        # TODO: Implement task cancellation
        return False
