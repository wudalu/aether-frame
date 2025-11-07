# -*- coding: utf-8 -*-
"""Unit tests for AdkDomainAgent helper utilities."""

from types import SimpleNamespace

import pytest

from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
from aether_frame.contracts import (
    ExecutionContext,
    FrameworkType,
    SessionContext,
    TaskRequest,
    UserContext,
    UniversalTool,
)


@pytest.fixture
def domain_agent():
    context = {"tool_service": "tool-service"}
    config = {"agent_type": "chat", "model_config": {}}
    return AdkDomainAgent(agent_id="agent-1", config=config, runtime_context=context)


def test_get_model_configuration_honors_priority(domain_agent, monkeypatch):
    domain_agent.config["model"] = "explicit-model"
    assert domain_agent._get_model_configuration() == "explicit-model"

    domain_agent.config.pop("model")
    domain_agent.config["model_config"] = {"model": "model-config"}
    assert domain_agent._get_model_configuration() == "model-config"

    domain_agent.config["model_config"] = {}

    class SettingsStub:
        default_model = "settings-model"

    monkeypatch.setattr(
        "aether_frame.config.settings.Settings", lambda: SettingsStub()
    )
    assert domain_agent._get_model_configuration() == "settings-model"


def test_prepare_tool_request_merges_metadata(domain_agent):
    domain_agent.runtime_context["session_id"] = "runtime-session"
    task_request = TaskRequest(
        task_id="task-1",
        task_type="chat",
        description="desc",
        user_context=UserContext(user_id="alice"),
        session_context=SessionContext(session_id="request-session"),
        execution_context=ExecutionContext(
            execution_id="exec-1", framework_type=FrameworkType.ADK
        ),
        metadata={"mcp_headers": {"trace": "abc"}},
    )
    domain_agent._active_task_request = task_request

    tool = SimpleNamespace(
        name="demo.search", namespace="demo", metadata={"mcp_headers": {"token": "123"}}
    )
    request = domain_agent._prepare_tool_request(tool, {"query": "python"})

    assert request.tool_name == "search"
    assert request.session_id == "runtime-session"
    assert request.metadata["mcp_headers"]["trace"] == "abc"
    assert request.metadata["mcp_headers"]["token"] == "123"


@pytest.mark.asyncio
async def test_update_tools_with_existing_agent(monkeypatch, domain_agent):
    domain_agent.adk_agent = SimpleNamespace(tools=None)

    async def fake_convert(universal_tools):
        return ["converted"]

    monkeypatch.setattr(
        domain_agent, "_convert_universal_tools_to_adk", lambda tools: ["converted"]
    )
    universal_tool = UniversalTool(
        name="demo.lookup", description="lookup", namespace="demo"
    )
    await domain_agent.update_tools([universal_tool])
    assert domain_agent.adk_agent.tools == ["converted"]
    assert domain_agent._tools_initialized is True


@pytest.mark.asyncio
async def test_update_tools_without_existing_agent(monkeypatch, domain_agent):
    calls = []

    async def fake_create(available_tools=None):
        calls.append(available_tools)

    domain_agent.adk_agent = None
    monkeypatch.setattr(domain_agent, "_create_adk_agent", fake_create)

    universal_tool = UniversalTool(
        name="demo.lookup", description="lookup", namespace="demo"
    )
    await domain_agent.update_tools([universal_tool])
    assert calls and calls[0][0].name == "demo.lookup"


def test_convert_universal_tools_to_adk_sets_policy(monkeypatch, domain_agent):
    recorded_args = {}

    def fake_create(tool_service, tools, request_factory, approval_callback):
        recorded_args["tool_service"] = tool_service
        return ["wrapped"]

    monkeypatch.setattr(
        "aether_frame.agents.adk.adk_domain_agent.create_function_tools", fake_create
    )
    universal_tool = UniversalTool(
        name="demo.search",
        description="search",
        namespace="demo",
        metadata={"requires_approval": False},
    )
    domain_agent.runtime_context["approval_broker"] = SimpleNamespace()
    wrapped = domain_agent._convert_universal_tools_to_adk([universal_tool])
    assert wrapped == ["wrapped"]
    assert domain_agent._tool_approval_policy["demo.search"] is False


@pytest.mark.asyncio
async def test_await_tool_approval_uses_broker(domain_agent):
    class Broker:
        def __init__(self):
            self.calls = []

        async def wait_for_tool_approval(self, tool_name, params):
            self.calls.append((tool_name, params))
            return {"approved": True}

    broker = Broker()
    domain_agent.runtime_context["approval_broker"] = broker
    domain_agent._tool_approval_policy = {"demo.search": True}
    response = await domain_agent._await_tool_approval(
        SimpleNamespace(name="demo.search"), {"value": 1}
    )
    assert response["approved"] is True
    assert broker.calls == [("demo.search", {"value": 1})]

    domain_agent._tool_approval_policy["demo.search"] = False
    response = await domain_agent._await_tool_approval(
        SimpleNamespace(name="demo.search"), {}
    )
    assert response["approved"] is True
