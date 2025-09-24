"""
Controller layer for Aether Frame.

This module provides HTTP API endpoints that replace the direct AI Assistant usage.
The controller layer handles:
- HTTP request/response processing
- Parameter validation and transformation
- Authentication and authorization
- TaskRequest construction and processing
- Response formatting
"""

from .request_processor import ControllerService
from .api_server import create_app

__all__ = ["ControllerService", "create_app"]