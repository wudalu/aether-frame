# -*- coding: utf-8 -*-
"""Native ADK skill loading utilities."""

from typing import Any, List, Sequence

from ...contracts import SkillSpec


class AdkSkillLoaderError(RuntimeError):
    """Raised when ADK native skill loading is unavailable or fails."""


def load_adk_skill_toolset(skill_specs: Sequence[SkillSpec]) -> List[Any]:
    """Load ADK skills from local directories and wrap with ``SkillToolset``."""
    if not skill_specs:
        return []

    try:
        from google.adk.skills import load_skill_from_dir  # type: ignore
        from google.adk.tools.skill_toolset import SkillToolset  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise AdkSkillLoaderError(
            "ADK skill APIs are unavailable. Upgrade google-adk to >=1.25.0."
        ) from exc

    loaded_skills = []
    for spec in skill_specs:
        try:
            loaded_skills.append(load_skill_from_dir(spec.skill_dir))
        except Exception as exc:  # pragma: no cover - delegated runtime behavior
            raise AdkSkillLoaderError(
                f"Failed to load skill '{spec.skill_name}' from {spec.skill_dir}: {exc}"
            ) from exc

    return [SkillToolset(skills=loaded_skills)]
