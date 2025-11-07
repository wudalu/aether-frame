# -*- coding: utf-8 -*-
"""Unit tests for UnifiedInteractionLogger context manager."""

import logging
from pathlib import Path

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
