# -*- coding: utf-8 -*-
"""Unit tests for RunnerManager session lifecycle behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from aether_frame.config.settings import Settings
from aether_frame.framework.adk.runner_manager import RunnerManager
from tests.fixtures.factories import make_agent_config, make_task_request


@pytest.mark.asyncio
async def test_get_or_create_runner_reuses_existing_runner(monkeypatch):
    settings = Settings(
        default_app_name="app",
        default_user_id="user",
        runner_id_prefix="runner",
        session_id_prefix="session",
    )
    manager = RunnerManager(settings=settings)
    agent_config = make_agent_config(agent_type="helper")

    create_runner_mock = AsyncMock(return_value="runner-1")
    create_session_mock = AsyncMock(return_value="session-abc")
    monkeypatch.setattr(manager, "_create_new_runner", create_runner_mock)
    monkeypatch.setattr(manager, "_create_session_in_runner", create_session_mock)

    runner_id, session_id = await manager.get_or_create_runner(
        agent_config,
        task_request=make_task_request(agent_id="agent-1"),
        engine_session_id="session-abc",
    )

    assert runner_id == "runner-1"
    assert session_id == "session-abc"
    create_runner_mock.assert_awaited_once()
    create_session_mock.assert_awaited_once()

    # Second call should reuse runner and skip creation
    create_runner_mock.reset_mock()
    create_session_mock.reset_mock()

    runner_id2, session_id2 = await manager.get_or_create_runner(
        agent_config,
        task_request=None,
        allow_reuse=True,
        create_session=False,
    )

    assert runner_id2 == "runner-1"
    assert session_id2 is None
    create_runner_mock.assert_not_called()
    create_session_mock.assert_not_called()


@pytest.mark.asyncio
async def test_remove_session_from_runner_cleans_mappings():
    settings = Settings(default_app_name="app", default_user_id="user")
    manager = RunnerManager(settings=settings)

    class FakeSessionService:
        def __init__(self):
            self.deleted = []

        async def delete_session(self, app_name, user_id, session_id):
            self.deleted.append((app_name, user_id, session_id))

    session_service = FakeSessionService()
    adk_session = SimpleNamespace(app_name="app", user_id="user")

    manager.runners["runner-1"] = {
        "session_service": session_service,
        "sessions": {"session-1": adk_session},
        "session_user_ids": {"session-1": "user"},
    }
    manager.session_to_runner["session-1"] = "runner-1"

    removed = await manager.remove_session_from_runner("runner-1", "session-1")

    assert removed is True
    assert "session-1" not in manager.session_to_runner
    assert session_service.deleted == [("app", "user", "session-1")]


@pytest.mark.asyncio
async def test_cleanup_runner_triggers_shutdown_and_callbacks():
    settings = Settings(default_app_name="app", default_user_id="user")
    agent_runner_mapping = {"agent-1": "runner-2"}
    cleanup_callback = AsyncMock()
    manager = RunnerManager(
        settings=settings,
        agent_runner_mapping=agent_runner_mapping,
        agent_cleanup_callback=cleanup_callback,
    )

    runner_stub = MagicMock()
    runner_stub.shutdown = AsyncMock()
    session_service_stub = MagicMock()
    session_service_stub.shutdown = AsyncMock()

    manager.runners["runner-2"] = {
        "runner": runner_stub,
        "session_service": session_service_stub,
        "sessions": {"sess": {}},
        "session_user_ids": {"sess": "user"},
        "config_hash": "hash-1",
    }
    manager.session_to_runner["sess"] = "runner-2"
    manager.config_to_runner["hash-1"] = "runner-2"

    result = await manager.cleanup_runner("runner-2")

    assert result is True
    runner_stub.shutdown.assert_awaited_once()
    session_service_stub.shutdown.assert_awaited_once()
    cleanup_callback.assert_awaited_once_with("agent-1")
    assert "runner-2" not in manager.runners
    assert "hash-1" not in manager.config_to_runner
    assert "agent-1" not in agent_runner_mapping
