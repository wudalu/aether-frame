# -*- coding: utf-8 -*-
"""Unit tests for AIAssistant orchestration logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from aether_frame.contracts import ErrorCode, TaskStatus
from aether_frame.execution.ai_assistant import AIAssistant
from aether_frame.execution.execution_engine import ExecutionEngine
from aether_frame.config.settings import Settings
from tests.fixtures.factories import (
    make_execution_context,
    make_task_request,
    make_task_result,
)


@pytest.mark.asyncio
async def test_process_request_returns_validation_error_when_missing_fields():
    engine = MagicMock(spec=ExecutionEngine)
    engine.execute_task = AsyncMock()
    assistant = AIAssistant(execution_engine=engine, settings=Settings())

    invalid_request = make_task_request(task_id="", task_type="", description="")

    result = await assistant.process_request(invalid_request)

    assert result.status == TaskStatus.ERROR
    assert result.metadata["error_stage"] == "ai_assistant.validate_request"
    assert result.error.code == ErrorCode.REQUEST_VALIDATION.value
    engine.execute_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_request_delegates_to_execution_engine():
    engine = MagicMock(spec=ExecutionEngine)
    expected_result = make_task_result()
    engine.execute_task = AsyncMock(return_value=expected_result)
    assistant = AIAssistant(execution_engine=engine, settings=Settings())

    request = make_task_request()

    result = await assistant.process_request(request)

    assert result is expected_result
    engine.execute_task.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_process_request_wraps_engine_failure():
    engine = MagicMock(spec=ExecutionEngine)
    engine.execute_task = AsyncMock(side_effect=RuntimeError("boom"))
    assistant = AIAssistant(execution_engine=engine, settings=Settings())

    request = make_task_request()

    result = await assistant.process_request(request)

    assert result.status == TaskStatus.ERROR
    assert result.error is not None
    assert result.error.code == ErrorCode.INTERNAL_ERROR.value
    assert result.metadata["error_stage"] == "ai_assistant.process_request"
    engine.execute_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_live_session_validates_request():
    engine = MagicMock(spec=ExecutionEngine)
    engine.execute_task_live = AsyncMock()
    assistant = AIAssistant(execution_engine=engine, settings=Settings())

    invalid_request = make_task_request(task_id="", task_type="", description="")

    with pytest.raises(RuntimeError) as exc:
        await assistant.start_live_session(invalid_request)
    assert "Invalid task request" in str(exc.value)
    engine.execute_task_live.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_live_session_uses_existing_context():
    engine = MagicMock(spec=ExecutionEngine)
    live_result = ("stream", "communicator")
    engine.execute_task_live = AsyncMock(return_value=live_result)
    assistant = AIAssistant(execution_engine=engine, settings=Settings())

    context = make_execution_context(execution_mode="live")
    request = make_task_request(execution_context=context)

    result = await assistant.start_live_session(request)

    assert result == live_result
    engine.execute_task_live.assert_awaited_once_with(request, context)


@pytest.mark.asyncio
async def test_start_live_session_builds_context_when_missing():
    engine = MagicMock(spec=ExecutionEngine)
    live_result = ("stream", "communicator")
    engine.execute_task_live = AsyncMock(return_value=live_result)
    assistant = AIAssistant(execution_engine=engine, settings=Settings())

    request = make_task_request(task_id="task-99")

    result = await assistant.start_live_session(request)

    assert result == live_result
    args, _ = engine.execute_task_live.await_args
    built_context = args[1]
    assert built_context.execution_id == "live_task-99"
    assert built_context.framework_type.value == "adk"
    assert built_context.execution_mode == "live"


@pytest.mark.asyncio
async def test_health_check_returns_status_and_version():
    engine = MagicMock(spec=ExecutionEngine)
    assistant = AIAssistant(execution_engine=engine, settings=Settings(app_version="1.2.3"))

    result = await assistant.health_check()

    assert result["status"] == "healthy"
    assert result["version"] == "1.2.3"
