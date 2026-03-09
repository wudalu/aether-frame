#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Convert prompt-only exported agents into skill directories."""

import argparse
import json
from pathlib import Path
import sys
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aether_frame.skills.runtime.agent_conversion import (  # noqa: E402
    ConversionReport,
    convert_prompt_agents_to_skills,
    load_export_records,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert prompt-only agents to SKILL.md directories.",
    )
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="Export files (.json or .jsonl).",
    )
    parser.add_argument(
        "--output-root",
        default="src/aether_frame/skills",
        help="Target skills root directory.",
    )
    parser.add_argument(
        "--default-category",
        default="builtin",
        choices=["builtin", "mcp", "computer_use", "domain"],
        help="Fallback category when category_hint is absent/invalid.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write files. Without this flag the script runs in dry-run mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_paths: List[Path] = [Path(value).resolve() for value in args.input]
    output_root = Path(args.output_root).resolve()

    records = load_export_records(input_paths)
    report = convert_prompt_agents_to_skills(
        records,
        output_root=output_root,
        default_category=args.default_category,
        apply_changes=args.apply,
    )

    _print_report(report, apply_changes=args.apply, output_root=output_root)
    return 1 if report.failed else 0


def _print_report(
    report: ConversionReport, *, apply_changes: bool, output_root: Path
) -> None:
    mode = "apply" if apply_changes else "dry-run"
    print(f"[skill-converter] mode={mode} output_root={output_root}")
    summary = report.to_dict()
    counts = summary["counts"]
    print(
        "[skill-converter] "
        f"converted={counts['converted']} "
        f"skipped_with_tools={counts['skipped_with_tools']} "
        f"conflicts={counts['conflicts']} "
        f"failed={counts['failed']}"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
