# -*- coding: utf-8 -*-
"""Local ``SKILL.md`` discovery and metadata parsing."""

import hashlib
from pathlib import Path
import re
from typing import Dict, List, Optional, Sequence, Tuple

from ..contracts import ACTIVE_SKILL_STATUS, DEFAULT_SKILL_CATEGORIES, SkillSpec


class SkillSpecParseError(ValueError):
    """Raised when a ``SKILL.md`` file cannot be parsed into a valid spec."""


def discover_skill_specs(
    skill_root: Path,
    categories: Sequence[str] = DEFAULT_SKILL_CATEGORIES,
) -> List[SkillSpec]:
    """Discover skill specs by scanning category directories for ``SKILL.md``."""
    specs: List[SkillSpec] = []
    for category in categories:
        category_dir = skill_root / category
        if not category_dir.exists() or not category_dir.is_dir():
            continue
        for skill_md in sorted(category_dir.rglob("SKILL.md")):
            specs.append(parse_skill_markdown(skill_md, fallback_category=category))
    return specs


def parse_skill_markdown(skill_md_path: Path, fallback_category: str) -> SkillSpec:
    """Parse one ``SKILL.md`` into a :class:`SkillSpec`."""
    text = skill_md_path.read_text(encoding="utf-8")
    content_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    front_matter, body = _split_front_matter(text)

    skill_dir = skill_md_path.parent
    raw_skill_name = front_matter.get("skill_name") or skill_dir.name
    skill_name = _normalize_skill_name(raw_skill_name)
    if not skill_name:
        raise SkillSpecParseError(f"Invalid skill_name in {skill_md_path}")

    category = (front_matter.get("category") or fallback_category or "").strip()
    if not category:
        raise SkillSpecParseError(f"Missing skill category for {skill_md_path}")

    display_name = (front_matter.get("display_name") or _to_display_name(skill_name)).strip()
    description = (
        front_matter.get("description")
        or _extract_body_description(body)
        or f"Skill {display_name}"
    ).strip()
    display_order = _parse_display_order(front_matter.get("display_order"))
    status = (front_matter.get("status") or ACTIVE_SKILL_STATUS).strip().lower()

    return SkillSpec(
        skill_name=skill_name,
        display_name=display_name,
        short_description=description,
        display_order=display_order,
        category=category,
        status=status,
        content_sha256=content_sha256,
        skill_dir=skill_dir,
        source_path=skill_md_path,
        metadata=front_matter,
    )


def _split_front_matter(text: str) -> Tuple[Dict[str, str], str]:
    """Split markdown front matter and body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_idx: Optional[int] = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        return {}, text

    front_lines = lines[1:end_idx]
    body_lines = lines[end_idx + 1 :]
    return _parse_front_matter(front_lines), "\n".join(body_lines).strip()


def _parse_front_matter(lines: Sequence[str]) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            data[key] = value
    return data


def _extract_body_description(body: str) -> str:
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        return line
    return ""


def _normalize_skill_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def _to_display_name(skill_name: str) -> str:
    words = [part for part in skill_name.split("_") if part]
    if not words:
        return skill_name
    return " ".join(word.capitalize() for word in words)


def _parse_display_order(raw_value: Optional[str]) -> int:
    if raw_value is None or raw_value == "":
        return 1000
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return 1000
