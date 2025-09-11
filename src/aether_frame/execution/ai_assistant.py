# -*- coding: utf-8 -*-
"""AI Assistant - System entry point for Aether Frame."""

from typing import Optional

from ..config.settings import Settings
from ..contracts import TaskRequest, TaskResult, TaskStatus
from ..framework.framework_registry import FrameworkRegistry
from .execution_engine import ExecutionEngine


class AIAssistant:
    """
    AI Assistant serves as the main entry point for the Aether Frame system.

    It provides a unified interface for processing task requests and handles
    request validation, routing to appropriate execution engines, and response
    formatting.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize AI Assistant with configuration."""
        self.settings = settings or Settings()
        self.framework_registry = FrameworkRegistry()
        self.execution_engine = ExecutionEngine(
            framework_registry=self.framework_registry, settings=self.settings
        )

    async def process_request(self, task_request: TaskRequest) -> TaskResult:
        """
        Process a task request and return the result.

        Args:
            task_request: The task to be processed

        Returns:
            TaskResult: The result of task processing
        """
        try:
            # Validate the request
            if not self._validate_request(task_request):
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message="Invalid task request",
                )

            # Process through execution engine
            result = await self.execution_engine.execute_task(task_request)
            return result

        except Exception as e:
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"Processing failed: {str(e)}",
            )

    def _validate_request(self, task_request: TaskRequest) -> bool:
        """Validate the incoming task request."""
        if not task_request.task_id:
            return False
        if not task_request.task_type:
            return False
        if not task_request.description:
            return False
        return True

    async def health_check(self) -> dict:
        """Check system health status."""
        return {
            "status": "healthy",
            "frameworks": await self.framework_registry.get_available_frameworks(),
            "version": (
                self.settings.version
                if hasattr(self.settings, "version")
                else "unknown"
            ),
        }
