# -*- coding: utf-8 -*-
"""Configuration data structures for Aether Frame."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .enums import ExecutionMode, FrameworkType, TaskComplexity


@dataclass
class AgentConfig:
    """Configuration for agent initialization and behavior - Simplified Core Fields."""

    """
    ADK AgentConfig example:
    adk_agent = AgentConfig(
      agent_type="coding_assistant",
      system_prompt="你是一个编程专家...",
      model_config={"model": "gpt-4", "temperature": 0.3},
      available_tools=["code_executor", "web_search"],
      framework_config={
          # ADK特定配置
          "include_contents": "default",  # ADK对话历史控制
          "output_schema": {"type": "object", "properties": {"code": {"type": "string"}}},
          "memory_settings": {"max_context_length": 4096},
          "adk_agent_id": "coding_agent_v1",
          "vertex_ai_config": {
              "project_id": "my-project",
              "location": "us-central1"
          }
      }
  )
    """

    # === Core Required Fields ===
    agent_type: str  # Agent type identifier (e.g., "coding_assistant", "writing_helper") - REQUIRED
    system_prompt: str  # Agent's system prompt/persona - REQUIRED for meaningful behavior
    
    # === Core Optional Fields (with defaults) ===
    framework_type: FrameworkType = FrameworkType.ADK  # Target framework
    model_config: Dict[str, Any] = field(default_factory=dict)  # LLM model settings
    available_tools: List[str] = field(default_factory=list)  # Tool names this agent can use
    
    # === Optional Identity Fields ===
    name: Optional[str] = None  # Human-readable agent name (can auto-generate from agent_type)
    description: Optional[str] = None  # Agent description for users (can auto-generate from system_prompt)
    
    # === Framework-Specific Configuration ===
    framework_config: Dict[str, Any] = field(default_factory=dict)  # Framework-specific settings


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
