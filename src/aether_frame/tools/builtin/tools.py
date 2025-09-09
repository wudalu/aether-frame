# -*- coding: utf-8 -*-
"""Builtin Tools Implementation."""

from typing import Dict, Any, Optional
from datetime import datetime
from ...contracts import ToolRequest, ToolResult, ToolStatus
from ..base.tool import Tool


class EchoTool(Tool):
    """
    Simple echo tool for testing and debugging.
    
    Returns the input message back to the caller.
    """
    
    def __init__(self):
        """Initialize echo tool."""
        super().__init__("echo", "builtin")
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """Initialize echo tool."""
        self._initialized = True
    
    async def execute(self, tool_request: ToolRequest) -> ToolResult:
        """
        Execute echo tool.
        
        Args:
            tool_request: Request containing message parameter
            
        Returns:
            ToolResult: Result containing echoed message
        """
        message = tool_request.parameters.get("message", "")
        
        return ToolResult(
            tool_name=self.name,
            tool_namespace=self.namespace,
            status=ToolStatus.SUCCESS,
            result_data={"echo": message},
            created_at=datetime.now()
        )
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get echo tool schema."""
        return {
            "name": "echo",
            "description": "Echo back the input message",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo back"
                    }
                },
                "required": ["message"]
            }
        }
    
    async def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate echo tool parameters."""
        return "message" in parameters and isinstance(parameters["message"], str)
    
    async def cleanup(self):
        """Cleanup echo tool."""
        self._initialized = False


class TimestampTool(Tool):
    """
    Timestamp tool that returns current date and time.
    
    Useful for getting current timestamp information.
    """
    
    def __init__(self):
        """Initialize timestamp tool."""
        super().__init__("timestamp", "builtin")
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """Initialize timestamp tool."""
        self._initialized = True
    
    async def execute(self, tool_request: ToolRequest) -> ToolResult:
        """
        Execute timestamp tool.
        
        Args:
            tool_request: Request (no parameters needed)
            
        Returns:
            ToolResult: Result containing current timestamp
        """
        now = datetime.now()
        format_type = tool_request.parameters.get("format", "iso")
        
        if format_type == "iso":
            timestamp = now.isoformat()
        elif format_type == "unix":
            timestamp = int(now.timestamp())
        elif format_type == "readable":
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp = now.isoformat()
        
        return ToolResult(
            tool_name=self.name,
            tool_namespace=self.namespace,
            status=ToolStatus.SUCCESS,
            result_data={
                "timestamp": timestamp,
                "format": format_type,
                "timezone": str(now.astimezone().tzinfo)
            },
            created_at=now
        )
    
    async def get_schema(self) -> Dict[str, Any]:
        """Get timestamp tool schema."""
        return {
            "name": "timestamp",
            "description": "Get current timestamp",
            "parameters": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["iso", "unix", "readable"],
                        "description": "Timestamp format",
                        "default": "iso"
                    }
                },
                "required": []
            }
        }
    
    async def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate timestamp tool parameters."""
        if "format" in parameters:
            return parameters["format"] in ["iso", "unix", "readable"]
        return True
    
    async def cleanup(self):
        """Cleanup timestamp tool."""
        self._initialized = False