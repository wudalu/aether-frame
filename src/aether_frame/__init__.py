# -*- coding: utf-8 -*-
"""
Aether Frame - Multi-Agent Framework Abstraction Layer

A unified abstraction layer for building multi-agent applications
that can seamlessly switch between different agent frameworks (ADK, AutoGen, LangGraph).

Architecture Layers:
- Application Execution Layer: AIAssistant, ExecutionEngine, TaskRouter
- Framework Abstraction Layer: FrameworkRegistry, FrameworkAdapter implementations
- Core Agent Layer: AgentManager, DomainAgent, AgentHooks implementations
- Tool Service Layer: ToolService, Tool implementations
- Infrastructure Layer: Session, Storage, Logging, Monitoring
"""

__version__ = "0.1.0"
__author__ = "Aether Frame Team"
__email__ = "team@aether-frame.dev"

# Core components for public API
from aether_frame.config.settings import Settings
from aether_frame.contracts import TaskRequest, TaskResult
from aether_frame.execution import AIAssistant

__all__ = ["Settings", "AIAssistant", "TaskRequest", "TaskResult", "__version__"]
