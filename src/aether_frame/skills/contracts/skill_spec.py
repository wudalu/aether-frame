# -*- coding: utf-8 -*-
"""Core skill metadata contracts."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple


DEFAULT_SKILL_CATEGORIES: Tuple[str, ...] = (
    "builtin",
    "mcp",
    "computer_use",
    "domain",
)
ACTIVE_SKILL_STATUS = "active"


@dataclass(frozen=True)
class SkillSpec:
    """Discovered skill metadata resolved from ``SKILL.md``."""

    skill_name: str
    display_name: str
    short_description: str
    display_order: int
    category: str
    status: str
    content_sha256: str
    skill_dir: Path
    source_path: Path
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_catalog_item(self) -> Dict[str, Any]:
        """Serialize to frontend-friendly catalog representation."""
        return {
            "skill_name": self.skill_name,
            "display_name": self.display_name,
            "short_description": self.short_description,
            "display_order": self.display_order,
            "category": self.category,
            "status": self.status,
        }
