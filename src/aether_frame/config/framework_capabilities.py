# -*- coding: utf-8 -*-
"""Static framework capability configurations - simplified for core capabilities."""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..contracts import FrameworkType


@dataclass
class FrameworkCapabilityConfig:
    """Simplified framework capability configuration - focus on core capabilities."""

    # Core capabilities - main focus
    async_execution: bool = False  # Framework supports async/sync execution
    memory_management: bool = False  # Framework supports memory/context management
    observability: bool = False  # Framework supports monitoring/logging
    streaming: bool = False  # Framework supports streaming responses

    # Agent execution modes supported
    execution_modes: List[str] = field(
        default_factory=list
    )  # workflow, plan-execution, react, etc.

    # Basic settings with defaults
    default_timeout: int = 300  # Default task timeout in seconds
    max_iterations: int = 20  # Default max iterations

    # Framework-specific extra config
    extra_config: Dict[str, Any] = field(default_factory=dict)

    # Future capabilities (commented for now)
    # tool_integration: bool = True        # Most frameworks support this
    # session_management: bool = False     # Can be derived from memory_management
    # state_persistence: bool = False      # Can be derived from memory_management
    # scalability: str = "medium"          # Can have default values
    # performance: str = "medium"          # Can have default values
    # reliability: str = "medium"          # Can have default values


# Static framework capability configurations - ADK focused
FRAMEWORK_CAPABILITIES: Dict[FrameworkType, FrameworkCapabilityConfig] = {
    FrameworkType.ADK: FrameworkCapabilityConfig(
        # ADK core capabilities
        async_execution=True,  # ADK supports both sync and async
        memory_management=True,  # ADK has context/memory management
        observability=True,  # ADK has built-in monitoring
        streaming=True,  # ADK supports streaming responses
        # ADK execution modes
        execution_modes=[
            "workflow",  # ADK supports workflow orchestration
            "plan-execution",  # ADK supports planning then execution
            "react",  # ADK supports ReAct pattern
        ],
        # ADK settings
        default_timeout=600,  # 10 minutes for complex tasks
        max_iterations=50,  # Higher iterations for complex workflows
        # ADK-specific configuration
        extra_config={
            "default_model": "gemini-1.5-pro",  # FIXME: replace with actual model
            "supports_multimodal": True,
            "supports_function_calling": True,
            "cloud_based": True,
            "authentication_required": True,
        },
    )
    # Future frameworks will be added here:
    # FrameworkType.AUTOGEN: FrameworkCapabilityConfig(...)
    # FrameworkType.LANGGRAPH: FrameworkCapabilityConfig(...)
}


def get_framework_capability_config(
    framework_type: FrameworkType,
) -> FrameworkCapabilityConfig:
    """Get capability configuration for a framework."""
    if framework_type not in FRAMEWORK_CAPABILITIES:
        raise ValueError(
            f"Framework {framework_type} capability configuration not found"
        )

    return FRAMEWORK_CAPABILITIES[framework_type]


def framework_supports_capability(
    framework_type: FrameworkType, capability: str
) -> bool:
    """Check if a framework supports a specific capability."""
    try:
        config = get_framework_capability_config(framework_type)
        return getattr(config, capability, False)
    except (ValueError, AttributeError):
        return False


def framework_supports_execution_mode(framework_type: FrameworkType, mode: str) -> bool:
    """Check if a framework supports a specific execution mode."""
    try:
        config = get_framework_capability_config(framework_type)
        return mode in config.execution_modes
    except ValueError:
        return False
