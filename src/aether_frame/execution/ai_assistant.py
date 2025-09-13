# -*- coding: utf-8 -*-
"""AI Assistant - System entry point for Aether Frame."""

from typing import Optional

from ..config.settings import Settings
from ..contracts import (
    ExecutionContext,
    FrameworkType,
    LiveExecutionResult,
    TaskRequest,
    TaskResult,
    TaskStatus,
)
from .execution_engine import ExecutionEngine


class AIAssistant:
    """
    AI Assistant serves as the main entry point for the Aether Frame system.

    It provides a unified interface for processing task requests and handles
    request validation, routing to appropriate execution engines, and response
    formatting.
    """

    def __init__(
        self, execution_engine: ExecutionEngine, settings: Optional[Settings] = None
    ):
        """Initialize AI Assistant with pre-initialized execution engine."""
        self.execution_engine = execution_engine
        self.settings = settings or Settings()

    @classmethod
    async def create(cls, settings: Optional[Settings] = None) -> "AIAssistant":
        """
        Alternative constructor using bootstrap.

        Args:
            settings: Optional application settings

        Returns:
            AIAssistant: Fully initialized AI Assistant
        """
        from ..bootstrap import create_ai_assistant

        return await create_ai_assistant(settings)

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

    async def start_live_session(
        self, task_request: TaskRequest
    ) -> LiveExecutionResult:
        """
        Start a live interactive session for real-time task processing.

        Args:
            task_request: The task to be processed in live mode

        Returns:
            LiveExecutionResult: Tuple of (event_stream, communicator) for
            bidirectional communication
        """
        try:
            # Validate the request
            if not self._validate_request(task_request):
                raise ValueError("Invalid task request")

            # Create execution context - use existing one or create minimal one
            if task_request.execution_context:
                execution_context = task_request.execution_context
            else:
                execution_context = ExecutionContext(
                    execution_id=f"live_{task_request.task_id}",
                    framework_type=FrameworkType.ADK,
                    execution_mode="live",
                    timeout=300,
                )

            # Delegate to execution engine for live execution
            return await self.execution_engine.execute_task_live(
                task_request, execution_context
            )

        except Exception as e:
            raise RuntimeError(f"Live session failed to start: {str(e)}")

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
            "version": (
                self.settings.app_version
                if hasattr(self.settings, "app_version")
                else "unknown"
            ),
        }
