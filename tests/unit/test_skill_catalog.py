# -*- coding: utf-8 -*-
"""Unit tests for local skill discovery and catalog behavior."""

from pathlib import Path

import pytest

from aether_frame.skills.registry import (
    SkillCatalog,
    SkillInactiveError,
    SkillNotFoundError,
)


def _write_skill(path: Path, *, skill_name: str, status: str = "active") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "---\n"
            f"skill_name: {skill_name}\n"
            f"display_name: {skill_name}\n"
            "description: test skill\n"
            f"status: {status}\n"
            "---\n\n"
            "# Test Skill\n"
        ),
        encoding="utf-8",
    )


def test_skill_catalog_discovers_and_lists_active(tmp_path: Path):
    _write_skill(
        tmp_path / "builtin" / "summary_rewrite" / "SKILL.md",
        skill_name="summary_rewrite",
    )
    _write_skill(
        tmp_path / "mcp" / "repo_triage" / "SKILL.md",
        skill_name="repo_triage",
        status="inactive",
    )

    catalog = SkillCatalog(skill_root=tmp_path)
    active = catalog.list_catalog_items(active_only=True)
    all_items = catalog.list_catalog_items(active_only=False)

    assert [item["skill_name"] for item in active] == ["summary_rewrite"]
    assert sorted(item["skill_name"] for item in all_items) == [
        "repo_triage",
        "summary_rewrite",
    ]


def test_skill_catalog_resolve_raises_for_missing_or_inactive(tmp_path: Path):
    _write_skill(
        tmp_path / "builtin" / "summary_rewrite" / "SKILL.md",
        skill_name="summary_rewrite",
    )
    _write_skill(
        tmp_path / "domain" / "risk_check" / "SKILL.md",
        skill_name="risk_check",
        status="inactive",
    )
    catalog = SkillCatalog(skill_root=tmp_path)

    with pytest.raises(SkillNotFoundError):
        catalog.resolve_skill_names(["missing_skill"], active_only=True)

    with pytest.raises(SkillInactiveError):
        catalog.resolve_skill_names(["risk_check"], active_only=True)


def test_skill_catalog_orders_by_category_and_display_order(tmp_path: Path):
    (tmp_path / "builtin" / "skill_a").mkdir(parents=True, exist_ok=True)
    (tmp_path / "builtin" / "skill_b").mkdir(parents=True, exist_ok=True)
    (tmp_path / "mcp" / "skill_c").mkdir(parents=True, exist_ok=True)

    (tmp_path / "builtin" / "skill_a" / "SKILL.md").write_text(
        "---\nskill_name: skill_a\ndisplay_order: 20\ndescription: a\nstatus: active\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "builtin" / "skill_b" / "SKILL.md").write_text(
        "---\nskill_name: skill_b\ndisplay_order: 10\ndescription: b\nstatus: active\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "mcp" / "skill_c" / "SKILL.md").write_text(
        "---\nskill_name: skill_c\ndisplay_order: 1\ndescription: c\nstatus: active\n---\n",
        encoding="utf-8",
    )

    catalog = SkillCatalog(skill_root=tmp_path)
    items = catalog.list_catalog_items(active_only=True)

    assert [item["skill_name"] for item in items] == ["skill_b", "skill_a", "skill_c"]
    assert items[0]["display_order"] == 10


def test_skill_catalog_hash_changes_when_skill_content_changes(tmp_path: Path):
    skill_path = tmp_path / "builtin" / "summary_rewrite" / "SKILL.md"
    _write_skill(skill_path, skill_name="summary_rewrite")
    catalog = SkillCatalog(skill_root=tmp_path)
    first_hash = catalog.compute_catalog_hash(active_only=True)

    skill_path.write_text(
        (
            "---\n"
            "skill_name: summary_rewrite\n"
            "display_name: summary_rewrite\n"
            "description: changed description\n"
            "status: active\n"
            "---\n\n"
            "# Test Skill\n"
        ),
        encoding="utf-8",
    )
    catalog.refresh()
    second_hash = catalog.compute_catalog_hash(active_only=True)

    assert first_hash != second_hash
