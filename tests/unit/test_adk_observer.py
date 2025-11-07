# -*- coding: utf-8 -*-
"""Unit tests for AdkObserver monitoring utilities."""

import pytest

from aether_frame.contracts import TaskResult, TaskStatus
from aether_frame.infrastructure.adk.adk_observer import AdkObserver


@pytest.mark.asyncio
async def test_record_execution_events_and_metrics_summary():
    observer = AdkObserver()
    await observer.record_execution_start("task-1", "agent-1", {"phase": "start"})

    result = TaskResult(task_id="task-1", status=TaskStatus.SUCCESS, metadata={"m": "v"})
    await observer.record_execution_completion("task-1", result, execution_time=1.2)

    await observer.record_execution_error("task-1", RuntimeError("boom"), "agent-1")

    summary = await observer.get_metrics_summary()
    assert summary["total_executions"] >= 1
    assert summary["total_errors"] >= 1
    assert summary["total_traces"] == 0


@pytest.mark.asyncio
async def test_tracing_and_spans_export_and_health():
    observer = AdkObserver(adk_client=object())
    trace_id = await observer.start_trace("operation", {"info": "test"})
    await observer.add_span(trace_id, "span-1", 0.5, {"detail": 1})
    await observer.end_trace(trace_id, "success", {"result": "ok"})

    export = await observer.export_metrics("json")
    assert "metrics" in export

    health = await observer.health_check()
    assert health["adk_client_connected"] is True

    await observer.cleanup()
    assert observer._metrics == {}
    assert observer._traces == []
