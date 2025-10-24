# -*- coding: utf-8 -*-
"""Tests for ADK domain agent tool request preparation."""

from unittest.mock import AsyncMock

from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
from aether_frame.contracts import (
    TaskRequest,
    UniversalTool,
    UserContext,
    SessionContext,
    ExecutionContext,
)
from aether_frame.contracts.enums import FrameworkType


def test_prepare_tool_request_includes_context_and_metadata():
    """Ensure ToolRequest carries TaskRequest context and tool metadata."""
    runtime_context = {
        "session_id": "runtime-session",
        "tool_service": AsyncMock(),
    }
    agent = AdkDomainAgent(agent_id="agent-1", config={}, runtime_context=runtime_context)

    task_request = TaskRequest(
        task_id="task-1",
        task_type="conversation",
        description="desc",
        user_context=UserContext(
            user_id="user-123",
            user_name="alice",
            session_token="token-xyz",
        ),
        session_context=SessionContext(session_id="session-abc"),
        execution_context=ExecutionContext(
            execution_id="exec-1",
            framework_type=FrameworkType.ADK,
        ),
        metadata={"mcp_headers": {"Authorization": "Bearer base-token"}},
    )
    agent._active_task_request = task_request  # simulate active task

    tool_metadata = {
        "mcp_headers": {"Authorization": "Bearer tool-token"},
        "custom": "value",
    }
    universal_tool = UniversalTool(
        name="test_server.search",
        description="Search tool",
        namespace="test_server",
        metadata=tool_metadata,
    )

    tool_request = agent._prepare_tool_request(universal_tool, {"query": "example"})

    assert tool_request.tool_name == "search"
    assert tool_request.tool_namespace == "test_server"
    assert tool_request.parameters == {"query": "example"}
    assert tool_request.session_id == "runtime-session"
    assert tool_request.user_context is task_request.user_context
    assert tool_request.session_context is task_request.session_context
    assert tool_request.execution_context is task_request.execution_context

    # Metadata should combine task and tool info (tool headers override task headers)
    assert tool_request.metadata["mcp_headers"] == {"Authorization": "Bearer tool-token"}
    assert tool_request.metadata["tool_metadata"]["custom"] == "value"

    # Ensure originals were not mutated
    assert task_request.metadata == {"mcp_headers": {"Authorization": "Bearer base-token"}}
    assert universal_tool.metadata == tool_metadata
