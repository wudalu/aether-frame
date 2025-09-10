"""Configuration module for Aether Frame."""

from aether_frame.config.settings import Settings
from aether_frame.config.environment import get_environment
from aether_frame.config.logging import setup_logging
from aether_frame.config.routing_config import (
    RoutingConfig, 
    FrameworkCapabilities, 
    ComplexityRouting, 
    TaskTypeMapping
)
from aether_frame.config.framework_capabilities import (
    FrameworkCapabilityConfig,
    get_framework_capability_config,
    framework_supports_capability,
    framework_supports_execution_mode
)

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
    "framework_supports_execution_mode"
]