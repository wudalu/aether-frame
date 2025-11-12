# -*- coding: utf-8 -*-
"""Tests for RunnerManager core lifecycle methods."""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from aether_frame.framework.adk.runner_manager import RunnerManager
from aether_frame.contracts import AgentConfig, TaskRequest, UserContext


class DummySessionService:
    def __init__(self):
        self.created = {}
        self.deleted = []
        self.shutdown_called = False

    async def create_session(self, app_name, user_id, session_id):
        session = SimpleNamespace(app_name=app_name, user_id=user_id, session_id=session_id)
        self.created[session_id] = session
        return session

    async def delete_session(self, app_name, user_id, session_id):
        self.deleted.append((session_id, app_name, user_id))

    async def shutdown(self):
        self.shutdown_called = True


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
def test_mark_runner_activity_and_get_runner_for_agent():
    manager = RunnerManager()
    manager.runners["runner-1"] = {"last_activity": None}
    manager.mark_runner_activity("runner-1")
    assert manager.runners["runner-1"]["last_activity"] is not None

    manager.agent_runner_mapping = {"agent-1": "runner-1"}
    manager.runners["runner-1"] = {}
    result = asyncio.get_event_loop().run_until_complete(manager.get_runner_for_agent("agent-1"))
    assert result == "runner-1"


@pytest.fixture
def stub_settings():
    return SimpleNamespace(
        default_app_name="stub-app",
        default_user_id="stub-user",
        session_id_prefix="sess",
        runner_id_prefix="runner",
    )


@pytest.mark.asyncio
async def test_create_session_in_runner_respects_external_id(stub_settings):
    manager = RunnerManager(settings=stub_settings)
    service = DummySessionService()
    runner_id = "runner-x"
    manager.runners[runner_id] = {"session_service": service, "sessions": {}, "session_user_ids": {}}

    task_request = TaskRequest(
        task_id="t2",
        task_type="chat",
        description="desc",
        user_context=UserContext(user_id="alice"),
    )

    session_id = await manager._create_session_in_runner(
        runner_id, task_request=task_request, external_session_id="engine-session"
    )
    assert session_id == "engine-session"
    assert "engine-session" in manager.session_to_runner
    assert service.created["engine-session"].user_id == "alice"
    assert manager.runners[runner_id]["session_user_ids"]["engine-session"] == "alice"


@pytest.mark.asyncio
async def test_create_session_in_runner_uses_defaults_when_missing_context(stub_settings):
    manager = RunnerManager(settings=stub_settings)
    service = DummySessionService()
    runner_id = "runner-y"
    manager.runners[runner_id] = {"session_service": service, "sessions": {}, "session_user_ids": {}}

    session_id = await manager._create_session_in_runner(runner_id)
    assert session_id.startswith(stub_settings.session_id_prefix)
    assert service.created[session_id].user_id == stub_settings.default_user_id
    assert manager.session_to_runner[session_id] == runner_id


@pytest.mark.asyncio
async def test_get_runner_by_session_returns_context(stub_settings):
    manager = RunnerManager(settings=stub_settings)
    manager.runners["runner-z"] = {"config_hash": "hash", "sessions": {}}
    manager.session_to_runner["sess-1"] = "runner-z"

    context = await manager.get_runner_by_session("sess-1")
    assert context["config_hash"] == "hash"

    missing = await manager.get_runner_by_session("unknown")
    assert missing is None


class ShutdownRunner:
    def __init__(self, should_fail=False):
        self.shutdown_called = False
        self.should_fail = should_fail

    async def shutdown(self):
        self.shutdown_called = True
        if self.should_fail:
            raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_cleanup_runner_shuts_down_resources(stub_settings):
    cleaned_agents = []

    async def cleanup_callback(agent_id):
        cleaned_agents.append(agent_id)

    manager = RunnerManager(
        settings=stub_settings,
        agent_runner_mapping={"agent-a": "runner-clean"},
        agent_cleanup_callback=cleanup_callback,
    )

    service = DummySessionService()
    runner = ShutdownRunner()
    manager.runners["runner-clean"] = {
        "runner": runner,
        "session_service": service,
        "sessions": {"sess-1": SimpleNamespace(app_name="app", user_id="bob")},
        "session_user_ids": {"sess-1": "bob"},
        "config_hash": "hash-clean",
    }
    manager.config_to_runner["hash-clean"] = "runner-clean"
    manager.session_to_runner["sess-1"] = "runner-clean"

    result = await manager.cleanup_runner("runner-clean")
    assert result is True
    assert runner.shutdown_called is True
    assert service.shutdown_called is True
    assert cleaned_agents == ["agent-a"]
    assert "runner-clean" not in manager.runners
    assert "hash-clean" not in manager.config_to_runner


@pytest.mark.asyncio
async def test_cleanup_runner_returns_false_on_error(stub_settings):
    manager = RunnerManager(settings=stub_settings)
    runner = ShutdownRunner(should_fail=True)
    manager.runners["runner-bad"] = {
        "runner": runner,
        "session_service": DummySessionService(),
        "sessions": {},
        "session_user_ids": {},
        "config_hash": "hash-bad",
    }

    assert await manager.cleanup_runner("runner-bad") is False


@pytest.mark.asyncio
async def test_get_runner_stats_reports_counts(stub_settings):
    manager = RunnerManager(settings=stub_settings)
    now = datetime.utcnow()
    manager.runners["runner-stat"] = {
        "config_hash": "hash-stat",
        "sessions": {"sess-1": object()},
        "created_at": now,
        "last_activity": now,
    }
    manager.session_to_runner["sess-1"] = "runner-stat"
    manager.config_to_runner["hash-stat"] = "runner-stat"

    stats = await manager.get_runner_stats()
    assert stats["total_runners"] == 1
    assert stats["total_sessions"] == 1
    assert stats["runners"][0]["session_count"] == 1


@pytest.mark.asyncio
async def test_get_runner_for_agent_error_paths():
    manager = RunnerManager()
    with pytest.raises(RuntimeError):
        await manager.get_runner_for_agent("agent-missing")

    manager = RunnerManager(agent_runner_mapping={})
    with pytest.raises(RuntimeError):
        await manager.get_runner_for_agent("agent-missing")

    manager = RunnerManager(agent_runner_mapping={"agent-1": "runner-missing"})
    manager.runners.clear()
    with pytest.raises(RuntimeError):
        await manager.get_runner_for_agent("agent-1")
