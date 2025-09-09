# -*- coding: utf-8 -*-
"""Framework Abstraction Layer for Aether Frame.

This module provides unified interfaces for multiple agent frameworks
with framework-specific implementations:

- base/: Abstract base classes and interfaces
- framework_registry.py: Framework adapter registry and management
- adk/: Google Cloud Agent Development Kit implementation
- autogen/: Microsoft AutoGen implementation (future)
- langgraph/: LangChain LangGraph implementation (future)
"""

from .base import FrameworkAdapter, AgentManager
from .framework_registry import FrameworkRegistry
from .adk import AdkFrameworkAdapter

__all__ = [
    # Base interfaces
    "FrameworkAdapter",
    "AgentManager",
    
    # Registry
    "FrameworkRegistry",
    
    # ADK implementation
    "AdkFrameworkAdapter",
]