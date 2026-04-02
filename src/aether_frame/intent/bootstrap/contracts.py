# -*- coding: utf-8 -*-
"""Typed contracts for the narrowed bootstrap labeling MVP."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InputTraceSample:
    sample_id: str
    conversation_id: str
    user_message: str
    created_at: str
    session_id: Optional[str] = None
    invocation_id: Optional[str] = None
    llm_input_text: Optional[str] = None
    llm_output_text: Optional[str] = None
    agent_name: Optional[str] = None
    model_name: Optional[str] = None
    final_status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateScore:
    intent_name: str
    score: float


@dataclass
class PrelabelRecord:
    sample_id: str
    conversation_id: str
    text: str
    predicted_intent: str
    confidence: float
    top_candidates: List[CandidateScore] = field(default_factory=list)
    needs_review: bool = False
    review_reason: Optional[str] = None
    prediction_source: str = "helper_labeling_model"
    llm_output_text: Optional[str] = None
    final_status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewedLabelRecord:
    sample_id: str
    reviewed_intent: str
    review_notes: Optional[str] = None


@dataclass
class LabelingSummary:
    schema_version: str = "v1"
    total_samples: int = 0
    predicted_intent_counts: Dict[str, int] = field(default_factory=dict)
    needs_review_count: int = 0
    unknown_count: int = 0
    top_confusions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CapabilitySeedSlot:
    name: str
    required: bool = False
    description: str = ""


@dataclass
class CapabilitySeedIntent:
    intent_name: str
    description: str
    downstream_execution: str
    enabled: bool = True
    example_messages: List[str] = field(default_factory=list)
    initial_slots: List[CapabilitySeedSlot] = field(default_factory=list)


@dataclass
class CapabilitySeedFile:
    schema_version: str = "v1"
    capability_seeds: List[CapabilitySeedIntent] = field(default_factory=list)
