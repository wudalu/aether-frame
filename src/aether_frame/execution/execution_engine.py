# -*- coding: utf-8 -*-
"""Execution Engine - Central orchestration for task processing."""

import logging
from typing import Optional
from datetime import datetime

from ..config.settings import Settings
from ..contracts import (
    ErrorCode,
    ExecutionContext,
    LiveExecutionResult,
    TaskRequest,
    TaskResult,
    TaskStatus,
    build_error,
)
from ..streaming import StreamSession, create_stream_session
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
        self.logger = logging.getLogger(__name__)

    async def execute_task(self, task_request: TaskRequest) -> TaskResult:
        """
        Execute a task by routing it to the appropriate framework.

        Args:
            task_request: The task to be executed

        Returns:
            TaskResult: The result of task execution
        """
        self.logger.info(f"Starting task execution - task_id: {task_request.task_id}, task_type: {task_request.task_type}, agent_id: {task_request.agent_id}")
            
        # Validate task request has proper context
        # Option 1: Continuing with existing agent (agent_id + session_id)
        # Option 2: Continuing existing session (session_id only, backward compatibility)
        # Option 3: Creating new agent/session (agent_config)
        if not (task_request.agent_id or task_request.session_id or task_request.agent_config):
            error_msg = "TaskRequest must have either agent_id (existing agent), session_id (existing session), or agent_config (new session)"
            self.logger.error(f"Context missing - {error_msg}")
            provided_context = {
                "agent_id": task_request.agent_id,
                "session_id": task_request.session_id,
                "has_agent_config": bool(task_request.agent_config),
            }
            error_payload = build_error(
                ErrorCode.REQUEST_VALIDATION,
                error_msg,
                source="execution_engine.validate_context",
                details=provided_context,
            )
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=error_msg,
                error=error_payload,
                metadata={
                    "error_stage": "execution_engine.validate_context",
                    "provided_context": provided_context,
                },
            )
            
        strategy = None  # Track strategy for better error reporting
        try:
            # Route task to determine execution strategy
            strategy = await self.task_router.route_task(task_request)
            self.logger.info(f"Task routing completed - framework: {strategy.framework_type.value}")

            # Get the appropriate framework adapter
            framework_adapter = await self.framework_registry.get_adapter(
                strategy.framework_type
            )

            if not framework_adapter:
                error_msg = f"Framework {strategy.framework_type} not available"
                self.logger.error(f"Framework adapter not available - {error_msg}")
                error_payload = build_error(
                    ErrorCode.FRAMEWORK_UNAVAILABLE,
                    error_msg,
                    source="execution_engine.get_adapter",
                    details={"framework": strategy.framework_type.value},
                )
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message=error_msg,
                    error=error_payload,
                    metadata={
                        "error_stage": "execution_engine.get_adapter",
                        "framework": strategy.framework_type.value,
                    },
                    session_id=task_request.session_id,
                    agent_id=task_request.agent_id,
                )
            
            self.logger.info(f"Framework adapter retrieved - type: {type(framework_adapter).__name__}")

            # Execute task through framework adapter
            result = await framework_adapter.execute_task(task_request, strategy)
            
            self.logger.info(f"Task execution completed - status: {result.status.value if result.status else 'unknown'}, session_id: {result.session_id}, agent_id: {result.agent_id}")
            return result

        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"Execution engine failed ({error_type}): {str(e)}"
            self.logger.error(f"Task execution failed - task_id: {task_request.task_id}, error: {error_msg}")
            framework_type = None
            try:
                framework_type = strategy.framework_type.value  # type: ignore[name-defined]
            except Exception:
                framework_type = None
            error_payload = build_error(
                ErrorCode.INTERNAL_ERROR,
                error_msg,
                source="execution_engine.execute_task",
                details={"error_type": error_type, "framework": framework_type},
            )
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=error_msg,
                error=error_payload,
                session_id=task_request.session_id,
                agent_id=task_request.agent_id,
                metadata={
                    "error_stage": "execution_engine.execute_task",
                    "error_type": error_type,
                    "framework": framework_type,
                },
            )

    async def execute_task_live(
        self, task_request: TaskRequest, context: ExecutionContext
    ) -> LiveExecutionResult:
        """
        Execute a task in live/interactive mode with real-time bidirectional
        communication.

        This method provides framework-agnostic routing for live execution,
        delegating the actual implementation to the appropriate framework
        adapter. All framework-specific logic (ADK, AutoGen, LangGraph) is
        contained within the adapters.

        Args:
            task_request: The task to be executed
            context: Execution context with user and session information

        Returns:
            LiveExecutionResult: Tuple of (event_stream, communicator) for
            real-time interaction

        Raises:
            ValueError: If the selected framework doesn't support live
            execution
            RuntimeError: If framework is not available or execution fails
        """
        try:
            # Route task to determine execution strategy (reuse existing logic)
            strategy = await self.task_router.route_task(task_request)

            # Get the appropriate framework adapter (reuse existing logic)
            framework_adapter = await self.framework_registry.get_adapter(
                strategy.framework_type
            )

            if not framework_adapter:
                raise RuntimeError(f"Framework {strategy.framework_type} not available")

            # Check if framework supports live execution
            if not framework_adapter.supports_live_execution():
                raise ValueError(
                    f"Framework {strategy.framework_type} doesn't support live execution"
                )

            # Delegate to framework-specific live execution
            # ALL framework-specific logic is in the adapter
            return await framework_adapter.execute_task_live(task_request, context)

        except Exception as e:
            # Let the exception bubble up for proper error handling
            raise RuntimeError(f"Live execution failed: {str(e)}") from e

    async def execute_task_live_session(
        self, task_request: TaskRequest, context: ExecutionContext
    ) -> StreamSession:
        """
        Execute a task in live mode and return a high-level StreamSession wrapper.

        This helper wraps ``execute_task_live`` and returns a ``StreamSession``
        object that exposes iteration, approval submission, and cancellation
        helpers geared toward API/service layers.
        """
        live_result = await self.execute_task_live(task_request, context)
        return create_stream_session(task_request.task_id, live_result)

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
