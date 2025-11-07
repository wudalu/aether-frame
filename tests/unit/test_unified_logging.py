# -*- coding: utf-8 -*-
"""Unit tests for unified logging helpers."""

import logging

from aether_frame.common import unified_logging


def read_log_file(directory):
    files = list(directory.glob("execution_*.log"))
    assert files, "No log files created"
    return files[0].read_text(encoding="utf-8")


def test_unified_logging_config_creates_directory_and_gitignore(tmp_path):
    log_dir = tmp_path / "logs"
    config = unified_logging.UnifiedLoggingConfig(log_base_dir=log_dir)

    assert log_dir.exists()
    gitignore = log_dir / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text()
    assert "*.log" in content

    logger = config.setup_execution_logger("exec-1", enable_console=False)
    assert isinstance(logger, logging.Logger)
    context = config.create_execution_context("exec-2")
    assert context.execution_id == "exec-2"


def test_execution_context_logs_flow_and_writes_file(tmp_path):
    log_dir = tmp_path / "logs"
    config = unified_logging.UnifiedLoggingConfig(log_base_dir=log_dir)
    context = config.create_execution_context("flow-1")

    context.step("Load Data")
    context.log_key_data("Payload", {"items": 2})
    context.log_warning("Potential delay")
    context.log_error("Minor issue", data={"retry": True})
    context.log_success("Completed step")
    context.log_flow_end(success=True, summary_data={"status": "ok"})

    contents = read_log_file(log_dir)
    assert "EXECUTION STARTED" in contents
    assert "STEP 1: Load Data" in contents
    assert "EXECUTION SUCCESS" in contents
    assert '"status": "ok"' in contents
