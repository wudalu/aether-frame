# -*- coding: utf-8 -*-
"""Unit tests for ToolResolver name resolution and permissions."""

import pytest

from aether_frame.contracts import UserContext, UserPermissions
from aether_frame.tools.resolver import ToolResolver, ToolNotFoundError


class StubTool:
    def __init__(self, full_name, description="tool", namespace=None, supports_streaming=False, schema=None):
        self.full_name = full_name
        self.description = description
        self.namespace = namespace or full_name.split(".")[0]
        self.name = full_name.split(".")[-1]
        self.parameters_schema = schema or {"type": "object"}
        self.metadata = {}
        self.supports_streaming = supports_streaming


class StubToolService:
    def __init__(self, mapping):
        self.mapping = mapping

    async def get_tools_dict(self, namespace=None):
        if not namespace:
            return dict(self.mapping)
        return {
            name: tool for name, tool in self.mapping.items() if tool.namespace == namespace
        }


@pytest.mark.asyncio
async def test_resolve_tools_supports_exact_and_simplified_names():
    mapping = {
        "builtin.echo": StubTool("builtin.echo"),
        "mcp.search": StubTool("mcp.search"),
    }
    resolver = ToolResolver(StubToolService(mapping))

    tools = await resolver.resolve_tools(["builtin.echo", "search"])

    names = [tool.name for tool in tools]
    assert names == ["builtin.echo", "mcp.search"]


@pytest.mark.asyncio
async def test_resolve_tools_respects_permissions():
    mapping = {
        "mcp.search": StubTool("mcp.search"),
        "builtin.echo": StubTool("builtin.echo"),
    }
    resolver = ToolResolver(StubToolService(mapping))
    user = UserContext(user_id="u1", permissions=UserPermissions(permissions=[]))

    tools = await resolver.resolve_tools(["builtin.echo"], user_context=user)
    assert tools[0].name == "builtin.echo"

    with pytest.raises(ToolNotFoundError):
        await resolver.resolve_tools(["mcp.search"], user_context=user)


@pytest.mark.asyncio
async def test_list_available_tools_filters_namespace_and_permissions():
    mapping = {
        "builtin.echo": StubTool("builtin.echo"),
        "custom.analyze": StubTool("custom.analyze"),
    }
    resolver = ToolResolver(StubToolService(mapping))
    user = UserContext(
        user_id="u2",
        permissions=UserPermissions(permissions=["custom.*"]),
    )

    tools = await resolver.list_available_tools(namespace_filter="custom", user_context=user)

    assert len(tools) == 1
    assert tools[0].name == "custom.analyze"


@pytest.mark.asyncio
async def test_resolve_tools_raises_error_when_not_found():
    mapping = {
        "builtin.echo": StubTool("builtin.echo"),
        "data.search": StubTool("data.search"),
    }
    resolver = ToolResolver(StubToolService(mapping))

    with pytest.raises(ToolNotFoundError):
        await resolver.resolve_tools(["missingtool"])
