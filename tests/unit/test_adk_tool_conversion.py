# -*- coding: utf-8 -*-
"""Unit tests for ADK tool conversion helpers."""

from types import ModuleType, SimpleNamespace
import sys

import pytest

from aether_frame.agents.adk import tool_conversion as tool_conversion
from aether_frame.contracts import ToolRequest
from aether_frame.contracts.enums import ToolStatus


def _install_fake_google_modules(monkeypatch, *, include_agents=False):
    """Install fake google.adk.* modules needed for conversion helpers."""
    google_module = ModuleType("google")
    adk_module = ModuleType("google.adk")
    tools_module = ModuleType("google.adk.tools")

    class FakeFunctionTool:
        def __init__(self, func):
            self.func = func

    tools_module.FunctionTool = FakeFunctionTool
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.adk", adk_module)
    monkeypatch.setitem(sys.modules, "google.adk.tools", tools_module)
    google_module.adk = adk_module
    adk_module.tools = tools_module

    if include_agents:
        agents_module = ModuleType("google.adk.agents")

        class FakeAgent:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        agents_module.Agent = FakeAgent
        monkeypatch.setitem(sys.modules, "google.adk.agents", agents_module)
        adk_module.agents = agents_module
    return google_module


def test_create_function_tools_returns_empty_without_tool_service():
    assert tool_conversion.create_function_tools(None, []) == []


@pytest.mark.asyncio
async def test_create_function_tools_executes_tool_and_handles_approval(monkeypatch):
    _install_fake_google_modules(monkeypatch)

    calls = {"approval": 0, "executed": 0}

    class FakeToolService:
        async def execute_tool(self, request: ToolRequest):
            calls["executed"] += 1
            assert request.parameters == {"value": 42}
            return SimpleNamespace(
                status=ToolStatus.SUCCESS,
                result_data={"ok": True},
                execution_time=0.12,
                error_message=None,
            )

    async def approval_callback(tool, params):
        calls["approval"] += 1
        return {"approved": True, "reason": "auto"}

    def request_factory(tool, params):
        return ToolRequest(tool_name=tool.name, tool_namespace=tool.namespace, parameters=params)

    universal_tool = SimpleNamespace(
        name="builtin.echo",
        namespace="builtin",
        description="Echo tool",
        parameters_schema={"type": "object", "properties": {"value": {"type": "integer"}}},
        metadata={"requires_approval": True},
    )

    tool_service = FakeToolService()
    function_tools = tool_conversion.create_function_tools(
        tool_service,
        [universal_tool],
        request_factory=request_factory,
        approval_callback=approval_callback,
    )

    assert len(function_tools) == 1
    result = await function_tools[0].func(value=42)  # type: ignore[attr-defined]
    assert result["status"] == "success"
    assert calls["approval"] == 1
    assert calls["executed"] == 1


@pytest.mark.asyncio
async def test_create_function_tools_returns_error_payload_on_failure(monkeypatch):
    _install_fake_google_modules(monkeypatch)

    class FailingToolService:
        async def execute_tool(self, request):
            return SimpleNamespace(
                status=ToolStatus.ERROR,
                error_message="boom",
                error=None,
            )

    universal_tool = SimpleNamespace(
        name="namespace.fail_tool",
        namespace="namespace",
        description="Failing tool",
        parameters_schema={},
        metadata={"requires_approval": False},
    )

    function_tools = tool_conversion.create_function_tools(
        FailingToolService(),
        [universal_tool],
    )

    payload = await function_tools[0].func(answer="no")  # type: ignore[attr-defined]
    assert payload["status"] == "error"
    assert "boom" in payload["error"]


def test_build_adk_agent_returns_none_when_dependencies_missing(monkeypatch):
    # Ensure google modules are absent
    monkeypatch.setitem(sys.modules, "google", ModuleType("google"))
    for key in ["google.adk", "google.adk.tools", "google.adk.agents"]:
        monkeypatch.delitem(sys.modules, key, raising=False)
    assert tool_conversion.build_adk_agent(
        name="agent",
        description="desc",
        instruction="instr",
        model_identifier="model-x",
    ) is None


@pytest.mark.asyncio
async def test_build_adk_agent_constructs_agent_with_tools(monkeypatch):
    _install_fake_google_modules(monkeypatch, include_agents=True)

    from aether_frame.framework.adk import model_factory

    async def fake_execute_tool(request):
        return SimpleNamespace(status=ToolStatus.SUCCESS, result_data={}, execution_time=None, error_message=None)

    monkeypatch.setattr(
        model_factory.AdkModelFactory,
        "create_model",
        classmethod(lambda cls, *args, **kwargs: "stub-model"),
    )

    universal_tool = SimpleNamespace(
        name="builtin.echo",
        namespace="builtin",
        description="Echo",
        parameters_schema={},
        metadata={},
    )

    agent = tool_conversion.build_adk_agent(
        name="agent",
        description="desc",
        instruction="instr",
        model_identifier="model-x",
        tool_service=SimpleNamespace(execute_tool=fake_execute_tool),
        universal_tools=[universal_tool],
        framework_config={"planner": "built_in"},
    )

    assert agent is not None
    assert agent.kwargs["model"] == "stub-model"
    assert len(agent.kwargs["tools"]) == 1
