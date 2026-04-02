# -*- coding: utf-8 -*-
"""Machine-assisted prelabeling for the narrowed bootstrap labeling MVP."""

from __future__ import annotations

import math
import re
from typing import Dict, Iterable, List, Set, Tuple

from .contracts import (
    CandidateScore,
    CapabilitySeedFile,
    CapabilitySeedIntent,
    InputTraceSample,
    LabelingSummary,
    PrelabelRecord,
)


UNKNOWN_THRESHOLD = 0.2
CONFUSION_MARGIN = 0.08
LOW_CONFIDENCE_REVIEW_THRESHOLD = 0.55

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "for",
    "from",
    "give",
    "i",
    "into",
    "is",
    "me",
    "of",
    "or",
    "please",
    "the",
    "this",
    "to",
    "what",
    "you",
}


def prelabel_samples(
    samples: Iterable[InputTraceSample],
    seeds: CapabilitySeedFile,
) -> Tuple[List[PrelabelRecord], LabelingSummary]:
    """Produce machine-assisted prelabels and a compact summary."""
    enabled_seeds = [seed for seed in seeds.capability_seeds if seed.enabled]
    records: List[PrelabelRecord] = []
    confusion_counts: Dict[Tuple[str, str], int] = {}
    predicted_counts: Dict[str, int] = {}
    needs_review_count = 0
    unknown_count = 0

    for sample in samples:
        record = _prelabel_one_sample(sample, enabled_seeds)
        records.append(record)

        predicted_counts[record.predicted_intent] = (
            predicted_counts.get(record.predicted_intent, 0) + 1
        )
        if record.needs_review:
            needs_review_count += 1
        if record.predicted_intent == "unknown":
            unknown_count += 1

        if record.review_reason == "high_confusion" and len(record.top_candidates) >= 2:
            a = record.top_candidates[0].intent_name
            b = record.top_candidates[1].intent_name
            key = tuple(sorted((a, b)))
            confusion_counts[key] = confusion_counts.get(key, 0) + 1

    summary = LabelingSummary(
        total_samples=len(records),
        predicted_intent_counts=predicted_counts,
        needs_review_count=needs_review_count,
        unknown_count=unknown_count,
        top_confusions=[
            {"intent_a": a, "intent_b": b, "count": count}
            for (a, b), count in sorted(
                confusion_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
    )
    return records, summary


def _prelabel_one_sample(
    sample: InputTraceSample,
    seeds: List[CapabilitySeedIntent],
) -> PrelabelRecord:
    text = sample.user_message.strip()
    sample_tokens = _tokenize(text)

    candidate_scores: List[CandidateScore] = []
    for seed in seeds:
        score = _score_seed(sample_tokens, seed)
        candidate_scores.append(
            CandidateScore(intent_name=seed.intent_name, score=round(score, 4))
        )

    candidate_scores.sort(key=lambda item: (-item.score, item.intent_name))

    top_score = candidate_scores[0].score if candidate_scores else 0.0
    second_score = candidate_scores[1].score if len(candidate_scores) > 1 else 0.0

    predicted_intent = candidate_scores[0].intent_name if candidate_scores else "unknown"
    confidence = top_score
    needs_review = False
    review_reason = None

    if top_score < UNKNOWN_THRESHOLD:
        predicted_intent = "unknown"
        needs_review = True
        review_reason = "no_confident_candidate"
    elif candidate_scores and abs(top_score - second_score) <= CONFUSION_MARGIN:
        needs_review = True
        review_reason = "high_confusion"
    elif top_score < LOW_CONFIDENCE_REVIEW_THRESHOLD:
        needs_review = True
        review_reason = "low_confidence"

    return PrelabelRecord(
        sample_id=sample.sample_id,
        conversation_id=sample.conversation_id,
        text=text,
        predicted_intent=predicted_intent,
        confidence=confidence,
        top_candidates=candidate_scores[:3],
        needs_review=needs_review,
        review_reason=review_reason,
        llm_output_text=sample.llm_output_text,
        final_status=sample.final_status,
        metadata={
            key: value
            for key, value in {
                "agent_name": sample.agent_name,
                "model_name": sample.model_name,
                "session_id": sample.session_id,
                **sample.metadata,
            }.items()
            if value is not None
        },
    )


def _score_seed(sample_tokens: Set[str], seed: CapabilitySeedIntent) -> float:
    if not sample_tokens:
        return 0.0

    seed_text_parts = [
        seed.intent_name.replace("_", " "),
        seed.description,
        *seed.example_messages,
    ]
    seed_tokens = _tokenize(" ".join(seed_text_parts))
    if not seed_tokens:
        return 0.0

    overlap = sample_tokens & seed_tokens
    if not overlap:
        return 0.0

    return len(overlap) / math.sqrt(len(sample_tokens) * len(seed_tokens))


def _tokenize(text: str) -> Set[str]:
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower().replace("_", " "))
        if token and token not in STOP_WORDS
    }
    return tokens
