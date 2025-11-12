# -*- coding: utf-8 -*-
"""Unit tests for AgentManager lifecycle and health handling."""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from aether_frame.agents.manager import AgentManager
from aether_frame.agents.base.domain_agent import DomainAgent
from aether_frame.contracts import AgentConfig, FrameworkType, TaskResult, TaskStatus


class DummyAgent(DomainAgent):
    def __init__(self, agent_id: str = "agent", config=None):
        super().__init__(agent_id, config or {})
        self.cleaned = False
        self._state = {"calls": 0}
        self.healthy = True

    async def initialize(self):
        self._initialized = True

    async def execute(self, agent_request):
        self._state["calls"] += 1
        task_id = agent_request.task_request.task_id if agent_request.task_request else "task"
        return TaskResult(task_id=task_id, status=TaskStatus.SUCCESS)

    async def get_state(self):
        return dict(self._state)

    async def cleanup(self):
        self.cleaned = True

    async def execute_live(self, task_request):
        return (), SimpleNamespace()

    async def health_check(self):
        return self.healthy


@pytest.mark.asyncio
async def test_create_agent_stores_metadata_and_prevents_duplicates():
    manager = AgentManager()
    agent_config = AgentConfig(agent_type="support", system_prompt="hi")

    async def factory():
        agent = DummyAgent(agent_id="custom", config={"model": "x"})
        await agent.initialize()
        return agent

    agent_id = await manager.create_agent(factory, agent_config=agent_config, agent_id="agent-123")

    assert agent_id == "agent-123"
    assert manager.get_active_agent_ids() == ["agent-123"]

    with pytest.raises(ValueError):
        await manager.create_agent(factory, agent_config=agent_config, agent_id="agent-123")


@pytest.mark.asyncio
async def test_get_agent_updates_last_activity():
    manager = AgentManager()

    async def factory():
        return DummyAgent()

    agent_id = await manager.create_agent(factory)
    metadata_before = dict(manager._agent_metadata[agent_id])

    agent = await manager.get_agent(agent_id)

    assert isinstance(agent, DummyAgent)
    assert manager._agent_metadata[agent_id]["last_activity"] >= metadata_before["last_activity"]


@pytest.mark.asyncio
async def test_cleanup_agent_invokes_agent_cleanup_and_removes_state():
    manager = AgentManager()

    async def factory():
        agent = DummyAgent()
        await agent.initialize()
        return agent

    agent_id = await manager.create_agent(factory, agent_config=AgentConfig(agent_type="helper", system_prompt="x"))
    agent = await manager.get_agent(agent_id)

    cleaned = await manager.cleanup_agent(agent_id)

    assert cleaned is True
    assert agent.cleaned is True
    assert manager.get_active_agent_ids() == []
    assert agent_id not in manager._agent_configs


@pytest.mark.asyncio
async def test_cleanup_expired_agents_uses_idle_threshold(monkeypatch):
    manager = AgentManager()

    async def factory():
        return DummyAgent()

    agent_id = await manager.create_agent(factory)
    manager._agent_metadata[agent_id]["last_activity"] = datetime.now() - timedelta(hours=2)

    cleaned = await manager.cleanup_expired_agents(max_idle_time=timedelta(minutes=30))

    assert cleaned == [agent_id]
    assert manager.get_active_agent_ids() == []


@pytest.mark.asyncio
async def test_get_agent_status_includes_health_check():
    manager = AgentManager()

    async def factory():
        agent = DummyAgent()
        agent.healthy = False
        return agent

    agent_id = await manager.create_agent(factory, agent_config=AgentConfig(agent_type="observer", system_prompt="y"))
    agent = await manager.get_agent(agent_id)
    agent.healthy = True

    status = await manager.get_agent_status(agent_id)

    assert status["agent_id"] == agent_id
    assert status["agent_type"] == "observer"
    assert status["is_healthy"] is True


@pytest.mark.asyncio
async def test_register_agent_factory_and_stats_tracking():
    manager = AgentManager()
    manager.register_agent_factory(FrameworkType.ADK, lambda: None)

    async def factory():
        return DummyAgent()

    await manager.create_agent(factory, agent_config=AgentConfig(agent_type="writer", system_prompt="hello"))

    stats = await manager.get_stats()
    assert stats["total_agents"] == 1
    assert stats["agent_types"]["writer"] == 1
    assert stats["registered_factories"] == 1
