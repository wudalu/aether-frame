# -*- coding: utf-8 -*-
"""Core Agent Layer components.

This module provides the agent management and lifecycle functionality:

- base/: Abstract interfaces for domain agents and hooks
- manager.py: AgentManager implementation for unified agent management
- adk/: ADK-specific domain agent implementations
"""

from .manager import AgentManager
from .base import DomainAgent, AgentHooks
from .adk import AdkDomainAgent, AdkAgentHooks

__all__ = [
    "AgentManager",
    "DomainAgent", 
    "AgentHooks",
    "AdkDomainAgent",
    "AdkAgentHooks",
]