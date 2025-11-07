# -*- coding: utf-8 -*-
"""Unit tests for contracts.errors helpers."""

from aether_frame.contracts import ErrorCode, build_error
from aether_frame.contracts.errors import ErrorPayload


def test_error_payload_to_dict_omits_empty_fields():
    payload = ErrorPayload(code="x", message="y")
    assert payload.to_dict() == {"code": "x", "message": "y"}

    payload.details["info"] = 1
    payload.source = "test"
    assert payload.to_dict() == {
        "code": "x",
        "message": "y",
        "source": "test",
        "details": {"info": 1},
    }


def test_build_error_accepts_enum_or_string():
    err = build_error(ErrorCode.TOOL_EXECUTION, "boom", source="svc")
    assert err.code == ErrorCode.TOOL_EXECUTION.value
    assert err.message == "boom"
    assert err.source == "svc"

    err2 = build_error("custom.code", "fail")
    assert err2.code == "custom.code"
