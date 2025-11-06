# -*- coding: utf-8 -*-
"""ADK Agent Hooks Implementation."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from ...contracts import AgentRequest, TaskResult, TaskStatus
from ..base.agent_hooks import AgentHooks
from ...infrastructure.adk.adk_observer import AdkObserver

if TYPE_CHECKING:
    from .adk_domain_agent import AdkDomainAgent


logger = logging.getLogger(__name__)


class AdkAgentHooks(AgentHooks):
    """
    ADK-specific agent hooks for memory and observability integration.

    Provides integration with ADK's native memory management (context.state)
    and observability features throughout the agent execution lifecycle.
    """

    def __init__(self, agent: "AdkDomainAgent"):
        """Initialize ADK agent hooks."""
        self.agent = agent
        self.adk_context = None
        self.memory_adapter = None
        self.observer = AdkObserver(getattr(agent, "adk_client", None))
        self._active_executions: Dict[str, Dict[str, Any]] = {}

    def _build_observer_metadata(self, agent_request: AgentRequest) -> Dict[str, Any]:
        """Collect execution context metadata for observer logging."""
        metadata: Dict[str, Any] = {}

        task = agent_request.task_request if agent_request else None
        runtime_context = getattr(self.agent, "runtime_context", {}) or {}

        metadata["task_id"] = getattr(task, "task_id", None)
        metadata["agent_id"] = getattr(self.agent, "agent_id", None)

        chat_session_id = getattr(task, "session_id", None)
        if chat_session_id:
            metadata["chat_session_id"] = chat_session_id

        if agent_request and getattr(agent_request, "session_id", None):
            request_session = agent_request.session_id
            if request_session and request_session != metadata.get("chat_session_id"):
                metadata["request_session_id"] = request_session

        adk_session_id = runtime_context.get("session_id")
        if adk_session_id:
            metadata["adk_session_id"] = adk_session_id

        runner_id = runtime_context.get("runner_id")
        if runner_id:
            metadata["runner_id"] = runner_id

        user_id = runtime_context.get("user_id")
        if user_id:
            metadata["user_id"] = user_id

        execution_id = (
            runtime_context.get("execution_id")
            or runtime_context.get("metadata", {}).get("execution_id")
            or (agent_request.metadata.get("execution_id") if agent_request else None)
        )
        if execution_id:
            metadata["execution_id"] = execution_id

        allowed_keys = (
            "phase",
            "request_mode",
            "execution_mode",
            "test_case",
            "tool_expected",
            "scenario",
        )
        if agent_request and agent_request.metadata:
            for key in allowed_keys:
                value = agent_request.metadata.get(key)
                if value is not None:
                    metadata[key] = value

        return {k: v for k, v in metadata.items() if v is not None}

    async def on_agent_created(self):
        """Hook called when ADK agent is created."""
        try:
            # Initialize ADK context and memory adapter
            # TODO: Initialize actual ADK context integration
            # from ...infrastructure.adk.adk_memory_adapter import \
            #     AdkMemoryAdapter
            # from ...infrastructure.adk.adk_observer import AdkObserver

            # self.memory_adapter = AdkMemoryAdapter(self.agent.adk_client)
            # self.observer = AdkObserver(self.agent.adk_client)

            # Set up memory integration with ADK context.state
            await self._setup_memory_integration()

            # Set up observability integration
            await self._setup_observability_integration()

        except Exception:
            # Log error but don't fail agent creation
            pass

    async def before_execution(self, agent_request: AgentRequest):
        """Hook called before task execution."""
        try:
            execution_key = self._resolve_execution_key(agent_request)
            execution_id = (
                agent_request.metadata.get("execution_id")
                if getattr(agent_request, "metadata", None)
                else None
            )
            self._active_executions[execution_key] = {
                "start_time": datetime.now(),
                "task_id": getattr(
                    agent_request.task_request, "task_id", execution_key
                ),
                "execution_id": execution_id,
            }

            # Load session context from ADK memory
            await self._load_session_context(agent_request)

            # Record execution start in ADK observer
            await self._record_execution_start(agent_request)

            # Apply ADK-specific preprocessing
            await self._preprocess_request(agent_request)

        except Exception:
            # Log error but continue execution
            pass

    async def after_execution(self, agent_request: AgentRequest, result: TaskResult):
        """Hook called after task execution."""
        try:
            self._attach_execution_stats(agent_request, result)

            # Save session state to ADK memory
            await self._save_session_context(agent_request, result)

            # Record execution completion in ADK observer
            await self._record_execution_completion(agent_request, result)

            # Update conversation history
            await self._update_conversation_history(agent_request, result)

        except Exception:
            # Log error but don't fail the execution
            pass

    async def on_error(self, agent_request: AgentRequest, error: Exception):
        """Hook called when execution error occurs."""
        try:
            # Record error in ADK observer
            await self._record_execution_error(agent_request, error)

            # Save error context for debugging
            await self._save_error_context(agent_request, error)

        except Exception:
            # Suppress hook errors to avoid masking original error
            pass

    async def on_agent_destroyed(self):
        """Hook called when agent is destroyed."""
        try:
            # Cleanup memory adapter
            if self.memory_adapter:
                await self.memory_adapter.cleanup()

            # Cleanup observer
            if self.observer:
                await self.observer.cleanup()

        except Exception:
            # Suppress cleanup errors
            pass

    async def _setup_memory_integration(self):
        """Set up ADK memory integration through context.state."""
        # TODO: Initialize ADK context.state integration
        # This will integrate with ADK's native memory management
        pass

    async def _setup_observability_integration(self):
        """Set up ADK observability integration."""
        # TODO: Initialize ADK monitoring and tracing
        # This will integrate with ADK's native observability features
        pass

    async def _load_session_context(self, agent_request: AgentRequest):
        """Load session context from ADK memory."""
        if not agent_request.task_request.session_context:
            return

        session_id = agent_request.task_request.session_context.get_adk_session_id()
        if session_id and self.memory_adapter:
            # TODO: Load from ADK context.state
            # session_data = await self.memory_adapter.load_session(session_id)
            # agent_request.task_request.session_context.session_state.update(session_data)
            pass

    async def _save_session_context(
        self, agent_request: AgentRequest, result: TaskResult
    ):
        """Save session context to ADK memory."""
        if not agent_request.task_request.session_context:
            return

        session_id = agent_request.task_request.session_context.get_adk_session_id()
        if session_id and self.memory_adapter:
            # TODO: Save to ADK context.state
            # session_data = agent_request.task_request.session_context.session_state
            # await self.memory_adapter.save_session(session_id, session_data)
            pass

    async def _record_execution_start(self, agent_request: AgentRequest):
        """Record execution start in ADK observer."""
        if self.observer:
            metadata = self._build_observer_metadata(agent_request)
            task_id = metadata.get("task_id") or self._resolve_execution_key(
                agent_request
            )
            agent_id = metadata.get(
                "agent_id", getattr(self.agent, "agent_id", "adk-agent")
            )
            await self.observer.record_execution_start(
                task_id=task_id,
                agent_id=agent_id,
                metadata=metadata,
            )

    async def _record_execution_completion(
        self, agent_request: AgentRequest, result: TaskResult
    ):
        """Record execution completion in ADK observer."""
        if self.observer:
            metadata = self._build_observer_metadata(agent_request)
            if result.metadata:
                metadata.update(result.metadata)

            if result.execution_time is not None:
                metadata.setdefault("execution_time", result.execution_time)
            if getattr(result, "status", None):
                metadata.setdefault("status", result.status.value)

            task = agent_request.task_request
            task_id = task.task_id if task else result.task_id
            await self.observer.record_execution_completion(
                task_id=task_id,
                result=result,
                execution_time=result.execution_time,
                metadata=metadata,
            )

    async def _record_execution_error(
        self, agent_request: AgentRequest, error: Exception
    ):
        """Record execution error in ADK observer."""
        if self.observer:
            metadata = self._build_observer_metadata(agent_request)
            execution_key = self._resolve_execution_key(agent_request)
            execution_info = self._active_executions.pop(execution_key, {})
            start_time = execution_info.get("start_time")
            stats = self._compute_execution_stats(
                start_time=start_time, status=TaskStatus.ERROR.value
            )
            if stats:
                metadata.setdefault("execution_stats", {}).update(stats)
            metadata.setdefault("error_type", type(error).__name__)
            metadata.setdefault("error_message", str(error))
            task = agent_request.task_request if agent_request else None
            task_id = task.task_id if task else "unknown"
            agent_id = metadata.get(
                "agent_id", getattr(self.agent, "agent_id", "adk-agent")
            )
            await self.observer.record_execution_error(
                task_id=task_id,
                error=error,
                agent_id=agent_id,
                metadata=metadata,
            )

    async def _preprocess_request(self, agent_request: AgentRequest):
        """Apply ADK-specific request preprocessing."""
        # Convert user context to ADK format
        if agent_request.task_request.user_context:
            user_id = agent_request.task_request.user_context.get_adk_user_id()
            agent_request.metadata["adk_user_id"] = user_id

    async def _update_conversation_history(
        self, agent_request: AgentRequest, result: TaskResult
    ):
        """Update conversation history in ADK memory."""
        if self.memory_adapter and result.messages:
            # TODO: Update conversation history in ADK memory
            # await self.memory_adapter.append_messages(
            #     session_id=agent_request.task_request.session_context.get_adk_session_id(),
            #     messages=result.messages
            # )
            pass

    async def _save_error_context(self, agent_request: AgentRequest, error: Exception):
        """Save error context for debugging."""
        if self.memory_adapter:
            # TODO: Save error context to ADK memory
            # error_context = {
            #     "error_type": type(error).__name__,
            #     "error_message": str(error),
            #     "task_id": agent_request.task_request.task_id,
            #     "agent_id": self.agent.agent_id
            # }
            # await self.memory_adapter.save_error_context(error_context)
            pass

    def _resolve_execution_key(self, agent_request: AgentRequest) -> str:
        """Return execution key for tracking start/stop information."""
        task = getattr(agent_request, "task_request", None) if agent_request else None
        task_id = getattr(task, "task_id", None)
        execution_id: Optional[str] = None
        if agent_request and getattr(agent_request, "metadata", None):
            execution_id = agent_request.metadata.get("execution_id")

        return execution_id or task_id or f"adk-execution-{id(agent_request)}"

    def _attach_execution_stats(
        self, agent_request: AgentRequest, result: TaskResult
    ) -> None:
        """Populate execution statistics on TaskResult metadata."""
        execution_key = self._resolve_execution_key(agent_request)
        execution_info = self._active_executions.pop(execution_key, {})
        start_time = execution_info.get("start_time")

        if result.execution_time is None and start_time:
            result.execution_time = (datetime.now() - start_time).total_seconds()

        stats = self._compute_execution_stats(
            start_time=start_time,
            duration_seconds=result.execution_time,
            status=result.status.value if getattr(result, "status", None) else None,
        )
        if stats:
            result.metadata.setdefault("execution_stats", {}).update(stats)
            if "execution_id" in execution_info:
                result.metadata.setdefault("execution_id", execution_info["execution_id"])

    @staticmethod
    def _compute_execution_stats(
        start_time: Optional[datetime],
        duration_seconds: Optional[float] = None,
        status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Compute execution statistics for observability logging."""
        if not start_time and duration_seconds is None and status is None:
            return None

        finished_at = datetime.now()
        stats: Dict[str, Any] = {"finished_at": finished_at.isoformat()}
        if status:
            stats["status"] = status

        if start_time:
            stats["started_at"] = start_time.isoformat()
            if duration_seconds is None:
                duration_seconds = (finished_at - start_time).total_seconds()

        if duration_seconds is not None:
            stats["duration_seconds"] = duration_seconds
            stats["duration_ms"] = int(duration_seconds * 1000)

        return stats
