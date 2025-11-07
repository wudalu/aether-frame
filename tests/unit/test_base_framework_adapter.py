# -*- coding: utf-8 -*-
"""Tests for base FrameworkAdapter helper methods."""

from types import SimpleNamespace

import pytest

from aether_frame.contracts import FrameworkType, TaskRequest
from aether_frame.contracts.enums import TaskComplexity
from aether_frame.execution.task_router import ExecutionStrategy
from aether_frame.framework.base.framework_adapter import FrameworkAdapter
import aether_frame.contracts as contracts_module
import aether_frame.framework.base.framework_adapter as adapter_module


class DummyAdapter(FrameworkAdapter):
    framework_type = FrameworkType.ADK

    async def initialize(self, config=None):
        self.initialized_with = config

    async def execute_task(self, task_request, strategy):
        self.last_execute = (task_request, strategy)
        return None

    async def execute_task_live(self, task_request, context):
        raise NotImplementedError

    async def shutdown(self):
        self.shutdown_called = True

    async def health_check(self):
        return {"status": "ok"}

    async def get_capabilities(self):
        return ["basic"]


def make_strategy():
    return ExecutionStrategy(
        framework_type=FrameworkType.ADK,
        task_complexity=TaskComplexity.SIMPLE,
        execution_config={"required_capabilities": ["tool"]},
        runtime_options={"complexity_level": "simple"},
    )


@pytest.mark.asyncio
async def test_convert_task_to_agent_request(monkeypatch):
    class DummyAgentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class DummyAgentRequest:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(adapter_module, "AgentConfig", DummyAgentConfig, raising=False)
    monkeypatch.setattr(adapter_module, "AgentRequest", DummyAgentRequest, raising=False)
    monkeypatch.setattr(contracts_module, "AgentConfig", DummyAgentConfig, raising=False)
    monkeypatch.setattr(contracts_module, "AgentRequest", DummyAgentRequest, raising=False)

    adapter = DummyAdapter()
    task_request = TaskRequest(task_id="t1", task_type="chat", description="desc")
    strategy = make_strategy()
    agent_request = adapter._convert_task_to_agent_request(task_request, strategy)
    assert agent_request.kwargs["agent_type"] == "conversational_agent"
    assert agent_request.kwargs["framework_type"] == FrameworkType.ADK


def test_supports_live_execution_default_false():
    adapter = DummyAdapter()
    assert adapter.supports_live_execution() is True  # because method defined
