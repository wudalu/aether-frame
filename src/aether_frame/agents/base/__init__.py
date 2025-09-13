# -*- coding: utf-8 -*-
"""Abstract base classes for Core Agent Layer.

This module contains abstract interfaces that define the contracts
for agent implementations across different frameworks:

- domain_agent.py: DomainAgent ABC for framework-specific agent implementations
- agent_hooks.py: AgentHooks interface for framework-specific extensions
"""

from .agent_hooks import AgentHooks
from .domain_agent import DomainAgent

__all__ = [
    "DomainAgent",
    "AgentHooks",
]
