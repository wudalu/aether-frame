# -*- coding: utf-8 -*-
"""Focused tests for AdkFrameworkAdapter helper and execution paths."""

from types import SimpleNamespace

import pytest

from aether_frame.contracts import AgentConfig, TaskRequest, TaskStatus, TaskResult, ErrorCode
from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter


@pytest.fixture
def adapter(monkeypatch):
    adapter = AdkFrameworkAdapter()
    adapter.agent_manager._agents = {}
    adapter.agent_manager._agent_metadata = {}
    adapter.agent_manager._agent_configs = {}
    return adapter


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


@pytest.mark.asyncio
async def test_execute_task_agent_creation_with_messages(adapter):
    task_request = TaskRequest(
        task_id="t1",
        task_type="chat",
        description="desc",
        agent_config=AgentConfig(agent_type="support", system_prompt="hi"),
        messages=[SimpleNamespace(role="user", content="hello")],
    )
    result = await adapter.execute_task(task_request, strategy=SimpleNamespace())
    assert result.status == TaskStatus.ERROR
    assert result.metadata["request_mode"] == "agent_creation_with_messages"


@pytest.mark.asyncio
async def test_execute_task_invalid_request_path(adapter):
    task_request = TaskRequest(task_id="t2", task_type="chat", description="desc")
    result = await adapter.execute_task(task_request, strategy=SimpleNamespace())
    assert result.status == TaskStatus.ERROR
    assert result.metadata["request_mode"] == "unknown"


@pytest.mark.asyncio
async def test_execute_task_handles_execution_error(adapter, monkeypatch):
    task_request = TaskRequest(
        task_id="t3",
        task_type="chat",
        description="desc",
        agent_id="agent-x",
        session_id="chat-1",
    )

    async def failing_conversation(*args, **kwargs):
        raise adapter.ExecutionError("boom", task_request)

    monkeypatch.setattr(adapter, "_handle_conversation", failing_conversation)
    result = await adapter.execute_task(task_request, strategy=SimpleNamespace())
    assert result.status == TaskStatus.ERROR
    assert result.metadata["error_stage"] == "adk_adapter.execute_task"
    assert result.metadata["request_mode"] == "conversation_existing_session"


class FakeAgent:
    def __init__(self):
        self.initialized = True
        self.runtime_context = {}

    async def initialize(self):
        return None


@pytest.mark.asyncio
async def test_build_runtime_context_for_new_agent(adapter, monkeypatch):
    task_request = TaskRequest(
        task_id="t4",
        task_type="chat",
        description="desc",
        agent_config=AgentConfig(agent_type="support", system_prompt="hi"),
    )
    agent = FakeAgent()

    async def fake_create_domain_agent(*args, **kwargs):
        agent.adk_agent = SimpleNamespace()
        return agent

    async def fake_get_runner(*args, **kwargs):
        adapter.runner_manager.runners["runner-1"] = {
            "sessions": {},
            "session_user_ids": {},
            "config_hash": "hash",
            "created_at": SimpleNamespace(),
            "last_activity": SimpleNamespace(),
        }
        return "runner-1", "session-1"

    monkeypatch.setattr(adapter, "_create_domain_agent_for_config", fake_create_domain_agent)
    monkeypatch.setattr(adapter.runner_manager, "get_or_create_runner", fake_get_runner)
    monkeypatch.setattr(adapter.agent_manager, "generate_agent_id", lambda: "agent-generated")

    runtime_context = await adapter._create_runtime_context_for_new_agent(task_request)
    assert runtime_context.agent_id == "agent-generated"
    assert adapter._agent_runners["agent-generated"] == "runner-1"


@pytest.mark.asyncio
async def test_handle_conversation_success_flow(adapter, monkeypatch):
    agent_id = "agent-chat"
    adapter.agent_manager._agents[agent_id] = SimpleNamespace()
    adapter.agent_manager._agent_metadata[agent_id] = {"last_activity": None}
    adapter._agent_runners[agent_id] = "runner-chat"
    adapter.runner_manager.runners["runner-chat"] = {
        "sessions": {"adk-new": SimpleNamespace()},
        "session_user_ids": {"adk-new": "user"},
    }
    task_request = TaskRequest(
        task_id="t5",
        task_type="chat",
        description="desc",
        agent_id=agent_id,
        session_id="chat-session",
        user_context=SimpleNamespace(get_adk_user_id=lambda: "user"),
    )

    async def fake_coordinate(**kwargs):
        return SimpleNamespace(adk_session_id="adk-new", switch_occurred=False)

    async def fake_runtime_context(*args, **kwargs):
        context = SimpleNamespace(
            session_id="adk-new",
            agent_id=agent_id,
            runner_id="runner-chat",
            execution_id="exec-123",
            metadata={"domain_agent": SimpleNamespace(), "pattern": "existing"},
        )

        def update_activity():
            context.metadata["updated"] = True

        context.update_activity = update_activity
        return context

    async def fake_execute(task_request_inner, runtime_context, domain_agent):
        return TaskResult(
            task_id=task_request_inner.task_id,
            status=TaskStatus.SUCCESS,
            agent_id=runtime_context.agent_id,
            session_id=runtime_context.session_id,
        )

    monkeypatch.setattr(adapter.adk_session_manager, "coordinate_chat_session", fake_coordinate)
    monkeypatch.setattr(adapter, "_create_runtime_context_for_existing_session", fake_runtime_context)
    monkeypatch.setattr(adapter, "_execute_with_domain_agent", fake_execute)

    result = await adapter._handle_conversation(task_request, strategy=SimpleNamespace())
    assert result.status == TaskStatus.SUCCESS
    assert result.session_id == "chat-session"
    assert result.metadata["adk_session_id"] == "adk-new"
