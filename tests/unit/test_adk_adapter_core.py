# -*- coding: utf-8 -*-
"""Focused tests for AdkFrameworkAdapter helper methods."""

import pytest

from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from aether_frame.contracts import AgentConfig


@pytest.fixture
def adapter():
    return AdkFrameworkAdapter()


def test_default_helpers_use_runner_settings(adapter):
    adapter.runner_manager.settings.default_user_id = "user-x"
    adapter.runner_manager.settings.default_agent_type = "agent-type"
    adapter.runner_manager.settings.default_adk_model = "model-x"
    adapter.runner_manager.settings.domain_agent_id_prefix = "prefix"

    assert adapter._get_default_user_id() == "user-x"
    assert adapter._get_default_agent_type() == "agent-type"
    assert adapter._get_default_adk_model() == "model-x"
    assert adapter._get_domain_agent_prefix() == "prefix"


@pytest.mark.asyncio
async def test_cleanup_chat_session_delegates(adapter, monkeypatch):
    called = []

    async def fake_cleanup(chat_session_id, runner_manager, agent_manager=None):
        called.append((chat_session_id, runner_manager))
        return True

    adapter.adk_session_manager.cleanup_chat_session = fake_cleanup  # type: ignore
    result = await adapter.cleanup_chat_session("chat-123")
    assert result is True
    assert called[0][0] == "chat-123"


@pytest.mark.asyncio
async def test_handle_agent_cleanup_cleans_mappings(adapter, monkeypatch):
    agent_id = "agent-1"
    adapter._agent_runners[agent_id] = "runner-1"
    adapter._agent_sessions[agent_id] = ["adk-1"]
    adapter._config_agents["hash-1"] = [agent_id]
    adapter.agent_manager._agent_configs[agent_id] = AgentConfig(agent_type="support", system_prompt="hi")

    cleaned = []

    async def fake_cleanup(agent_id_in):
        cleaned.append(agent_id_in)

    adapter.agent_manager.cleanup_agent = fake_cleanup  # type: ignore
    await adapter._handle_agent_cleanup(agent_id)

    assert agent_id not in adapter._agent_runners
    assert agent_id not in adapter._agent_sessions
    assert "hash-1" not in adapter._config_agents
    assert cleaned == [agent_id]
