# -*- coding: utf-8 -*-
"""Unit tests for prompt-agent to skill conversion helpers."""

from pathlib import Path

from aether_frame.skills.runtime.agent_conversion import (
    convert_prompt_agents_to_skills,
    derive_skill_name,
)


def test_derive_skill_name_strips_agent_suffix():
    assert derive_skill_name("summary_rewrite_agent") == "summary_rewrite"
    assert derive_skill_name("Issue Triage Agent") == "issue_triage_agent"


def test_convert_prompt_agents_to_skills_dry_run(tmp_path: Path):
    records = [
        {
            "agent_name": "summary_rewrite_agent",
            "system_prompt": "Rewrite to concise summaries.",
            "available_tools": [],
            "description": "Rewrite summary",
            "category_hint": "builtin",
        },
        {
            "agent_name": "issue_triage_agent",
            "system_prompt": "Classify severity.",
            "available_tools": ["mcp.github.search_issues"],
            "category_hint": "mcp",
        },
    ]

    report = convert_prompt_agents_to_skills(
        records,
        output_root=tmp_path,
        apply_changes=False,
    )
    summary = report.to_dict()["counts"]
    assert summary["converted"] == 1
    assert summary["skipped_with_tools"] == 1
    assert summary["failed"] == 0
    assert not (tmp_path / "builtin" / "summary_rewrite" / "SKILL.md").exists()


def test_convert_prompt_agents_to_skills_apply_writes_skill_file(tmp_path: Path):
    records = [
        {
            "agent_name": "summary_rewrite_agent",
            "system_prompt": "Rewrite to concise summaries.",
            "available_tools": [],
            "description": "Rewrite summary",
            "category_hint": "builtin",
        }
    ]

    report = convert_prompt_agents_to_skills(
        records,
        output_root=tmp_path,
        apply_changes=True,
    )
    assert report.to_dict()["counts"]["converted"] == 1

    skill_md = tmp_path / "builtin" / "summary_rewrite" / "SKILL.md"
    assert skill_md.exists()
    content = skill_md.read_text(encoding="utf-8")
    assert "skill_name: summary_rewrite" in content
    assert "Rewrite to concise summaries." in content
