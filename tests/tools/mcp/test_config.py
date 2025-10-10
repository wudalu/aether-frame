# -*- coding: utf-8 -*-
"""Test suite for MCPServerConfig data structure."""

import pytest
from typing import Any, Dict

from aether_frame.tools.mcp.config import MCPServerConfig


class TestMCPServerConfigValidation:
    """Test configuration validation and error handling."""
    
    def test_valid_basic_config(self) -> None:
        """Test creation of valid basic configuration."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        
        assert config.name == "test_server"
        assert config.endpoint == "http://localhost:8000/mcp"
        assert config.headers == {}
        assert config.timeout == 30
    
    def test_valid_full_config(self) -> None:
        """Test creation of configuration with all fields."""
        headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        
        config = MCPServerConfig(
            name="production_server",
            endpoint="https://api.example.com/mcp",
            headers=headers,
            timeout=60
        )
        
        assert config.name == "production_server"
        assert config.endpoint == "https://api.example.com/mcp"
        assert config.headers == headers
        assert config.timeout == 60
    
    def test_name_validation_empty_name(self) -> None:
        """Test validation fails for empty name."""
        with pytest.raises(ValueError, match="Server name cannot be empty"):
            MCPServerConfig(name="", endpoint="http://localhost:8000/mcp")
    
    def test_name_validation_whitespace_only(self) -> None:
        """Test validation fails for whitespace-only name."""
        with pytest.raises(ValueError, match="Server name cannot be empty"):
            MCPServerConfig(name="   ", endpoint="http://localhost:8000/mcp")
    
    def test_name_validation_strips_whitespace(self) -> None:
        """Test name whitespace is stripped during validation."""
        config = MCPServerConfig(
            name="  test_server  ",
            endpoint="http://localhost:8000/mcp"
        )
        assert config.name == "test_server"
    
    def test_name_validation_invalid_characters(self) -> None:
        """Test validation fails for names with invalid characters."""
        invalid_names = ["test@server", "test.server", "test server", "test/server"]
        
        for invalid_name in invalid_names:
            with pytest.raises(
                ValueError, 
                match="Server name can only contain letters, numbers, underscores, and hyphens"
            ):
                MCPServerConfig(name=invalid_name, endpoint="http://localhost:8000/mcp")
    
    def test_name_validation_valid_characters(self) -> None:
        """Test validation passes for names with valid characters."""
        valid_names = ["test_server", "test-server", "TestServer123", "server_123-prod"]
        
        for valid_name in valid_names:
            config = MCPServerConfig(name=valid_name, endpoint="http://localhost:8000/mcp")
            assert config.name == valid_name
    
    def test_name_validation_max_length(self) -> None:
        """Test validation fails for names exceeding maximum length."""
        long_name = "a" * 51  # 51 characters
        
        with pytest.raises(ValueError, match="Server name cannot exceed 50 characters"):
            MCPServerConfig(name=long_name, endpoint="http://localhost:8000/mcp")
    
    def test_endpoint_validation_empty_endpoint(self) -> None:
        """Test validation fails for empty endpoint."""
        with pytest.raises(ValueError, match="Endpoint cannot be empty"):
            MCPServerConfig(name="test", endpoint="")
    
    def test_endpoint_validation_whitespace_only(self) -> None:
        """Test validation fails for whitespace-only endpoint."""
        with pytest.raises(ValueError, match="Endpoint cannot be empty"):
            MCPServerConfig(name="test", endpoint="   ")
    
    def test_endpoint_validation_strips_whitespace(self) -> None:
        """Test endpoint whitespace is stripped during validation."""
        config = MCPServerConfig(
            name="test",
            endpoint="  http://localhost:8000/mcp  "
        )
        assert config.endpoint == "http://localhost:8000/mcp"
    
    def test_endpoint_validation_missing_scheme(self) -> None:
        """Test validation fails for endpoints without scheme."""
        with pytest.raises(ValueError, match="Endpoint scheme must be http or https"):
            MCPServerConfig(name="test", endpoint="localhost:8000/mcp")
    
    def test_endpoint_validation_invalid_scheme(self) -> None:
        """Test validation fails for unsupported schemes."""
        invalid_schemes = ["ftp://localhost:8000/mcp", "ws://localhost:8000/mcp"]
        
        for invalid_endpoint in invalid_schemes:
            with pytest.raises(ValueError, match="Endpoint scheme must be http or https"):
                MCPServerConfig(name="test", endpoint=invalid_endpoint)
    
    def test_endpoint_validation_missing_host(self) -> None:
        """Test validation fails for endpoints without host."""
        with pytest.raises(ValueError, match="Endpoint must include a host"):
            MCPServerConfig(name="test", endpoint="http:///mcp")
    
    def test_endpoint_validation_valid_formats(self) -> None:
        """Test validation passes for valid endpoint formats."""
        valid_endpoints = [
            "http://localhost:8000/mcp",
            "https://api.example.com/mcp",
            "http://127.0.0.1:3000",
            "https://subdomain.example.org:8080/api/mcp"
        ]
        
        for valid_endpoint in valid_endpoints:
            config = MCPServerConfig(name="test", endpoint=valid_endpoint)
            assert config.endpoint == valid_endpoint
    
    def test_timeout_validation_negative_timeout(self) -> None:
        """Test validation fails for negative timeout."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            MCPServerConfig(
                name="test",
                endpoint="http://localhost:8000/mcp",
                timeout=-1
            )
    
    def test_timeout_validation_zero_timeout(self) -> None:
        """Test validation fails for zero timeout."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            MCPServerConfig(
                name="test",
                endpoint="http://localhost:8000/mcp",
                timeout=0
            )
    
    def test_timeout_validation_excessive_timeout(self) -> None:
        """Test validation fails for timeout exceeding maximum."""
        with pytest.raises(ValueError, match="Timeout cannot exceed 300 seconds"):
            MCPServerConfig(
                name="test",
                endpoint="http://localhost:8000/mcp",
                timeout=301
            )
    
    def test_timeout_validation_non_integer(self) -> None:
        """Test validation fails for non-integer timeout."""
        with pytest.raises(ValueError, match="Timeout must be an integer"):
            MCPServerConfig(
                name="test",
                endpoint="http://localhost:8000/mcp",
                timeout=30.5  # type: ignore
            )


class TestMCPServerConfigSerialization:
    """Test configuration serialization and deserialization."""
    
    def test_to_dict_basic(self) -> None:
        """Test conversion to dictionary format."""
        config = MCPServerConfig(
            name="test_server",
            endpoint="http://localhost:8000/mcp"
        )
        
        result = config.to_dict()
        expected = {
            "name": "test_server",
            "endpoint": "http://localhost:8000/mcp",
            "headers": {},
            "timeout": 30
        }
        
        assert result == expected
    
    def test_to_dict_full(self) -> None:
        """Test conversion to dictionary with all fields."""
        headers = {"Authorization": "Bearer token"}
        config = MCPServerConfig(
            name="prod_server",
            endpoint="https://api.example.com/mcp",
            headers=headers,
            timeout=60
        )
        
        result = config.to_dict()
        expected = {
            "name": "prod_server",
            "endpoint": "https://api.example.com/mcp",
            "headers": headers,
            "timeout": 60
        }
        
        assert result == expected
    
    def test_to_dict_headers_copy(self) -> None:
        """Test that to_dict returns a copy of headers."""
        original_headers = {"Authorization": "Bearer token"}
        config = MCPServerConfig(
            name="test",
            endpoint="http://localhost:8000/mcp",
            headers=original_headers
        )
        
        result_dict = config.to_dict()
        result_dict["headers"]["New-Header"] = "value"
        
        # Original headers should not be modified
        assert "New-Header" not in config.headers
        assert "New-Header" not in original_headers
    
    def test_from_dict_basic(self) -> None:
        """Test creation from dictionary with required fields only."""
        data = {
            "name": "test_server",
            "endpoint": "http://localhost:8000/mcp"
        }
        
        config = MCPServerConfig.from_dict(data)
        
        assert config.name == "test_server"
        assert config.endpoint == "http://localhost:8000/mcp"
        assert config.headers == {}
        assert config.timeout == 30
    
    def test_from_dict_full(self) -> None:
        """Test creation from dictionary with all fields."""
        data = {
            "name": "prod_server",
            "endpoint": "https://api.example.com/mcp",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 60
        }
        
        config = MCPServerConfig.from_dict(data)
        
        assert config.name == "prod_server"
        assert config.endpoint == "https://api.example.com/mcp"
        assert config.headers == {"Authorization": "Bearer token"}
        assert config.timeout == 60
    
    def test_from_dict_missing_required_field(self) -> None:
        """Test from_dict fails when required fields are missing."""
        # Missing name
        data_missing_name = {"endpoint": "http://localhost:8000/mcp"}
        with pytest.raises(ValueError, match="Missing required fields: name"):
            MCPServerConfig.from_dict(data_missing_name)
        
        # Missing endpoint
        data_missing_endpoint = {"name": "test"}
        with pytest.raises(ValueError, match="Missing required fields: endpoint"):
            MCPServerConfig.from_dict(data_missing_endpoint)
        
        # Missing both
        data_missing_both = {}
        with pytest.raises(ValueError, match="Missing required fields:"):
            MCPServerConfig.from_dict(data_missing_both)
    
    def test_from_dict_invalid_data_type(self) -> None:
        """Test from_dict fails for non-dictionary input."""
        with pytest.raises(TypeError, match="Configuration data must be a dictionary"):
            MCPServerConfig.from_dict("not a dict")  # type: ignore
    
    def test_from_dict_invalid_headers_type(self) -> None:
        """Test from_dict fails for non-dictionary headers."""
        data = {
            "name": "test",
            "endpoint": "http://localhost:8000/mcp",
            "headers": "not a dict"
        }
        
        with pytest.raises(ValueError, match="Headers must be a dictionary"):
            MCPServerConfig.from_dict(data)
    
    def test_from_dict_invalid_header_values(self) -> None:
        """Test from_dict fails for non-string header keys or values."""
        # Non-string key
        data_invalid_key = {
            "name": "test",
            "endpoint": "http://localhost:8000/mcp",
            "headers": {123: "value"}
        }
        
        with pytest.raises(ValueError, match="All header keys and values must be strings"):
            MCPServerConfig.from_dict(data_invalid_key)
        
        # Non-string value
        data_invalid_value = {
            "name": "test",
            "endpoint": "http://localhost:8000/mcp",
            "headers": {"key": 123}
        }
        
        with pytest.raises(ValueError, match="All header keys and values must be strings"):
            MCPServerConfig.from_dict(data_invalid_value)
    
    def test_roundtrip_serialization(self) -> None:
        """Test that to_dict and from_dict are inverse operations."""
        original_config = MCPServerConfig(
            name="roundtrip_test",
            endpoint="https://api.example.com/mcp",
            headers={"Authorization": "Bearer token", "Content-Type": "application/json"},
            timeout=90
        )
        
        # Convert to dict and back
        config_dict = original_config.to_dict()
        restored_config = MCPServerConfig.from_dict(config_dict)
        
        # Should be identical
        assert restored_config.name == original_config.name
        assert restored_config.endpoint == original_config.endpoint
        assert restored_config.headers == original_config.headers
        assert restored_config.timeout == original_config.timeout


class TestMCPServerConfigEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_headers_mutability(self) -> None:
        """Test that headers can be modified after creation."""
        config = MCPServerConfig(
            name="test",
            endpoint="http://localhost:8000/mcp"
        )
        
        # Should be able to add headers
        config.headers["Authorization"] = "Bearer token"
        assert config.headers["Authorization"] == "Bearer token"
    
    def test_name_boundary_length(self) -> None:
        """Test name at maximum allowed length."""
        max_length_name = "a" * 50  # Exactly 50 characters
        
        config = MCPServerConfig(
            name=max_length_name,
            endpoint="http://localhost:8000/mcp"
        )
        
        assert config.name == max_length_name
        assert len(config.name) == 50
    
    def test_timeout_boundary_values(self) -> None:
        """Test timeout at boundary values."""
        # Minimum valid timeout
        config_min = MCPServerConfig(
            name="test",
            endpoint="http://localhost:8000/mcp",
            timeout=1
        )
        assert config_min.timeout == 1
        
        # Maximum valid timeout
        config_max = MCPServerConfig(
            name="test",
            endpoint="http://localhost:8000/mcp",
            timeout=300
        )
        assert config_max.timeout == 300