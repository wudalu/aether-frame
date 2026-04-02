# -*- coding: utf-8 -*-
"""I/O helpers for the narrowed bootstrap labeling MVP."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .contracts import (
    CapabilitySeedFile,
    CapabilitySeedIntent,
    CapabilitySeedSlot,
    InputTraceSample,
    LabelingSummary,
    PrelabelRecord,
    ReviewedLabelRecord,
)


def load_input_trace_samples(path: Path) -> List[InputTraceSample]:
    """Load input trace rows from JSONL or JSON array files."""
    records = _load_records(path)
    return [_input_trace_from_dict(record) for record in records]


def load_capability_seed_file(path: Path) -> CapabilitySeedFile:
    """Load capability seed file from JSON or YAML when available."""
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return _load_capability_seed_yaml(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Capability seed file must be a JSON object")

    return _capability_seed_file_from_dict(payload)


def load_reviewed_labels(path: Path) -> List[ReviewedLabelRecord]:
    """Load reviewed label rows from JSONL or JSON array files."""
    records = _load_records(path)
    return [_reviewed_label_from_dict(record) for record in records]


def write_prelabel_outputs(
    *,
    output_dir: Path,
    records: List[PrelabelRecord],
    summary: LabelingSummary,
) -> None:
    """Write the narrowed MVP outputs into the target directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    review_dir = output_dir / "review_payloads"
    review_dir.mkdir(parents=True, exist_ok=True)

    _write_jsonl(output_dir / "prelabels.jsonl", [asdict(record) for record in records])
    (output_dir / "labeling_summary.json").write_text(
        json.dumps(asdict(summary), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    review_payloads = []
    unknown_rows = []
    for record in records:
        row = asdict(record)
        if record.predicted_intent == "unknown":
            unknown_rows.append(row)
        if record.needs_review or record.predicted_intent == "unknown":
            review_payloads.append(
                {
                    "id": record.sample_id,
                    "data": {
                        "sample_id": record.sample_id,
                        "conversation_id": record.conversation_id,
                        "text": record.text,
                        "predicted_intent": record.predicted_intent,
                        "confidence": record.confidence,
                        "top_candidates": row["top_candidates"],
                        "review_reason": record.review_reason,
                        "llm_output_text": record.llm_output_text,
                    },
                }
            )

    _write_jsonl(review_dir / "label_studio.jsonl", review_payloads)
    _write_jsonl(output_dir / "unknown_samples.jsonl", unknown_rows)


def write_draft_registry_outputs(*, output_dir: Path, artifacts: Dict[str, Any]) -> None:
    """Write minimal draft-registry artifacts into the target directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "candidate_intents.json").write_text(
        json.dumps(artifacts["candidate_intents"], indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    (output_dir / "slot_candidates.json").write_text(
        json.dumps(artifacts["slot_candidates"], indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    (output_dir / "draft_registry.json").write_text(
        json.dumps(artifacts["draft_registry"], indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    (output_dir / "review_report.md").write_text(
        artifacts["review_report"],
        encoding="utf-8",
    )


def _load_records(path: Path) -> List[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON input file must contain an array of objects")
        return [_ensure_dict(row, context=str(path)) for row in payload]
    if suffix != ".jsonl":
        raise ValueError(f"Unsupported input file format: {path}")

    records: List[Dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        row = json.loads(stripped)
        records.append(_ensure_dict(row, context=f"{path}:{line_no}"))
    return records


def _ensure_dict(value: Any, *, context: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Expected object row in {context}")
    return value


def _input_trace_from_dict(payload: Dict[str, Any]) -> InputTraceSample:
    return InputTraceSample(
        sample_id=_require_string(payload, "sample_id"),
        conversation_id=_require_string(payload, "conversation_id"),
        user_message=_require_string(payload, "user_message"),
        created_at=_require_string(payload, "created_at"),
        session_id=_optional_string(payload, "session_id"),
        invocation_id=_optional_string(payload, "invocation_id"),
        llm_input_text=_optional_string(payload, "llm_input_text"),
        llm_output_text=_optional_string(payload, "llm_output_text"),
        agent_name=_optional_string(payload, "agent_name"),
        model_name=_optional_string(payload, "model_name"),
        final_status=_optional_string(payload, "final_status"),
        metadata=_optional_dict(payload.get("metadata")),
    )


def _capability_seed_file_from_dict(payload: Dict[str, Any]) -> CapabilitySeedFile:
    raw_seeds = payload.get("capability_seeds", [])
    if not isinstance(raw_seeds, list):
        raise ValueError("capability_seeds must be an array")

    seeds: List[CapabilitySeedIntent] = []
    for raw_seed in raw_seeds:
        seed = _ensure_dict(raw_seed, context="capability_seeds")
        raw_slots = seed.get("initial_slots", [])
        if not isinstance(raw_slots, list):
            raise ValueError("initial_slots must be an array")
        slots = [
            CapabilitySeedSlot(
                name=_require_string(slot, "name"),
                required=bool(slot.get("required", False)),
                description=_optional_string(slot, "description") or "",
            )
            for slot in [_ensure_dict(item, context="initial_slots") for item in raw_slots]
        ]
        examples = seed.get("example_messages", [])
        if not isinstance(examples, list):
            raise ValueError("example_messages must be an array")
        seeds.append(
            CapabilitySeedIntent(
                intent_name=_require_string(seed, "intent_name"),
                description=_require_string(seed, "description"),
                downstream_execution=_require_string(seed, "downstream_execution"),
                enabled=bool(seed.get("enabled", True)),
                example_messages=[
                    item.strip()
                    for item in examples
                    if isinstance(item, str) and item.strip()
                ],
                initial_slots=slots,
            )
        )

    schema_version = _optional_string(payload, "schema_version") or "v1"
    return CapabilitySeedFile(schema_version=schema_version, capability_seeds=seeds)


def _reviewed_label_from_dict(payload: Dict[str, Any]) -> ReviewedLabelRecord:
    return ReviewedLabelRecord(
        sample_id=_require_string(payload, "sample_id"),
        reviewed_intent=_require_string(payload, "reviewed_intent"),
        review_notes=_optional_string(payload, "review_notes"),
    )


def _load_capability_seed_yaml(path: Path) -> CapabilitySeedFile:
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on env
        raise RuntimeError(
            "YAML capability seed files require PyYAML. Use JSON or install PyYAML."
        ) from exc

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Capability seed YAML must contain an object")
    return _capability_seed_file_from_dict(payload)


def _require_string(payload: Dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_string(payload: Dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string when provided")
    stripped = value.strip()
    return stripped or None


def _optional_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("metadata must be an object when provided")
    return dict(value)


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    content = "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")
