"""Configuration module for Aether Frame."""

from aether_frame.config.environment import get_environment
from aether_frame.config.framework_capabilities import (
    FrameworkCapabilityConfig,
    framework_supports_capability,
    framework_supports_execution_mode,
    get_framework_capability_config,
)
from aether_frame.config.logging import setup_logging
from aether_frame.config.routing_config import (
    ComplexityRouting,
    FrameworkCapabilities,
    RoutingConfig,
    TaskTypeMapping,
)
from aether_frame.config.settings import Settings

__all__ = [
    "Settings",
    "get_environment",
    "setup_logging",
    "RoutingConfig",
    "FrameworkCapabilities",
    "ComplexityRouting",
    "TaskTypeMapping",
    "FrameworkCapabilityConfig",
    "get_framework_capability_config",
    "framework_supports_capability",
    "framework_supports_execution_mode",
]
