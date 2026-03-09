# -*- coding: utf-8 -*-
"""Conversion utilities for migrating prompt-only agents into skills."""

import json
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Sequence

from ..contracts import DEFAULT_SKILL_CATEGORIES


SUPPORTED_EXPORT_SUFFIXES = {".json", ".jsonl"}
SUPPORTED_CATEGORIES = set(DEFAULT_SKILL_CATEGORIES)


@dataclass
class ConversionReport:
    """Structured conversion report for dry-run and apply modes."""

    converted: List[str] = field(default_factory=list)
    skipped_with_tools: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    failed: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "converted": self.converted,
            "skipped_with_tools": self.skipped_with_tools,
            "conflicts": self.conflicts,
            "failed": self.failed,
            "counts": {
                "converted": len(self.converted),
                "skipped_with_tools": len(self.skipped_with_tools),
                "conflicts": len(self.conflicts),
                "failed": len(self.failed),
            },
        }


def load_export_records(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    """Load exported agent records from ``.json`` or ``.jsonl`` files."""
    records: List[Dict[str, Any]] = []
    for path in paths:
        if path.suffix not in SUPPORTED_EXPORT_SUFFIXES:
            raise ValueError(f"Unsupported export file format: {path}")
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError(f"JSON export must be an array: {path}")
            for row in payload:
                if not isinstance(row, dict):
                    raise ValueError(f"JSON export row must be object: {path}")
                records.append(row)
            continue

        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"JSONL row must be object: {path}:{line_no}")
            records.append(row)
    return records


def convert_prompt_agents_to_skills(
    records: Iterable[Dict[str, Any]],
    *,
    output_root: Path,
    default_category: str = "builtin",
    apply_changes: bool = False,
) -> ConversionReport:
    """Convert prompt-only agent records into ``SKILL.md`` directories."""
    if default_category not in SUPPORTED_CATEGORIES:
        raise ValueError(
            f"default_category must be one of {sorted(SUPPORTED_CATEGORIES)}"
        )

    report = ConversionReport()
    seen_skill_names = set()

    for index, record in enumerate(records, start=1):
        try:
            agent_name = _require_non_empty_string(record, "agent_name")
            system_prompt = _require_non_empty_string(record, "system_prompt")
            available_tools = record.get("available_tools")
            if not isinstance(available_tools, list):
                raise ValueError("available_tools must be an array")

            if available_tools:
                report.skipped_with_tools.append(agent_name)
                continue

            skill_name = derive_skill_name(agent_name)
            if not skill_name:
                raise ValueError("derived skill_name is empty")

            if skill_name in seen_skill_names:
                report.conflicts.append(
                    f"{agent_name}: duplicate derived skill_name '{skill_name}'"
                )
                continue
            seen_skill_names.add(skill_name)

            category_hint = record.get("category_hint")
            category = (
                category_hint
                if isinstance(category_hint, str) and category_hint in SUPPORTED_CATEGORIES
                else default_category
            )
            skill_md_path = output_root / category / skill_name / "SKILL.md"

            if skill_md_path.exists():
                report.conflicts.append(
                    f"{agent_name}: target already exists at {skill_md_path}"
                )
                continue

            content = build_skill_markdown(
                skill_name=skill_name,
                category=category,
                system_prompt=system_prompt,
                source_agent_name=agent_name,
                description=record.get("description"),
            )

            if apply_changes:
                skill_md_path.parent.mkdir(parents=True, exist_ok=True)
                skill_md_path.write_text(content, encoding="utf-8")

            report.converted.append(skill_name)
        except Exception as exc:  # noqa: BLE001
            report.failed.append(
                {
                    "index": str(index),
                    "reason": str(exc),
                }
            )

    return report


def derive_skill_name(agent_name: str) -> str:
    """Derive normalized ``skill_name`` from source ``agent_name``."""
    lowered = agent_name.strip().lower()
    if lowered.endswith("_agent"):
        lowered = lowered[: -len("_agent")]
    normalized = re.sub(r"[^a-z0-9_]+", "_", lowered)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def build_skill_markdown(
    *,
    skill_name: str,
    category: str,
    system_prompt: str,
    source_agent_name: str,
    description: Any = None,
) -> str:
    """Build ``SKILL.md`` content for one converted skill."""
    display_name = " ".join(part.capitalize() for part in skill_name.split("_") if part)
    short_description = (
        description.strip()
        if isinstance(description, str) and description.strip()
        else f"Migrated from agent '{source_agent_name}'"
    )
    slug_name = skill_name.replace("_", "-")
    prompt_body = system_prompt.strip()
    return (
        "---\n"
        f"name: {slug_name}\n"
        f"description: {short_description}\n"
        f"skill_name: {skill_name}\n"
        f"display_name: {display_name}\n"
        f"category: {category}\n"
        "status: active\n"
        f"source_agent_name: {source_agent_name}\n"
        "---\n\n"
        f"# {display_name}\n\n"
        "## Instructions\n\n"
        f"{prompt_body}\n"
    )


def _require_non_empty_string(record: Dict[str, Any], field: str) -> str:
    raw = record.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return raw.strip()
