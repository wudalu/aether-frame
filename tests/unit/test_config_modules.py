# -*- coding: utf-8 -*-
"""Tests for configuration helper modules."""

import logging
import os
from pathlib import Path

import pytest

from aether_frame.config import environment as env
from aether_frame.config import framework_capabilities as fc
from aether_frame.config import logging as log_config
from aether_frame.contracts import FrameworkType


def test_environment_helpers(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert env.get_environment() == "production"
    assert env.is_production() is True
    assert env.is_development() is False
    assert env.is_testing() is False

    monkeypatch.setenv("ENVIRONMENT", "development")
    assert env.is_development() is True

    monkeypatch.setenv("ENVIRONMENT", "test")
    assert env.is_testing() is True

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert env.get_environment() == "development"

    monkeypatch.setenv("REQUIRED_KEY", "value")
    assert env.get_env_var("REQUIRED_KEY") == "value"
    monkeypatch.delenv("REQUIRED_KEY")
    with pytest.raises(ValueError):
        env.require_env_var("REQUIRED_KEY")


def test_framework_capabilities_config():
    config = fc.get_framework_capability_config(FrameworkType.ADK)
    assert config.async_execution is True
    assert fc.framework_supports_capability(FrameworkType.ADK, "streaming") is True
    assert fc.framework_supports_capability(FrameworkType.ADK, "unknown_capability") is False
    assert fc.framework_supports_execution_mode(FrameworkType.ADK, "workflow") is True
    assert fc.framework_supports_execution_mode(FrameworkType.ADK, "unknown") is False

    with pytest.raises(ValueError):
        fc.get_framework_capability_config(FrameworkType.AUTOGEN)


def test_setup_logging_creates_file(tmp_path, capsys):
    log_file = tmp_path / "app.log"
    log_config.setup_logging(level="INFO", log_format="standard", log_file_path=str(log_file))
    log_config.setup_logging(level="DEBUG", log_format="json")

    logger = logging.getLogger("test.config")
    logger.info("hello logging")

    captured = capsys.readouterr().out
    assert "hello logging" in captured
    assert log_file.exists()

    struct_logger = log_config.get_logger("structured")
    struct_logger.info("structured log", extra={"key": "value"})
