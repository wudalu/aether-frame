# -*- coding: utf-8 -*-
"""Unit tests for UnifiedInteractionLogger context manager."""

import logging
from pathlib import Path

import pytest

from aether_frame.common.interaction_logger import InteractionSession, UnifiedInteractionLogger


def test_unified_interaction_logger_writes_to_file(tmp_path, capsys):
    log_path = tmp_path / "interaction.log"
    logger = UnifiedInteractionLogger(str(log_path))

    logger.log_separator("TEST")
    logger.log_user_request("sess-1", "task-1", "hello")
    logger.log_session_action("created", "sess-1", {"agent": "demo"})
    logger.log_llm_request("model", "provider", [{"role": "user", "content": "hi"}], {"temperature": 0.2})
    logger.log_llm_response("response text", 50.0)
    logger.log_system_action("Do work", {"step": 1})
    logger.log_error("ValidationError", "bad input", {"field": "name"})
    logger.log_performance("run", 123.4, {"iterations": 3})
    logger.log_interaction_complete("sess-1", "task-1", True, {"summary": "ok"})

    # Force flush and inspect file contents
    assert log_path.exists()
    contents = log_path.read_text()
    assert "USER REQUEST" in contents
    assert "LLM RESPONSE" in contents
    assert "INTERACTION ✅ COMPLETED" in contents


def test_logger_additional_branches(tmp_path):
    log_path = tmp_path / "interaction.log"
    logger = UnifiedInteractionLogger(str(log_path))

    # Include agent info and action variants
    logger.log_user_request("sess-2", "task-2", "hello", {"agent_type": "assistant"})
    logger.log_session_action("found", "sess-2", {"reuse": True})
    logger.log_session_action("continued", "sess-2")
    logger.log_llm_response("ok", 42.0, token_usage={"total_tokens": 10})
    logger.log_llm_response("", 10.0, error="boom")
    logger.log_system_action("step", {"detail": "x"})
    logger.log_error("TypeError", "bad", {"field": "name"})
    logger.log_performance("op", 5.0)
    logger.log_interaction_complete("sess-2", "task-2", False)

    contents = log_path.read_text()
    assert "Agent: assistant" in contents
    assert "SESSION FOUND" in contents
    assert "LLM RESPONSE ERROR" in contents
    assert "💥 ERROR" in contents


def test_interaction_session_context_manager(tmp_path):
    log_path = tmp_path / "interaction.log"
    logger = UnifiedInteractionLogger(str(log_path))
    from aether_frame.common.interaction_logger import InteractionSession

    # Successful session
    with InteractionSession("sess-3", "task-3", "hello", {"agent_type": "helper"}):
        logger.log_system_action("processing", {"step": 1})

    # Session with exception to hit error path
    with pytest.raises(RuntimeError):
        with InteractionSession("sess-4", "task-4", "hey") as session:
            raise RuntimeError("fail")
