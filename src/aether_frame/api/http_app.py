# -*- coding: utf-8 -*-
"""FastAPI application for exposing Aether Frame APIs."""

from contextlib import asynccontextmanager
import logging
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import FastAPI, HTTPException, Request

from ..bootstrap import create_system_components, shutdown_system
from ..config.settings import Settings


logger = logging.getLogger(__name__)


def create_http_app(settings: Optional[Settings] = None) -> FastAPI:
    """Create and configure the HTTP API application."""
    app_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        components = await create_system_components(app_settings)
        app.state.components = components
        try:
            yield
        finally:
            await shutdown_system(components)

    app = FastAPI(
        title="Aether Frame API",
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    app.state.components = None

    @app.get("/v1/skills")
    async def list_skills(request: Request) -> Dict[str, Any]:
        components = getattr(request.app.state, "components", None)
        if components is None:
            raise HTTPException(status_code=503, detail="System not initialized")

        # Preferred path: TaskFactory snapshot API
        task_factory = getattr(components, "task_factory", None)
        if task_factory and hasattr(task_factory, "get_skill_catalog_snapshot"):
            snapshot = await task_factory.get_skill_catalog_snapshot(active_only=True)
            return _normalize_snapshot(snapshot)

        # Fallback path: SkillCatalog direct access
        skill_catalog = getattr(components, "skill_catalog", None)
        if skill_catalog is not None:
            snapshot = skill_catalog.get_catalog_snapshot(active_only=True)
            return _normalize_snapshot(snapshot)

        return {"catalog_hash": "", "skills": []}

    return app


def _normalize_snapshot(snapshot: Any) -> Dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {"catalog_hash": "", "skills": []}
    catalog_hash = snapshot.get("catalog_hash")
    skills = snapshot.get("skills")
    return {
        "catalog_hash": catalog_hash if isinstance(catalog_hash, str) else "",
        "skills": skills if isinstance(skills, list) else [],
    }
