"""Environment variable management."""

import os
from typing import Optional


def get_environment() -> str:
    """Get the current environment."""
    return os.getenv("ENVIRONMENT", "development")


def is_development() -> bool:
    """Check if running in development mode."""
    return get_environment().lower() in ("development", "dev")


def is_production() -> bool:
    """Check if running in production mode."""
    return get_environment().lower() in ("production", "prod")


def is_testing() -> bool:
    """Check if running in testing mode."""
    return get_environment().lower() in ("testing", "test")


def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with optional default."""
    return os.getenv(key, default)


def require_env_var(key: str) -> str:
    """Get required environment variable, raise if not found."""
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Required environment variable {key} not found")
    return value
