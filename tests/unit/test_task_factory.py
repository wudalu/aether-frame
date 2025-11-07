# -*- coding: utf-8 -*-
"""Unit tests for TaskRequestBuilder and TaskRequestFactory."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from aether_frame.contracts import FrameworkType, UserContext
from aether_frame.execution.task_factory import TaskRequestBuilder, TaskRequestFactory
from aether_frame.tools.resolver import ToolNotFoundError
from aether_frame.tools.service import ToolService
from tests.fixtures.factories import (
    make_universal_tool,
    make_message,
)


@pytest.mark.asyncio
async def test_builder_create_resolves_tools(monkeypatch):
    tool_service = MagicMock(spec=ToolService)
    builder = TaskRequestBuilder(tool_service)
    resolved_tool = make_universal_tool(name="builtin.echo")

    builder.tool_resolver.resolve_tools = AsyncMock(return_value=[resolved_tool])

    request = await builder.create(
        task_id="task-1",
        task_type="chat",
        description="collect info",
        tool_names=["echo"],
    )

    assert request.available_tools == [resolved_tool]
    builder.tool_resolver.resolve_tools.assert_awaited_once_with(["echo"], None)


@pytest.mark.asyncio
async def test_builder_create_propagates_tool_resolution_errors():
    tool_service = MagicMock(spec=ToolService)
    builder = TaskRequestBuilder(tool_service)
    builder.tool_resolver.resolve_tools = AsyncMock(side_effect=ToolNotFoundError("missing"))

    with pytest.raises(ToolNotFoundError):
        await builder.create(
            task_id="task-1",
            task_type="chat",
            description="collect info",
            tool_names=["missing"],
        )


@pytest.mark.asyncio
async def test_builder_create_with_manual_tools_passes_through():
    tool_service = MagicMock(spec=ToolService)
    builder = TaskRequestBuilder(tool_service)
    manual_tool = make_universal_tool(name="builtin.timestamp")

    request = await builder.create_with_manual_tools(
        task_id="manual-1",
        task_type="utility",
        description="use manual tool",
        available_tools=[manual_tool],
    )

    assert request.available_tools == [manual_tool]
    assert request.task_type == "utility"


@pytest.mark.asyncio
async def test_factory_create_tool_task_requires_tools():
    tool_service = MagicMock(spec=ToolService)
    factory = TaskRequestFactory(tool_service)

    with pytest.raises(ValueError):
        await factory.create_tool_task(
            task_id="tool-1",
            description="should fail",
            tools=[],
        )


@pytest.mark.asyncio
async def test_factory_create_tool_task_resolves_tools():
    tool_service = MagicMock(spec=ToolService)
    factory = TaskRequestFactory(tool_service)
    resolved_tool = make_universal_tool(name="builtin.logger")
    factory.builder.tool_resolver.resolve_tools = AsyncMock(return_value=[resolved_tool])

    request = await factory.create_tool_task(
        task_id="tool-2",
        description="execute tool",
        tools=["logger"],
    )

    assert request.task_type == "tool_execution"
    assert request.available_tools == [resolved_tool]


@pytest.mark.asyncio
async def test_factory_create_live_chat_task_builds_agent_and_context():
    tool_service = MagicMock(spec=ToolService)
    factory = TaskRequestFactory(tool_service)
    resolved_tool = make_universal_tool(name="builtin.echo")
    factory.builder.tool_resolver.resolve_tools = AsyncMock(return_value=[resolved_tool])

    user_context = UserContext(user_id="user-1")
    execution_messages = [make_message(role="user", content="ping")]

    request = await factory.create_live_chat_task(
        task_id="live-1",
        description="live support",
        user_context=user_context,
        messages=execution_messages,
        agent_type="helper",
        system_prompt="Be helpful.",
        tool_names=["echo"],
        framework_config={"planner": "simple"},
        execution_metadata={"origin": "test"},
    )

    assert request.agent_config is not None
    assert request.agent_config.agent_type == "helper"
    assert request.agent_config.available_tools == ["echo"]
    assert request.agent_config.framework_config["planner"] == "simple"

    assert request.execution_context is not None
    assert request.execution_context.execution_mode == "live"
    assert request.execution_context.metadata["stream_mode"] is True

    assert request.metadata["stream_mode"] is True
    assert request.metadata["phase"] == "live_execution"
    assert request.execution_context.framework_type == FrameworkType.ADK
