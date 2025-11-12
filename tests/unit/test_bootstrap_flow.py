# -*- coding: utf-8 -*-
"""Unit tests for bootstrap initialization and teardown flow."""

import asyncio

import pytest

from aether_frame import bootstrap
from aether_frame.contracts import FrameworkType
from aether_frame.config.settings import Settings


class FakeToolService:
    def __init__(self):
        self.initialized_with = None
        self.shutdown_called = False

    async def initialize(self, config):
        self.initialized_with = config

    async def health_check(self):
        return {"status": "healthy", "tools": 2}

    async def shutdown(self):
        self.shutdown_called = True


class FakeAdapter:
    def __init__(self):
        self.initialized = False

    async def initialize(self, config=None, tool_service=None, settings=None):
        self.initialized = tool_service is not None


class FakeFrameworkRegistry:
    def __init__(self):
        self.adapter = FakeAdapter()
        self.shutdown_called = False

    async def get_adapter(self, framework_type):
        return self.adapter

    async def get_available_frameworks(self):
        return [FrameworkType.ADK]

    async def shutdown_all_adapters(self):
        self.shutdown_called = True


class FakeAgentManager:
    def __init__(self):
        self.destroyed_agents = []

    async def list_agents(self):
        return ["agent-1"]

    async def destroy_agent(self, agent_id):
        self.destroyed_agents.append(agent_id)


class FakeExecutionEngine:
    def __init__(self, registry, settings):
        self.registry = registry
        self.settings = settings


class FakeTaskFactory:
    def __init__(self, tool_service):
        self.tool_service = tool_service


@pytest.mark.asyncio
async def test_initialize_health_and_shutdown_flow(monkeypatch):
    fake_registry = FakeFrameworkRegistry()
    fake_tool_service = FakeToolService()

    monkeypatch.setattr(bootstrap, "FrameworkRegistry", lambda: fake_registry)
    monkeypatch.setattr(bootstrap, "ToolService", lambda: fake_tool_service)
    monkeypatch.setattr(bootstrap, "AgentManager", FakeAgentManager)
    monkeypatch.setattr(bootstrap, "ExecutionEngine", FakeExecutionEngine)
    monkeypatch.setattr(bootstrap, "TaskRequestFactory", FakeTaskFactory)

    settings = Settings(enable_tool_service=True)

    components = await bootstrap.initialize_system(settings)

    assert isinstance(components.framework_registry, FakeFrameworkRegistry)
    assert isinstance(components.agent_manager, FakeAgentManager)
    assert isinstance(components.execution_engine, FakeExecutionEngine)
    assert isinstance(components.tool_service, FakeToolService)
    assert components.task_factory is not None
    assert fake_tool_service.initialized_with["enable_builtin"] is True
    assert fake_registry.adapter.initialized is True

    health = await bootstrap.health_check_system(components)
    assert health["overall_status"] == "healthy"
    assert "framework_registry" in health["components"]

    await bootstrap.shutdown_system(components)
    assert fake_tool_service.shutdown_called is True
    assert fake_registry.shutdown_called is True
    assert components.agent_manager.destroyed_agents == ["agent-1"]
