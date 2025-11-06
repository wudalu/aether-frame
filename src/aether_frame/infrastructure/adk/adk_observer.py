# -*- coding: utf-8 -*-
"""ADK Observer - Integration with ADK monitoring and observability."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...contracts import AgentRequest, TaskResult

logger = logging.getLogger("aether_frame.infrastructure.adk.observer")


class AdkObserver:
    """
    ADK Observer provides integration with ADK's native monitoring and observability
    features, enabling metrics collection, tracing, and performance monitoring.
    """

    def __init__(self, adk_client=None):
        """Initialize ADK observer."""
        self.adk_client = adk_client
        self._metrics: Dict[str, List[Dict[str, Any]]] = {}
        self._traces: List[Dict[str, Any]] = []
        self._performance_data: List[Dict[str, Any]] = []

    async def record_execution_start(
        self, task_id: str, agent_id: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record execution start event.

        Args:
            task_id: Task identifier
            agent_id: Agent identifier
            metadata: Additional metadata
        """
        try:
            metadata = metadata or {}

            event = {
                "event_type": "execution_start",
                "task_id": task_id,
                "agent_id": agent_id,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata,
            }

            # TODO: Integrate with ADK monitoring
            # await self.adk_client.monitoring.record_event(event)

            # For now, store locally
            if "execution_events" not in self._metrics:
                self._metrics["execution_events"] = []
            self._metrics["execution_events"].append(event)

            key_data = {"task_id": task_id, "agent_id": agent_id}
            key_data.update(metadata)

            logger.info(
                "ADK execution start",
                extra={
                    "execution_id": metadata.get("execution_id", task_id),
                    "flow_step": "ADK_START",
                    "component": "AdkObserver",
                    "key_data": key_data,
                },
            )

        except Exception as e:
            # Don't let monitoring failures break execution
            logger.debug("Failed to record execution start: %s", e, exc_info=True)

    async def record_execution_completion(
        self,
        task_id: str,
        result: TaskResult,
        execution_time: Optional[float],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Record execution completion event.

        Args:
            task_id: Task identifier
            result: Task execution result
            execution_time: Execution time in seconds
        """
        try:
            metadata = metadata or {}

            stats = metadata.get("execution_stats") if metadata else {}
            derived_execution_time = (
                execution_time
                if execution_time is not None
                else (stats.get("duration_seconds") if isinstance(stats, dict) else None)
            )

            event = {
                "event_type": "execution_completion",
                "task_id": task_id,
                "status": result.status.value,
                "execution_time": derived_execution_time,
                "timestamp": datetime.now().isoformat(),
                "result_metadata": metadata or result.metadata,
            }

            # TODO: Integrate with ADK monitoring
            # await self.adk_client.monitoring.record_completion(event)

            # Store performance data
            if derived_execution_time:
                performance_event = {
                    "task_id": task_id,
                    "execution_time": derived_execution_time,
                    "timestamp": datetime.now().isoformat(),
                    "status": result.status.value,
                }
                self._performance_data.append(performance_event)

            # Store locally
            if "execution_events" not in self._metrics:
                self._metrics["execution_events"] = []
            self._metrics["execution_events"].append(event)

            key_data = {
                "task_id": task_id,
                "agent_id": metadata.get("agent_id")
                if metadata.get("agent_id")
                else result.metadata.get("agent_id") if result.metadata else None,
                "status": result.status.value,
            }
            if derived_execution_time is not None:
                key_data["execution_time"] = derived_execution_time
            if result.error_message:
                key_data["error_message"] = result.error_message
            token_usage = metadata.get("token_usage") if metadata else None
            if not token_usage and result.metadata:
                token_usage = result.metadata.get("token_usage")
            if token_usage:
                key_data["token_usage"] = token_usage
            if stats:
                key_data["execution_stats"] = stats

            key_data.update(metadata)

            logger.info(
                "ADK execution complete",
                extra={
                    "execution_id": metadata.get("execution_id", task_id),
                    "flow_step": "ADK_COMPLETE",
                    "component": "AdkObserver",
                    "key_data": key_data,
                },
            )

        except Exception as e:
            # Don't let monitoring failures break execution
            logger.debug("Failed to record execution completion: %s", e, exc_info=True)

    async def record_execution_error(
        self,
        task_id: str,
        error: Exception,
        agent_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Record execution error event.

        Args:
            task_id: Task identifier
            error: Error that occurred
            agent_id: Agent identifier
        """
        try:
            metadata = metadata or {}
            metadata.setdefault("error_type", type(error).__name__)
            metadata.setdefault("error_message", str(error))
            metadata.setdefault("status", "error")

            event = {
                "event_type": "execution_error",
                "task_id": task_id,
                "agent_id": agent_id,
                "error_type": metadata.get("error_type"),
                "error_message": metadata.get("error_message"),
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata,
            }

            # TODO: Integrate with ADK error tracking
            # await self.adk_client.monitoring.record_error(event)

            # Store locally
            if "execution_errors" not in self._metrics:
                self._metrics["execution_errors"] = []
            self._metrics["execution_errors"].append(event)

            key_data = {"task_id": task_id, "agent_id": agent_id}
            key_data.update(metadata)

            logger.warning(
                "ADK execution error",
                extra={
                    "execution_id": metadata.get("execution_id", task_id),
                    "flow_step": "ADK_ERROR",
                    "component": "AdkObserver",
                    "key_data": key_data,
                },
            )

        except Exception as log_error:
            # Suppress errors in error tracking
            logger.debug("Failed to record execution error: %s", log_error, exc_info=True)

    async def start_trace(self, operation: str, metadata: Dict[str, Any]) -> str:
        """
        Start a new trace for an operation.

        Args:
            operation: Operation being traced
            metadata: Trace metadata

        Returns:
            str: Trace identifier
        """
        try:
            import uuid

            trace_id = str(uuid.uuid4())

            trace = {
                "trace_id": trace_id,
                "operation": operation,
                "start_time": datetime.now().isoformat(),
                "metadata": metadata,
                "spans": [],
            }

            # TODO: Integrate with ADK tracing
            # await self.adk_client.tracing.start_trace(trace_id, operation, metadata)

            # Store locally
            self._traces.append(trace)

            return trace_id

        except Exception:
            # Return dummy trace ID on error
            return "error-trace"

    async def end_trace(
        self, trace_id: str, status: str, result_metadata: Dict[str, Any]
    ):
        """
        End a trace.

        Args:
            trace_id: Trace identifier
            status: Trace completion status
            result_metadata: Result metadata
        """
        try:
            # Find and update trace
            for trace in self._traces:
                if trace["trace_id"] == trace_id:
                    trace["end_time"] = datetime.now().isoformat()
                    trace["status"] = status
                    trace["result_metadata"] = result_metadata
                    break

            # TODO: Integrate with ADK tracing
            # await self.adk_client.tracing.end_trace(trace_id, status, result_metadata)

        except Exception:
            # Suppress tracing errors
            pass

    async def add_span(
        self, trace_id: str, span_name: str, duration: float, metadata: Dict[str, Any]
    ):
        """
        Add a span to a trace.

        Args:
            trace_id: Trace identifier
            span_name: Name of the span
            duration: Span duration in seconds
            metadata: Span metadata
        """
        try:
            span = {
                "span_name": span_name,
                "duration": duration,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata,
            }

            # Find trace and add span
            for trace in self._traces:
                if trace["trace_id"] == trace_id:
                    trace["spans"].append(span)
                    break

            # TODO: Integrate with ADK tracing
            # await self.adk_client.tracing.add_span(trace_id, span)

        except Exception:
            # Suppress span errors
            pass

    async def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of collected metrics.

        Returns:
            Dict[str, Any]: Metrics summary
        """
        try:
            summary = {
                "total_executions": len(self._metrics.get("execution_events", [])),
                "total_errors": len(self._metrics.get("execution_errors", [])),
                "total_traces": len(self._traces),
                "timestamp": datetime.now().isoformat(),
            }

            # Calculate average execution time
            if self._performance_data:
                execution_times = [
                    d["execution_time"]
                    for d in self._performance_data
                    if d.get("execution_time")
                ]
                if execution_times:
                    summary["avg_execution_time"] = sum(execution_times) / len(
                        execution_times
                    )
                    summary["min_execution_time"] = min(execution_times)
                    summary["max_execution_time"] = max(execution_times)

            # Calculate success rate
            events = self._metrics.get("execution_events", [])
            completion_events = [
                e for e in events if e["event_type"] == "execution_completion"
            ]
            if completion_events:
                successful = len(
                    [e for e in completion_events if e.get("status") == "success"]
                )
                summary["success_rate"] = successful / len(completion_events)

            return summary

        except Exception:
            # Return minimal summary on error
            return {
                "total_executions": 0,
                "total_errors": 0,
                "total_traces": 0,
                "timestamp": datetime.now().isoformat(),
            }

    async def export_metrics(self, format_type: str = "json") -> Dict[str, Any]:
        """
        Export metrics in specified format.

        Args:
            format_type: Export format (json, prometheus)

        Returns:
            Dict[str, Any]: Exported metrics
        """
        try:
            if format_type == "json":
                return {
                    "metrics": self._metrics,
                    "traces": self._traces,
                    "performance_data": self._performance_data,
                    "summary": await self.get_metrics_summary(),
                }
            elif format_type == "prometheus":
                # TODO: Convert to Prometheus format
                return {"prometheus_format": "TODO: Implement Prometheus export"}
            else:
                return {"error": f"Unsupported format: {format_type}"}

        except Exception as e:
            return {"error": f"Export failed: {str(e)}"}

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of observer.

        Returns:
            Dict[str, Any]: Health status
        """
        return {
            "status": "healthy",
            "adk_client_connected": self.adk_client is not None,
            "metrics_count": sum(len(v) for v in self._metrics.values()),
            "traces_count": len(self._traces),
            "timestamp": datetime.now().isoformat(),
        }

    async def cleanup(self):
        """Cleanup observer resources."""
        self._metrics.clear()
        self._traces.clear()
        self._performance_data.clear()
