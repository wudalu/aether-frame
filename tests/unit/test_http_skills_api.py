# -*- coding: utf-8 -*-
"""Unit tests for the HTTP /v1/skills API."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from aether_frame.api import http_app
from aether_frame.config.settings import Settings


def test_v1_skills_returns_snapshot_from_task_factory(monkeypatch):
    class FakeTaskFactory:
        async def get_skill_catalog_snapshot(self, active_only=True):
            assert active_only is True
            return {
                "catalog_hash": "hash_abc",
                "skills": [
                    {
                        "skill_name": "summary_rewrite",
                        "display_name": "Summary Rewrite",
                        "short_description": "Rewrite long text.",
                        "display_order": 10,
                        "category": "builtin",
                        "status": "active",
                    }
                ],
            }

    async def fake_create_components(settings):
        return SimpleNamespace(
            framework_registry=object(),
            agent_manager=object(),
            execution_engine=object(),
            task_factory=FakeTaskFactory(),
            skill_catalog=None,
            tool_service=None,
        )

    async def fake_shutdown(components):
        return None

    monkeypatch.setattr(http_app, "create_system_components", fake_create_components)
    monkeypatch.setattr(http_app, "shutdown_system", fake_shutdown)

    app = http_app.create_http_app(Settings())
    with TestClient(app) as client:
        response = client.get("/v1/skills")
        assert response.status_code == 200
        payload = response.json()
        assert payload["catalog_hash"] == "hash_abc"
        assert payload["skills"][0]["display_order"] == 10


def test_v1_skills_falls_back_to_catalog(monkeypatch):
    class FakeCatalog:
        def get_catalog_snapshot(self, active_only=True):
            assert active_only is True
            return {
                "catalog_hash": "hash_from_catalog",
                "skills": [],
            }

    async def fake_create_components(settings):
        return SimpleNamespace(
            framework_registry=object(),
            agent_manager=object(),
            execution_engine=object(),
            task_factory=None,
            skill_catalog=FakeCatalog(),
            tool_service=None,
        )

    async def fake_shutdown(components):
        return None

    monkeypatch.setattr(http_app, "create_system_components", fake_create_components)
    monkeypatch.setattr(http_app, "shutdown_system", fake_shutdown)

    app = http_app.create_http_app(Settings())
    with TestClient(app) as client:
        response = client.get("/v1/skills")
        assert response.status_code == 200
        assert response.json() == {"catalog_hash": "hash_from_catalog", "skills": []}
