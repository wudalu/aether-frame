# -*- coding: utf-8 -*-
"""Error code registry and helpers for Aether Frame."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """Canonical error codes used across task and streaming responses."""

    INTERNAL_ERROR = "internal.error"
    REQUEST_VALIDATION = "request.validation"
    FRAMEWORK_UNAVAILABLE = "framework.unavailable"
    FRAMEWORK_EXECUTION = "framework.execution"
    MODEL_UPSTREAM = "model.upstream"
    STREAM_INTERRUPTED = "stream.interrupted"
    APPROVAL_TIMEOUT = "approval.timeout"
    TOOL_NOT_DECLARED = "tool.not_declared"
    TOOL_EXECUTION = "tool.execution"
    TOOL_PARAMETERS = "tool.invalid_parameters"


@dataclass
class ErrorPayload:
    """Structured error payload surfaced to callers."""

    code: str
    message: str
    source: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable representation."""
        payload = {
            "code": self.code,
            "message": self.message,
        }
        if self.source:
            payload["source"] = self.source
        if self.details:
            payload["details"] = self.details
        return payload


def build_error(
    code: ErrorCode,
    message: str,
    *,
    source: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> ErrorPayload:
    """Helper to construct an ErrorPayload."""
    return ErrorPayload(
        code=code.value if isinstance(code, ErrorCode) else str(code),
        message=message,
        source=source,
        details=dict(details or {}),
    )
