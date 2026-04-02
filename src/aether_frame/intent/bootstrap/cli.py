# -*- coding: utf-8 -*-
"""CLI for the narrowed bootstrap labeling MVP."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Sequence

from .io import (
    load_capability_seed_file,
    load_input_trace_samples,
    load_reviewed_labels,
    write_draft_registry_outputs,
    write_prelabel_outputs,
)
from .drafting import build_draft_registry_artifacts
from .labeling import prelabel_samples


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap intent registry artifacts from offline traces."
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["prelabel-review", "report-only", "draft-registry", "evaluate-registry"],
    )
    parser.add_argument("--input-traces", required=True)
    parser.add_argument("--capability-seeds")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--draft-registry")
    parser.add_argument("--reviewed-labels")
    parser.add_argument("--public-benchmark-config")
    parser.add_argument("--enable-helper-labeling", action="store_true")
    parser.add_argument("--enable-llm-summarization", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.mode == "prelabel-review":
        if not args.capability_seeds:
            raise ValueError("--capability-seeds is required for prelabel-review mode")

        input_traces = load_input_trace_samples(Path(args.input_traces))
        seed_file = load_capability_seed_file(Path(args.capability_seeds))
        records, summary = prelabel_samples(input_traces, seed_file)
        write_prelabel_outputs(
            output_dir=Path(args.output_dir),
            records=records,
            summary=summary,
        )
        return 0

    if args.mode == "draft-registry":
        if not args.capability_seeds:
            raise ValueError("--capability-seeds is required for draft-registry mode")
        if not args.reviewed_labels:
            raise ValueError("--reviewed-labels is required for draft-registry mode")

        input_traces = load_input_trace_samples(Path(args.input_traces))
        seed_file = load_capability_seed_file(Path(args.capability_seeds))
        reviewed_labels = load_reviewed_labels(Path(args.reviewed_labels))
        artifacts = build_draft_registry_artifacts(
            input_traces,
            reviewed_labels,
            seed_file,
        )
        write_draft_registry_outputs(
            output_dir=Path(args.output_dir),
            artifacts=artifacts,
        )
        return 0

    raise ValueError(
        "Only prelabel-review and draft-registry are implemented in the narrowed MVP."
    )


def cli_main() -> None:
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    cli_main()
