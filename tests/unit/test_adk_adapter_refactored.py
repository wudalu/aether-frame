# -*- coding: utf-8 -*-
"""Updated tests aligned with the current AdkFrameworkAdapter implementation."""

import pytest

from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from aether_frame.contracts import AgentConfig, FrameworkType


@pytest.fixture
def adk_adapter():
    return AdkFrameworkAdapter()


def test_initial_state(adk_adapter):
    assert adk_adapter.framework_type == FrameworkType.ADK
    assert adk_adapter._initialized is False
    assert adk_adapter._agent_runners == {}
    assert adk_adapter._agent_sessions == {}
    assert adk_adapter._config_agents == {}


@pytest.mark.asyncio
async def test_is_ready_and_health_check(adk_adapter):
    # Before initialization the adapter is not ready
    assert adk_adapter.is_ready() is False
    health = await adk_adapter.health_check()
    assert health["status"] == "not_initialized"

    # Simulate initialized adapter with one active runner
    adk_adapter._initialized = True
    adk_adapter.runner_manager.runners["runner-1"] = {"sessions": {}}
    health = await adk_adapter.health_check()
    assert health["status"] == "healthy"
    assert health["active_sessions"] == 1
    assert "conversational_agents" in health["capabilities"]
    assert adk_adapter.is_ready() is True


@pytest.mark.asyncio
async def test_handle_agent_cleanup_clears_mappings(monkeypatch, adk_adapter):
    agent_id = "agent-123"
    adk_adapter._agent_runners[agent_id] = "runner-1"
    adk_adapter._agent_sessions[agent_id] = ["session-1", "session-2"]
    adk_adapter._config_agents["hash-1"] = [agent_id]
    adk_adapter.agent_manager._agent_configs[agent_id] = AgentConfig(
        agent_type="support", system_prompt="help"
    )

    cleaned_agents = []

    async def fake_cleanup(agent_id_in):
        cleaned_agents.append(agent_id_in)

    monkeypatch.setattr(adk_adapter.agent_manager, "cleanup_agent", fake_cleanup)

    await adk_adapter._handle_agent_cleanup(agent_id)

    assert agent_id not in adk_adapter._agent_runners
    assert agent_id not in adk_adapter._agent_sessions
    assert "hash-1" not in adk_adapter._config_agents
    assert cleaned_agents == [agent_id]


@pytest.mark.asyncio
async def test_cleanup_chat_session_handles_missing_id(adk_adapter):
    assert await adk_adapter.cleanup_chat_session("") is False


@pytest.mark.asyncio
async def test_get_capabilities(adk_adapter):
    capabilities = await adk_adapter.get_capabilities()
    assert "tool_integration" in capabilities
