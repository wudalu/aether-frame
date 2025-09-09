# -*- coding: utf-8 -*-
"""Tool Service Layer components.

This module provides unified tool execution and management:

- service.py: ToolService unified interface for all tool types
- base/: Abstract tool interfaces and base classes
- builtin/: Built-in system tools
- mcp/: Model Context Protocol integration
- adk_native/: ADK framework native tool wrappers
"""

from .service import ToolService
from .base import Tool

__all__ = [
    "ToolService",
    "Tool",
]