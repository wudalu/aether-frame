# -*- coding: utf-8 -*-
"""In-memory skill catalog with validation helpers."""

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from ..contracts import ACTIVE_SKILL_STATUS, DEFAULT_SKILL_CATEGORIES, SkillSpec
from .local_skill_discovery import discover_skill_specs


class SkillCatalogError(ValueError):
    """Base class for skill catalog validation errors."""


class SkillConflictError(SkillCatalogError):
    """Raised when duplicate ``skill_name`` entries are discovered."""


class SkillNotFoundError(SkillCatalogError):
    """Raised when one or more skill names are not in catalog."""


class SkillInactiveError(SkillCatalogError):
    """Raised when requested skills are not in ``active`` status."""


class SkillCatalog:
    """Catalog of local skills discovered from ``SKILL.md`` files."""

    def __init__(
        self,
        skill_root: Path,
        categories: Sequence[str] = DEFAULT_SKILL_CATEGORIES,
        auto_refresh: bool = True,
    ):
        self.skill_root = skill_root
        self.categories = tuple(categories)
        self._skills_by_name: Dict[str, SkillSpec] = {}
        if auto_refresh:
            self.refresh()

    @property
    def size(self) -> int:
        return len(self._skills_by_name)

    def refresh(self) -> None:
        """Rescan the filesystem and rebuild catalog entries."""
        discovered = discover_skill_specs(
            skill_root=self.skill_root,
            categories=self.categories,
        )
        skills_by_name: Dict[str, SkillSpec] = {}
        duplicates: List[str] = []

        for spec in discovered:
            if spec.skill_name in skills_by_name:
                duplicates.append(spec.skill_name)
                continue
            skills_by_name[spec.skill_name] = spec

        if duplicates:
            unique = sorted(set(duplicates))
            raise SkillConflictError(
                f"Duplicate skill_name detected: {', '.join(unique)}"
            )

        self._skills_by_name = skills_by_name

    def list_skills(self, active_only: bool = True) -> List[SkillSpec]:
        """Return all catalog skills, optionally filtering inactive entries."""
        category_order = {name: idx for idx, name in enumerate(self.categories)}
        specs = sorted(
            self._skills_by_name.values(),
            key=lambda item: (
                category_order.get(item.category, len(category_order)),
                item.display_order,
                item.skill_name,
            ),
        )
        if not active_only:
            return specs
        return [spec for spec in specs if spec.status == ACTIVE_SKILL_STATUS]

    def list_catalog_items(self, active_only: bool = True) -> List[Dict[str, object]]:
        """Return frontend-friendly skill list."""
        return [spec.to_catalog_item() for spec in self.list_skills(active_only=active_only)]

    def compute_catalog_hash(self, active_only: bool = True) -> str:
        """Compute deterministic hash for skill consistency checks."""
        items = self.list_skills(active_only=active_only)
        payload = [
            {
                "skill_name": spec.skill_name,
                "category": spec.category,
                "display_order": spec.display_order,
                "status": spec.status,
                "content_sha256": spec.content_sha256,
            }
            for spec in items
        ]
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get_catalog_snapshot(self, active_only: bool = True) -> Dict[str, object]:
        """Return skills plus a deterministic catalog hash."""
        return {
            "catalog_hash": self.compute_catalog_hash(active_only=active_only),
            "skills": self.list_catalog_items(active_only=active_only),
        }

    def get_skill(self, skill_name: str) -> Optional[SkillSpec]:
        """Get one skill by name."""
        return self._skills_by_name.get(skill_name)

    def resolve_skill_names(
        self,
        skill_names: Optional[Iterable[str]],
        *,
        active_only: bool = True,
    ) -> List[SkillSpec]:
        """Validate and resolve ordered skill names into specs."""
        normalized = _validate_skill_names(skill_names)
        if not normalized:
            return []

        missing: List[str] = []
        inactive: List[str] = []
        resolved: List[SkillSpec] = []

        for name in normalized:
            spec = self._skills_by_name.get(name)
            if not spec:
                missing.append(name)
                continue
            if active_only and spec.status != ACTIVE_SKILL_STATUS:
                inactive.append(name)
                continue
            resolved.append(spec)

        if missing:
            raise SkillNotFoundError(f"Skill not found: {', '.join(missing)}")
        if inactive:
            raise SkillInactiveError(f"Inactive skill: {', '.join(inactive)}")
        return resolved


def _validate_skill_names(skill_names: Optional[Iterable[str]]) -> List[str]:
    if skill_names is None:
        return []
    if not isinstance(skill_names, list):
        raise SkillCatalogError("skill_names must be a list of strings")

    normalized: List[str] = []
    seen = set()
    for raw in skill_names:
        if not isinstance(raw, str) or not raw.strip():
            raise SkillCatalogError("skill_names must contain non-empty strings")
        name = raw.strip()
        if name in seen:
            raise SkillCatalogError(f"Duplicate skill in request: {name}")
        seen.add(name)
        normalized.append(name)
    return normalized
