# -*- coding: utf-8 -*-
"""Routing configuration for task execution strategies."""

from dataclasses import dataclass, field
from typing import Dict, List

from ..contracts import ExecutionMode, FrameworkType, TaskComplexity


@dataclass
class FrameworkCapabilities:
    """Capabilities configuration for a framework."""

    memory_management: bool = False
    observability: bool = False
    tool_integration: bool = False
    session_management: bool = False
    state_persistence: bool = False
    streaming: bool = False
    async_execution: bool = False
    scalability: str = "medium"  # low, medium, high
    performance: str = "medium"  # low, medium, high


@dataclass
class ComplexityRouting:
    """Routing configuration for task complexity levels."""

    preferred_frameworks: List[FrameworkType] = field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.SYNC
    max_iterations: int = 10
    timeout: int = 60
    retry_count: int = 2


@dataclass
class TaskTypeMapping:
    """Task type to framework preferences mapping configuration."""

    preferred_frameworks: List[FrameworkType] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    # Note: agent_type mapping moved to Framework Abstraction Layer


@dataclass
class RoutingConfig:
    """Complete routing configuration."""

    framework_capabilities: Dict[FrameworkType, FrameworkCapabilities] = field(
        default_factory=dict
    )
    complexity_routing: Dict[TaskComplexity, ComplexityRouting] = field(
        default_factory=dict
    )
    task_type_mapping: Dict[str, TaskTypeMapping] = field(default_factory=dict)
    selection_weights: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize default configurations."""
        if not self.framework_capabilities:
            self._init_default_framework_capabilities()

        if not self.complexity_routing:
            self._init_default_complexity_routing()

        if not self.task_type_mapping:
            self._init_default_task_type_mapping()

        if not self.selection_weights:
            self._init_default_selection_weights()

    def _init_default_framework_capabilities(self):
        """Initialize default framework capabilities."""
        self.framework_capabilities = {
            FrameworkType.ADK: FrameworkCapabilities(
                memory_management=True,
                observability=True,
                tool_integration=True,
                session_management=True,
                state_persistence=True,
                streaming=True,
                async_execution=True,
                scalability="high",
                performance="high",
            ),
            FrameworkType.AUTOGEN: FrameworkCapabilities(
                memory_management=False,
                observability=False,
                tool_integration=True,
                session_management=False,
                state_persistence=False,
                streaming=False,
                async_execution=True,
                scalability="medium",
                performance="medium",
            ),
            FrameworkType.LANGGRAPH: FrameworkCapabilities(
                memory_management=True,
                observability=True,
                tool_integration=True,
                session_management=True,
                state_persistence=True,
                streaming=True,
                async_execution=True,
                scalability="high",
                performance="high",
            ),
        }

    def _init_default_complexity_routing(self):
        """Initialize default complexity routing."""
        self.complexity_routing = {
            TaskComplexity.SIMPLE: ComplexityRouting(
                preferred_frameworks=[
                    FrameworkType.ADK, FrameworkType.AUTOGEN
                ],
                execution_mode=ExecutionMode.SYNC,
                max_iterations=5,
                timeout=30,
                retry_count=2,
            ),
            TaskComplexity.MODERATE: ComplexityRouting(
                preferred_frameworks=[
                    FrameworkType.ADK, FrameworkType.LANGGRAPH
                ],
                execution_mode=ExecutionMode.ASYNC,
                max_iterations=10,
                timeout=120,
                retry_count=3,
            ),
            TaskComplexity.COMPLEX: ComplexityRouting(
                preferred_frameworks=[
                    FrameworkType.ADK, FrameworkType.LANGGRAPH
                ],
                execution_mode=ExecutionMode.ASYNC,
                max_iterations=20,
                timeout=300,
                retry_count=3,
            ),
            TaskComplexity.ADVANCED: ComplexityRouting(
                preferred_frameworks=[
                    FrameworkType.ADK, FrameworkType.LANGGRAPH
                ],
                execution_mode=ExecutionMode.STREAMING,
                max_iterations=50,
                timeout=600,
                retry_count=5,
            ),
        }

    def _init_default_task_type_mapping(self):
        """Initialize default task type mapping."""
        self.task_type_mapping = {
            "chat": TaskTypeMapping(
                preferred_frameworks=[FrameworkType.ADK],
                required_capabilities=[
                    "memory_management", "session_management"
                ],
            ),
            "analysis": TaskTypeMapping(
                preferred_frameworks=[
                    FrameworkType.ADK, FrameworkType.LANGGRAPH
                ],
                required_capabilities=[
                    "tool_integration", "state_persistence"
                ],
            ),
            "code": TaskTypeMapping(
                preferred_frameworks=[
                    FrameworkType.ADK, FrameworkType.LANGGRAPH
                ],
                required_capabilities=["tool_integration", "observability"],
            ),
            "research": TaskTypeMapping(
                preferred_frameworks=[
                    FrameworkType.ADK, FrameworkType.LANGGRAPH
                ],
                required_capabilities=[
                    "tool_integration",
                    "memory_management",
                    "state_persistence",
                ],
            ),
            "planning": TaskTypeMapping(
                preferred_frameworks=[
                    FrameworkType.LANGGRAPH, FrameworkType.ADK
                ],
                required_capabilities=[
                    "state_persistence",
                    "memory_management",
                    "async_execution",
                ],
            ),
            "orchestration": TaskTypeMapping(
                preferred_frameworks=[
                    FrameworkType.LANGGRAPH, FrameworkType.ADK
                ],
                required_capabilities=[
                    "async_execution", "streaming", "observability"
                ],
            ),
        }

    def _init_default_selection_weights(self):
        """Initialize default selection weights."""
        self.selection_weights = {
            "capability_match": 0.4,
            "performance": 0.3,
            "reliability": 0.2,
            "resource_usage": 0.1,
        }
