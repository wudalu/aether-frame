# -*- coding: utf-8 -*-
"""AI Assistant - System entry point for Aether Frame."""

import logging
from typing import Optional
from datetime import datetime

from ..config.settings import Settings
from ..contracts import (
    ErrorCode,
    ExecutionContext,
    FrameworkType,
    LiveExecutionResult,
    TaskRequest,
    TaskResult,
    TaskStatus,
    build_error,
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
        self.logger = logging.getLogger(__name__)

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
        self.logger.info(f"AI Assistant processing request - task_id: {task_request.task_id}, task_type: {task_request.task_type}")
            
        try:
            # Validate the request
            if not self._validate_request(task_request):
                validation_errors = self._get_validation_errors(task_request)
                error_msg = (
                    "Invalid task request: missing "
                    + ", ".join(validation_errors)
                    if validation_errors
                    else "Invalid task request: unknown validation failure"
                )
                self.logger.error(f"Request validation failed - task_id: {task_request.task_id}, errors: {validation_errors}")
                error_payload = build_error(
                    ErrorCode.REQUEST_VALIDATION,
                    error_msg,
                    source="ai_assistant.validate_request",
                    details={"validation_errors": validation_errors},
                )
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message=error_msg,
                    error=error_payload,
                    metadata={
                        "error_stage": "ai_assistant.validate_request",
                        "validation_errors": validation_errors,
                    },
                )
            
            self.logger.info(f"Request validation passed - task_id: {task_request.task_id}")

            # Process through execution engine
            result = await self.execution_engine.execute_task(task_request)
            
            self.logger.info(f"Processing completed - task_id: {result.task_id}, status: {result.status.value if result.status else 'unknown'}, has_response: {bool(result.messages)}")
            return result

        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"Processing failed in ai_assistant.process_request ({error_type}): {str(e)}"
            self.logger.error(f"AI Assistant processing failed - task_id: {task_request.task_id}, error: {error_msg}")
            error_payload = build_error(
                ErrorCode.INTERNAL_ERROR,
                error_msg,
                source="ai_assistant.process_request",
                details={"error_type": error_type},
            )
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=error_msg,
                error=error_payload,
                metadata={
                    "error_stage": "ai_assistant.process_request",
                    "error_type": error_type,
                },
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
    
    def _get_validation_errors(self, task_request: TaskRequest) -> list:
        """Get detailed validation errors for logging."""
        errors = []
        if not task_request.task_id:
            errors.append("missing_task_id")
        if not task_request.task_type:
            errors.append("missing_task_type")
        if not task_request.description:
            errors.append("missing_description")
        return errors

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
