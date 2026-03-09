# -*- coding: utf-8 -*-
"""Runtime selection and ADK loading helpers for skills."""

from typing import Any, Dict, List, Optional, Tuple

from ..adapters.adk import load_adk_skill_toolset
from ..registry import SkillCatalog


class SkillRuntime:
    """Skill runtime facade used by adapter/domain-agent orchestration."""

    def __init__(self, catalog: SkillCatalog):
        self.catalog = catalog
        self._adk_toolset_cache: Dict[Tuple[str, ...], List[Any]] = {}

    def refresh_catalog(self) -> None:
        """Refresh local catalog and clear loader cache."""
        self.catalog.refresh()
        self._adk_toolset_cache.clear()

    def list_active_skills(self) -> List[Dict[str, str]]:
        """Return frontend-facing active skill summaries."""
        return self.catalog.list_catalog_items(active_only=True)

    def validate_skill_names(self, skill_names: Optional[List[str]]) -> List[str]:
        """Validate list of skill names and return normalized request order."""
        specs = self.catalog.resolve_skill_names(skill_names, active_only=True)
        return [spec.skill_name for spec in specs]

    def load_adk_skill_tools(self, skill_names: Optional[List[str]]) -> List[Any]:
        """Resolve and load ADK skill toolsets for the selected skill names."""
        specs = self.catalog.resolve_skill_names(skill_names, active_only=True)
        if not specs:
            return []

        cache_key = tuple(spec.skill_name for spec in specs)
        cached = self._adk_toolset_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        toolsets = load_adk_skill_toolset(specs)
        self._adk_toolset_cache[cache_key] = list(toolsets)
        return list(toolsets)


def normalize_skill_name_list(raw: Any, *, source: str) -> Optional[List[str]]:
    """Validate one skill-name list field; returns ``None`` when not provided."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError(f"{source} must be a list of non-empty strings")

    normalized: List[str] = []
    seen = set()
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{source} must contain non-empty strings")
        value = item.strip()
        if value in seen:
            raise ValueError(f"{source} contains duplicate skill_name: {value}")
        seen.add(value)
        normalized.append(value)
    return normalized
