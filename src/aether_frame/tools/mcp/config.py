# -*- coding: utf-8 -*-
"""MCP server configuration data structure."""

from dataclasses import dataclass, field
from typing import Any, Dict
from urllib.parse import urlparse


@dataclass
class MCPServerConfig:
    """Configuration for MCP server connection.
    
    Simple MCP server configuration following the design document specifications.
    Supports server identification, endpoint configuration, and connection settings.
    
    Attributes:
        name: Server identifier for namespacing (used as tool namespace prefix)
        endpoint: Server endpoint URL (e.g., "http://localhost:8000/mcp")
        headers: Optional HTTP headers for authentication and custom headers
        timeout: Request timeout in seconds (default: 30)
    
    Example:
        >>> config = MCPServerConfig(
        ...     name="local_tools",
        ...     endpoint="http://localhost:8000/mcp",
        ...     headers={"Authorization": "Bearer token"},
        ...     timeout=60
        ... )
        >>> print(config.name)
        "local_tools"
    """
    
    name: str
    endpoint: str
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate_name()
        self._validate_endpoint()
        self._validate_timeout()
    
    def _validate_name(self) -> None:
        """Validate server name field.
        
        Raises:
            ValueError: When name is empty, contains invalid characters,
                       or exceeds maximum length
        """
        if not self.name or not self.name.strip():
            raise ValueError("Server name cannot be empty")
        
        # Remove leading/trailing whitespace
        self.name = self.name.strip()
        
        # Check for invalid characters (only allow alphanumeric, underscore, hyphen)
        if not all(c.isalnum() or c in ("_", "-") for c in self.name):
            raise ValueError(
                "Server name can only contain letters, numbers, underscores, and hyphens"
            )
        
        # Check maximum length (reasonable limit for namespace usage)
        if len(self.name) > 50:
            raise ValueError("Server name cannot exceed 50 characters")
    
    def _validate_endpoint(self) -> None:
        """Validate endpoint URL format.
        
        Raises:
            ValueError: When endpoint is empty, malformed, or uses unsupported scheme
        """
        if not self.endpoint or not self.endpoint.strip():
            raise ValueError("Endpoint cannot be empty")
        
        # Remove leading/trailing whitespace
        self.endpoint = self.endpoint.strip()
        
        try:
            parsed_url = urlparse(self.endpoint)
        except Exception as e:
            raise ValueError(f"Invalid endpoint URL format: {e}")
        
        # Check scheme validity first
        if parsed_url.scheme not in ("http", "https"):
            raise ValueError("Endpoint scheme must be http or https")
        
        # Check for host
        if not parsed_url.netloc:
            raise ValueError("Endpoint must include a host")
    
    def _validate_timeout(self) -> None:
        """Validate timeout value.
        
        Raises:
            ValueError: When timeout is not positive or exceeds maximum limit
        """
        if not isinstance(self.timeout, int):
            raise ValueError("Timeout must be an integer")
        
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        
        # Set reasonable maximum (5 minutes)
        if self.timeout > 300:
            raise ValueError("Timeout cannot exceed 300 seconds")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format.
        
        Returns:
            Dictionary representation of the configuration
        """
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "headers": self.headers.copy(),
            "timeout": self.timeout,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServerConfig":
        """Create configuration from dictionary.
        
        Args:
            data: Dictionary containing configuration data
            
        Returns:
            MCPServerConfig instance
            
        Raises:
            ValueError: When required fields are missing or data is invalid
            TypeError: When data is not a dictionary
        """
        if not isinstance(data, dict):
            raise TypeError("Configuration data must be a dictionary")
        
        # Check required fields
        required_fields = {"name", "endpoint"}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Extract fields with defaults
        name = data["name"]
        endpoint = data["endpoint"]
        headers = data.get("headers", {})
        timeout = data.get("timeout", 30)
        
        # Validate headers type
        if not isinstance(headers, dict):
            raise ValueError("Headers must be a dictionary")
        
        # Validate all header keys and values are strings
        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("All header keys and values must be strings")
        
        return cls(
            name=name,
            endpoint=endpoint,
            headers=headers,
            timeout=timeout
        )