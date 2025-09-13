# -*- coding: utf-8 -*-
"""Base interfaces for Framework Abstraction Layer.

This module contains abstract base classes that define the contracts
for framework-specific implementations:

- framework_adapter.py: FrameworkAdapter ABC for framework integration
- agent_manager.py: DEPRECATED - AgentManager is now a concrete class in agents.manager

Note: AgentManager was moved from abstract interface to concrete implementation
as part of Phase 4 refactoring. There should be only ONE AgentManager instance.
"""

from .framework_adapter import FrameworkAdapter

__all__ = [
    "FrameworkAdapter",
]
