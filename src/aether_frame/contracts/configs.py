# -*- coding: utf-8 -*-
"""Configuration data structures for Aether Frame."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .enums import ExecutionMode, FrameworkType, TaskComplexity


@dataclass
class AgentConfig:
    """Configuration for agent initialization and behavior."""

    agent_type: str
    framework_type: FrameworkType = FrameworkType.ADK

    # Core Agent Identity (ADK Requirements)
    name: Optional[str] = None  # ADK Agent unique identifier
    description: Optional[str] = None  # ADK Agent description for multi-agent scenarios

    # Agent Behavior
    capabilities: List[str] = field(default_factory=list)
    max_iterations: int = 10
    timeout: Optional[int] = None
    model_config: Dict[str, Any] = field(default_factory=dict)
    system_prompt: Optional[str] = None
    behavior_settings: Dict[str, Any] = field(default_factory=dict)
    memory_config: Dict[str, Any] = field(default_factory=dict)
    tool_permissions: List[str] = field(default_factory=list)

    # ADK-Specific Configuration
    include_contents: str = (
        "default"  # ADK conversation history control: 'default', 'none'
    )
    output_schema: Optional[Any] = None  # ADK structured output schema
    input_schema: Optional[Any] = None  # ADK structured input schema
    output_key: Optional[str] = None  # ADK state key for storing output


@dataclass
class ExecutionConfig:
    """Configuration for task execution."""

    execution_mode: ExecutionMode = ExecutionMode.SYNC
    max_retries: int = 3
    timeout: Optional[int] = None
    parallel_execution: bool = False
    enable_logging: bool = True
    enable_monitoring: bool = True
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    error_handling: Dict[str, Any] = field(default_factory=dict)
    performance_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyConfig:
    """Configuration for strategy selection and routing."""

    strategy_name: str
    applicable_task_types: List[str] = field(default_factory=list)
    complexity_levels: List[TaskComplexity] = field(default_factory=list)
    execution_modes: List[ExecutionMode] = field(default_factory=list)
    target_framework: FrameworkType = FrameworkType.ADK
    priority: int = 1
    description: Optional[str] = None
    # Execution strategy details
    agent_type: str = "general"
    agent_config: Dict[str, Any] = field(default_factory=dict)
    runtime_options: Dict[str, Any] = field(default_factory=dict)
