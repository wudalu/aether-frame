# -*- coding: utf-8 -*-
"""ADK-specific infrastructure adapters.

This module contains ADK framework integration components that bridge
the unified infrastructure layer with ADK's native capabilities:

- adk_memory_adapter.py: ADK context.state integration for memory management
- adk_observer.py: ADK monitoring and observability integration
"""

from .adk_memory_adapter import AdkMemoryAdapter
from .adk_observer import AdkObserver

__all__ = [
    "AdkMemoryAdapter",
    "AdkObserver",
]
