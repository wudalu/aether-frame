# -*- coding: utf-8 -*-
"""Core Agent Layer components.

This module provides the agent management and lifecycle functionality:

- base/: Abstract interfaces for domain agents and hooks
- manager.py: AgentManager implementation for unified agent management
- adk/: ADK-specific domain agent implementations
"""

from .adk import AdkAgentHooks, AdkDomainAgent
from .base import AgentHooks, DomainAgent
from .manager import AgentManager

__all__ = [
    "AgentManager",
    "DomainAgent",
    "AgentHooks",
    "AdkDomainAgent",
    "AdkAgentHooks",
]
