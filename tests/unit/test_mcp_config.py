# -*- coding: utf-8 -*-
"""Tests for MCPServerConfig validation helpers."""

import sys
from types import ModuleType

import pytest


def _install_mcp_stub():
    if "mcp" in sys.modules:
        return
    mcp_module = ModuleType("mcp")
    client_module = ModuleType("mcp.client")
    class DummyClientSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    client_module.ClientSession = DummyClientSession
    mcp_module.ClientSession = DummyClientSession
    stream_module = ModuleType("mcp.client.streamable_http")
    def streamablehttp_client(**kwargs):
        class Dummy:
            async def __aenter__(self):
                return (None, None, None)

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False
        return Dummy()
    stream_module.streamablehttp_client = streamablehttp_client
    sys.modules["mcp"] = mcp_module
    sys.modules["mcp.client"] = client_module
    sys.modules["mcp.client.streamable_http"] = stream_module
    types_module = ModuleType("mcp.types")
    types_module.Tool = object
    sys.modules["mcp.types"] = types_module


_install_mcp_stub()

from aether_frame.tools.mcp.config import MCPServerConfig


def test_mcp_config_to_from_dict_roundtrip():
    config = MCPServerConfig(
        name="local_tools",
        endpoint="https://example.com/mcp",
        headers={"Authorization": "Bearer token"},
        timeout=60,
    )
    data = config.to_dict()
    clone = MCPServerConfig.from_dict(data)
    assert clone.name == "local_tools"
    assert clone.endpoint == "https://example.com/mcp"
    assert clone.timeout == 60


def test_mcp_config_validation_errors():
    with pytest.raises(ValueError):
        MCPServerConfig(name="", endpoint="http://x")

    with pytest.raises(ValueError):
        MCPServerConfig(name="bad name", endpoint="http://x")

    with pytest.raises(ValueError):
        MCPServerConfig(name="good", endpoint="ftp://example.com")

    with pytest.raises(ValueError):
        MCPServerConfig(name="good", endpoint="http://", timeout=10)

    with pytest.raises(ValueError):
        MCPServerConfig(name="good", endpoint="http://example.com", timeout=0)

    with pytest.raises(ValueError):
        MCPServerConfig.from_dict({"endpoint": "http://example.com"})

    with pytest.raises(ValueError):
        MCPServerConfig.from_dict({"name": "good", "endpoint": "http://example.com", "headers": {"X": 1}})

    with pytest.raises(TypeError):
        MCPServerConfig.from_dict("not a dict")
