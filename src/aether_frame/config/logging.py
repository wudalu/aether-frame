"""Logging configuration for Aether Frame."""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Optional

import structlog


def setup_logging(
    level: str = "INFO", log_format: str = "json", log_file_path: Optional[str] = None
) -> None:
    """Setup structured logging configuration."""

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.filters.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            (
                structlog.processors.JSONRenderer()
                if log_format == "json"
                else structlog.dev.ConsoleRenderer(colors=True)
            ),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Setup standard logging
    handlers = ["console"]
    if log_file_path:
        handlers.append("file")

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"format": "%(asctime)s %(name)s %(levelname)s %(message)s"},
            "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "json" if log_format == "json" else "standard",
                "stream": sys.stdout,
            }
        },
        "root": {"level": level, "handlers": handlers},
    }

    # Add file handler if specified
    if log_file_path:
        log_dir = Path(log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        logging_config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": level,
            "formatter": "json",
            "filename": log_file_path,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
