# -*- coding: utf-8 -*-
"""Unit tests for ExecutionEngine orchestration paths."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from aether_frame.config.settings import Settings
from aether_frame.contracts import ExecutionContext, FrameworkType, TaskComplexity, TaskStatus
from aether_frame.execution.execution_engine import ExecutionEngine
from aether_frame.execution.task_router import ExecutionStrategy
from aether_frame.framework.framework_registry import FrameworkRegistry
from tests.fixtures.factories import make_task_request, make_task_result


def _make_strategy() -> ExecutionStrategy:
    return ExecutionStrategy(
        framework_type=FrameworkType.ADK,
        task_complexity=TaskComplexity.SIMPLE,
        execution_config={},
        runtime_options={},
        execution_mode="async",
        framework_score=1.0,
        fallback_frameworks=[],
    )


@pytest.mark.asyncio
async def test_execute_task_returns_validation_error_when_context_missing():
    framework_registry = MagicMock(spec=FrameworkRegistry)
    engine = ExecutionEngine(framework_registry, settings=Settings())
    engine.task_router = MagicMock()
    engine.task_router.route_task = AsyncMock()

    request = make_task_request(agent_id=None, session_id=None, agent_config=None)
    request.agent_config = None
    request.agent_id = None
    request.session_id = None

    result = await engine.execute_task(request)

    assert result.status == TaskStatus.ERROR
    assert result.metadata["error_stage"] == "execution_engine.validate_context"
    engine.task_router.route_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_task_returns_error_when_adapter_missing():
    framework_registry = MagicMock(spec=FrameworkRegistry)
    framework_registry.get_adapter = AsyncMock(return_value=None)

    engine = ExecutionEngine(framework_registry, settings=Settings())
    strategy = _make_strategy()
    engine.task_router = MagicMock()
    engine.task_router.route_task = AsyncMock(return_value=strategy)

    request = make_task_request(agent_id="agent-1")

    result = await engine.execute_task(request)

    assert result.status == TaskStatus.ERROR
    assert result.metadata["error_stage"] == "execution_engine.get_adapter"
    assert result.error.code == "framework.unavailable"
    framework_registry.get_adapter.assert_awaited_once_with(strategy.framework_type)


@pytest.mark.asyncio
async def test_execute_task_delegates_to_adapter():
    framework_registry = MagicMock(spec=FrameworkRegistry)
    adapter = MagicMock()
    adapter.execute_task = AsyncMock(return_value=make_task_result())
    framework_registry.get_adapter = AsyncMock(return_value=adapter)

    engine = ExecutionEngine(framework_registry, settings=Settings())
    strategy = _make_strategy()
    engine.task_router = MagicMock()
    engine.task_router.route_task = AsyncMock(return_value=strategy)

    request = make_task_request(agent_id="agent-1")

    result = await engine.execute_task(request)

    assert result.status == TaskStatus.SUCCESS
    adapter.execute_task.assert_awaited_once_with(request, strategy)
    framework_registry.get_adapter.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_task_wraps_adapter_exceptions():
    framework_registry = MagicMock(spec=FrameworkRegistry)
    adapter = MagicMock()
    adapter.execute_task = AsyncMock(side_effect=RuntimeError("adapter crash"))
    framework_registry.get_adapter = AsyncMock(return_value=adapter)

    engine = ExecutionEngine(framework_registry, settings=Settings())
    strategy = _make_strategy()
    engine.task_router = MagicMock()
    engine.task_router.route_task = AsyncMock(return_value=strategy)

    request = make_task_request(agent_id="agent-1")

    result = await engine.execute_task(request)

    assert result.status == TaskStatus.ERROR
    assert result.metadata["framework"] == strategy.framework_type.value
    assert "adapter crash" in result.error_message


@pytest.mark.asyncio
async def test_execute_task_live_requires_adapter_support():
    framework_registry = MagicMock(spec=FrameworkRegistry)
    adapter = MagicMock()
    adapter.supports_live_execution.return_value = False
    framework_registry.get_adapter = AsyncMock(return_value=adapter)

    engine = ExecutionEngine(framework_registry, settings=Settings())
    strategy = _make_strategy()
    engine.task_router = MagicMock()
    engine.task_router.route_task = AsyncMock(return_value=strategy)

    request = make_task_request(agent_id="agent-1")

    with pytest.raises(RuntimeError) as exc:
        await engine.execute_task_live(request, ExecutionContext(execution_id="exec", framework_type=FrameworkType.ADK))

    assert "doesn't support live execution" in str(exc.value)


@pytest.mark.asyncio
async def test_execute_task_live_returns_adapter_result():
    framework_registry = MagicMock(spec=FrameworkRegistry)
    adapter = MagicMock()
    live_result = ("stream", "communicator")
    adapter.supports_live_execution.return_value = True
    adapter.execute_task_live = AsyncMock(return_value=live_result)
    framework_registry.get_adapter = AsyncMock(return_value=adapter)

    engine = ExecutionEngine(framework_registry, settings=Settings())
    strategy = _make_strategy()
    engine.task_router = MagicMock()
    engine.task_router.route_task = AsyncMock(return_value=strategy)

    request = make_task_request(agent_id="agent-1")
    context = ExecutionContext(execution_id="exec", framework_type=FrameworkType.ADK)

    result = await engine.execute_task_live(request, context)

    assert result == live_result
    adapter.execute_task_live.assert_awaited_once_with(request, context)


@pytest.mark.asyncio
async def test_execute_task_live_session_wraps_stream_session(monkeypatch):
    framework_registry = MagicMock(spec=FrameworkRegistry)
    engine = ExecutionEngine(framework_registry, settings=Settings())
    live_result = ("stream", "communicator")
    engine.execute_task_live = AsyncMock(return_value=live_result)

    captured = {}

    def fake_create_stream_session(task_id, result):
        captured["args"] = (task_id, result)
        return "stream-session"

    monkeypatch.setattr(
        "aether_frame.execution.execution_engine.create_stream_session",
        fake_create_stream_session,
    )

    request = make_task_request(agent_id="agent-1")
    context = ExecutionContext(execution_id="exec", framework_type=FrameworkType.ADK)

    session = await engine.execute_task_live_session(request, context)

    assert session == "stream-session"
    assert captured["args"] == (request.task_id, live_result)
    engine.execute_task_live.assert_awaited_once_with(request, context)
