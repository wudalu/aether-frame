import inspect
from typing import Any, Dict
import pytest

from aether_frame.agents.adk.tool_conversion import create_function_tools
from aether_frame.contracts import ToolRequest, ToolResult, UniversalTool
from aether_frame.contracts.enums import ToolStatus


class StubToolService:
    def __init__(self, expected_params):
        self.expected_params = expected_params
        self.captured_request: ToolRequest | None = None

    async def execute_tool(self, request: ToolRequest) -> ToolResult:
        self.captured_request = request
        assert request.parameters == self.expected_params
        return ToolResult(
            tool_name=request.tool_name,
            tool_namespace=request.tool_namespace,
            status=ToolStatus.SUCCESS,
            result_data={"ok": True},
        )


@pytest.mark.asyncio
async def test_object_parameter_schema_pass_through():
    schema = {
        "type": "object",
        "properties": {
            "requestId": {"type": "string", "description": "Unique request identifier"},
            "ticket": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Ticket ID"},
                    "source": {"type": "string", "description": "System source"},
                },
                "required": ["id"],
            },
            "includeHistory": {"type": "boolean", "description": "Whether to include history"},
        },
        "required": ["requestId", "ticket"],
    }

    universal_tool = UniversalTool(
        name="java-mcp.getTicketDetails",
        description="Retrieve ticket details from MCP server",
        namespace="java-mcp",
        parameters_schema=schema,
    )

    params = {
        "requestId": "REQ-123",
        "ticket": {"id": "ALM-42", "source": "ALM"},
        "includeHistory": True,
    }

    stub_service = StubToolService(expected_params=params)

    tools = create_function_tools(
        stub_service,
        [universal_tool],
        request_factory=lambda tool, kwargs: ToolRequest(
            tool_name=tool.name.split(".")[-1],
            tool_namespace=tool.namespace,
            parameters=kwargs,
        ),
    )

    assert len(tools) == 1
    function_tool = tools[0]

    sig = inspect.signature(function_tool.func)
    assert list(sig.parameters.keys()) == ["requestId", "ticket", "includeHistory"]
    ticket_annotation = sig.parameters["ticket"].annotation
    assert ticket_annotation in (dict, Dict[str, Any])

    doc = function_tool.func.__doc__
    assert "requestId (required) [string]" in doc
    assert "ticket (required) [object]" in doc

    result = await function_tool.func(**params)
    assert result["status"] == "success"
    assert stub_service.captured_request is not None
