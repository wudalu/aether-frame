# -*- coding: utf-8 -*-
"""Unit tests for TaskRouter strategy selection."""

import pytest

from aether_frame.contracts import ExecutionMode, FrameworkType, TaskComplexity
from aether_frame.execution.task_router import ExecutionStrategy, TaskRouter
from tests.fixtures.factories import make_execution_config, make_task_request, make_universal_tool, make_message


@pytest.mark.asyncio
async def test_route_task_returns_adk_strategy_by_default():
    router = TaskRouter()
    request = make_task_request(
        available_tools=[make_universal_tool(name="builtin.echo")],
    )

    strategy = await router.route_task(request)

    assert isinstance(strategy, ExecutionStrategy)
    assert strategy.framework_type == FrameworkType.ADK
    assert strategy.execution_mode == "async"
    assert strategy.framework_score == 1.0
    assert strategy.runtime_options["task_type"] == request.task_type
    assert strategy.runtime_options["complexity_level"] == TaskComplexity.SIMPLE.value
    assert strategy.execution_config["available_tools"] == ["builtin.echo"]


def test_complexity_analysis_uses_message_and_tool_counts():
    router = TaskRouter()

    simple_request = make_task_request(messages=[make_message(content="m1")])
    assert router._analyze_task_complexity(simple_request) == TaskComplexity.SIMPLE

    moderate_request = make_task_request(
        messages=[make_message(content=f"m{i}") for i in range(4)],
        available_tools=[make_universal_tool(name="builtin.echo")] * 3,
    )
    assert router._analyze_task_complexity(moderate_request) == TaskComplexity.MODERATE

    complex_request = make_task_request(
        messages=[make_message(content=f"m{i}") for i in range(11)],
        available_tools=[make_universal_tool(name="builtin.echo")] * 6,
    )
    assert router._analyze_task_complexity(complex_request) == TaskComplexity.COMPLEX


def test_build_execution_config_merges_request_config():
    router = TaskRouter()
    execution_config = make_execution_config(
        execution_mode=ExecutionMode.STREAMING,
        max_retries=7,
        enable_logging=False,
        enable_monitoring=True,
    )
    request = make_task_request(execution_config=execution_config)

    config = router._build_execution_config(request)

    assert config["execution_mode"] == ExecutionMode.STREAMING.value
    assert config["max_retries"] == 7
    assert config["enable_logging"] is False
    assert config["enable_monitoring"] is True


def test_build_runtime_options_includes_complexity():
    router = TaskRouter()
    request = make_task_request(task_type="analysis")
    complexity = TaskComplexity.MODERATE

    runtime_options = router._build_runtime_options(request, complexity)

    assert runtime_options["execution_mode"] == ExecutionMode.ASYNC.value
    assert runtime_options["complexity_level"] == complexity.value
    assert runtime_options["task_type"] == "analysis"
