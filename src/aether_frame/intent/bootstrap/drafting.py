# -*- coding: utf-8 -*-
"""Minimal reviewed-labels to draft-registry generation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from .contracts import CapabilitySeedFile, InputTraceSample, ReviewedLabelRecord


def build_draft_registry_artifacts(
    samples: List[InputTraceSample],
    reviewed_labels: List[ReviewedLabelRecord],
    seeds: CapabilitySeedFile,
) -> Dict[str, Any]:
    """Build minimal reviewable draft-registry artifacts from reviewed labels."""
    sample_by_id = {sample.sample_id: sample for sample in samples}
    seed_by_intent = {seed.intent_name: seed for seed in seeds.capability_seeds if seed.enabled}

    grouped_samples: Dict[str, List[InputTraceSample]] = defaultdict(list)
    for label in reviewed_labels:
        if label.reviewed_intent == "unknown":
            continue
        sample = sample_by_id.get(label.sample_id)
        if sample is None:
            continue
        grouped_samples[label.reviewed_intent].append(sample)

    candidate_rows: List[Dict[str, Any]] = []
    slot_rows: List[Dict[str, Any]] = []
    draft_intents: List[Dict[str, Any]] = []

    for intent_name in sorted(grouped_samples):
        intent_samples = grouped_samples[intent_name]
        seed = seed_by_intent.get(intent_name)
        if seed is None:
            continue

        example_messages = _dedupe_preserve_order(
            [sample.user_message for sample in intent_samples]
        )[:5]
        sample_count = len(intent_samples)

        candidate_rows.append(
            {
                "intent_name": intent_name,
                "description": seed.description,
                "sample_count": sample_count,
                "confidence": "reviewed",
                "example_messages": example_messages,
                "confusing_neighbors": [],
                "recommended_action": "promote",
            }
        )

        required_slots: List[Dict[str, Any]] = []
        optional_slots: List[Dict[str, Any]] = []
        for slot in seed.initial_slots:
            slot_row = {
                "intent_name": intent_name,
                "slot_name": slot.name,
                "required": slot.required,
                "evidence_count": sample_count,
                "clarification_question": _default_clarification_question(slot.name),
                "clarification_priority": 10 if slot.required else 100,
                "notes": [],
            }
            slot_rows.append(slot_row)
            slot_payload = {
                "name": slot.name,
                "required": slot.required,
                "description": slot.description,
                "clarification_question": slot_row["clarification_question"],
                "clarification_priority": slot_row["clarification_priority"],
            }
            if slot.required:
                required_slots.append(slot_payload)
            else:
                optional_slots.append(slot_payload)

        draft_intents.append(
            {
                "name": intent_name,
                "description": seed.description,
                "examples": example_messages,
                "negative_examples": [],
                "required_slots": required_slots,
                "optional_slots": optional_slots,
            }
        )

    candidate_payload = {
        "schema_version": "v1",
        "candidates": candidate_rows,
    }
    slot_payload = {
        "schema_version": "v1",
        "slot_candidates": slot_rows,
    }
    draft_registry_payload = {
        "schema_version": "v1",
        "registry_name": "intent_registry_bootstrap_draft",
        "generated_at": None,
        "intents": draft_intents,
    }
    review_report = _build_review_report(candidate_rows, slot_rows)

    return {
        "candidate_intents": candidate_payload,
        "slot_candidates": slot_payload,
        "draft_registry": draft_registry_payload,
        "review_report": review_report,
    }


def _default_clarification_question(slot_name: str) -> str:
    words = slot_name.replace("_", " ")
    return f"Please provide {words}."


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _build_review_report(
    candidate_rows: List[Dict[str, Any]],
    slot_rows: List[Dict[str, Any]],
) -> str:
    lines = [
        "# Review Report",
        "",
        "## Proposed Intent Set",
        "",
    ]
    if not candidate_rows:
        lines.append("No reviewed intent candidates were available.")
    else:
        for row in candidate_rows:
            lines.append(
                f"- {row['intent_name']}: {row['sample_count']} reviewed samples"
            )

    lines.extend(["", "## Slot Candidates", ""])
    if not slot_rows:
        lines.append("No slot candidates were produced.")
    else:
        for row in slot_rows:
            required_label = "required" if row["required"] else "optional"
            lines.append(
                f"- {row['intent_name']} -> {row['slot_name']} ({required_label})"
            )

    return "\n".join(lines) + "\n"
