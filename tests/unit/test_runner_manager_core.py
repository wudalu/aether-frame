# -*- coding: utf-8 -*-
"""Tests for RunnerManager core lifecycle methods."""

from types import SimpleNamespace

import pytest

from aether_frame.framework.adk.runner_manager import RunnerManager
from aether_frame.contracts import AgentConfig, TaskRequest


class DummySessionService:
    def __init__(self):
        self.created = {}
        self.deleted = []

    async def create_session(self, app_name, user_id, session_id):
        session = SimpleNamespace(app_name=app_name, user_id=user_id, session_id=session_id)
        self.created[session_id] = session
        return session

    async def delete_session(self, app_name, user_id, session_id):
        self.deleted.append((session_id, app_name, user_id))


class DummyRunner:
    def __init__(self):
        self.shutdown_called = False

    async def shutdown(self):
        self.shutdown_called = True


@pytest.mark.asyncio
async def test_get_or_create_runner_creates_and_reuses(monkeypatch):
    manager = RunnerManager()
    agent_config = AgentConfig(agent_type="support", system_prompt="help")

    async def fake_create(agent_config, config_hash, adk_agent):
        manager.runners["runner-1"] = {
            "session_service": DummySessionService(),
            "sessions": {},
            "session_user_ids": {},
            "agent_config": agent_config,
            "config_hash": config_hash,
        }
        return "runner-1"

    async def fake_create_session(runner_id, task_request=None, external_session_id=None):
        manager.runners[runner_id]["sessions"][external_session_id] = SimpleNamespace()
        return external_session_id

    monkeypatch.setattr(manager, "_create_new_runner", fake_create)
    monkeypatch.setattr(manager, "_create_session_in_runner", fake_create_session)

    runner_id, session_id = await manager.get_or_create_runner(
        agent_config,
        task_request=TaskRequest(task_id="t1", task_type="chat", description="desc"),
        adk_agent=object(),
        engine_session_id="session-1",
    )
    assert runner_id == "runner-1"
    assert session_id == "session-1"
    assert manager.session_to_runner["session-1"] == "runner-1"

    # Reuse existing runner without creating session
    runner_id_2, session_id_2 = await manager.get_or_create_runner(
        agent_config,
        task_request=None,
        adk_agent=None,
        create_session=False,
    )
    assert runner_id_2 == "runner-1"
    assert session_id_2 is None


@pytest.mark.asyncio
async def test_remove_session_and_cleanup_runner(monkeypatch):
    manager = RunnerManager()
    session_service = DummySessionService()
    runner = DummyRunner()
    manager.runners["runner-1"] = {
        "session_service": session_service,
        "sessions": {"session-1": SimpleNamespace(app_name="app", user_id="user", session_id="session-1")},
        "session_user_ids": {"session-1": "user"},
        "config_hash": "hash-1",
        "runner": runner,
    }
    manager.session_to_runner["session-1"] = "runner-1"
    manager.config_to_runner["hash-1"] = "runner-1"

    removed = await manager.remove_session_from_runner("runner-1", "session-1")
    assert removed is True
    assert manager.session_to_runner == {}

    async def fake_agent_cleanup(agent_id):
        cleaned.append(agent_id)

    cleaned = []
    manager.agent_runner_mapping = {"agent-1": "runner-1"}
    manager.agent_cleanup_callback = fake_agent_cleanup

    result = await manager.cleanup_runner("runner-1")
    assert result is True
    assert manager.runners == {}
    assert cleaned == ["agent-1"]
