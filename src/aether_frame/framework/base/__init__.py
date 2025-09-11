# -*- coding: utf-8 -*-
"""Base interfaces for Framework Abstraction Layer.

This module contains abstract base classes that define the contracts
for framework-specific implementations:

- framework_adapter.py: FrameworkAdapter ABC for framework integration
- agent_manager.py: AgentManager interface for agent lifecycle management
"""

from .agent_manager import AgentManager
from .framework_adapter import FrameworkAdapter

__all__ = [
    "FrameworkAdapter",
    "AgentManager",
]
