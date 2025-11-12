# -*- coding: utf-8 -*-
"""Unit tests for contracts.contexts helpers."""

from aether_frame.contracts import (
    ExecutionContext,
    FrameworkType,
    ImageReference,
    SessionContext,
    UserContext,
)


def test_user_context_adk_id_priority():
    assert UserContext(user_id="u-1").get_adk_user_id() == "u-1"
    assert UserContext(user_name="alice").get_adk_user_id() == "user_alice"
    assert (
        UserContext(session_token="abcd1234efgh").get_adk_user_id()
        == "session_abcd1234"
    )
    assert UserContext().get_adk_user_id() == "anonymous_user"


def test_session_context_and_execution_context_defaults():
    ctx = SessionContext(session_id="s-1")
    assert ctx.get_adk_session_id() == "s-1"
    ctx.session_id = None
    ctx.conversation_id = "c-1"
    assert ctx.get_adk_session_id() == "c-1"

    exec_ctx = ExecutionContext(execution_id="exec-1", framework_type=FrameworkType.ADK)
    assert exec_ctx.available_tools == []
    exec_ctx.available_tools.append("x")
    other_ctx = ExecutionContext(execution_id="exec-2", framework_type=FrameworkType.ADK)
    assert other_ctx.available_tools == []  # ensure no shared list


def test_image_reference_from_base64():
    image = ImageReference.from_base64("ZmFrZQ==", image_format="png", source="test")
    assert image.image_format == "png"
    assert image.metadata["base64_data"] == "ZmFrZQ=="
    assert image.metadata["source"] == "test"
