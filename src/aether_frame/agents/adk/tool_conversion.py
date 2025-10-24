# -*- coding: utf-8 -*-
"""Helpers for converting UniversalTools into ADK FunctionTool objects."""

from typing import Any, Callable, Dict, Iterable, List, Optional

from ...contracts import ToolRequest
from ...contracts.enums import ToolStatus


def create_function_tools(
    tool_service: Any,
    universal_tools: Iterable[Any],
    request_factory: Optional[Callable[[Any, Dict[str, Any]], ToolRequest]] = None,
) -> List[Any]:
    """Convert UniversalTool objects into ADK FunctionTool instances."""
    if not tool_service:
        return []

    try:
        from google.adk.tools import FunctionTool  # type: ignore
    except ImportError:
        return []

    adk_tools: List[Any] = []

    for universal_tool in universal_tools:

        def create_async_wrapper(tool):
            async def async_adk_tool(**kwargs):
                tool_request = (
                    request_factory(tool, kwargs)
                    if request_factory
                    else ToolRequest(
                        tool_name=tool.name.split(".")[-1] if "." in tool.name else tool.name,
                        tool_namespace=tool.namespace,
                        parameters=kwargs,
                    )
                )

                result = await tool_service.execute_tool(tool_request)

                if result and result.status == ToolStatus.SUCCESS:
                    return {
                        "status": "success",
                        "result": result.result_data,
                        "tool_name": tool.name,
                        "namespace": tool.namespace,
                        "execution_time": getattr(result, "execution_time", None),
                    }

                status_value = "error"
                error_message = "Tool execution failed"
                if result:
                    status_value = (
                        result.status.value if hasattr(result.status, "value") else result.status
                    )
                    error_message = result.error_message or error_message

                return {
                    "status": status_value,
                    "error": error_message,
                    "tool_name": tool.name,
                    "namespace": tool.namespace,
                }

            async_adk_tool.__name__ = tool.name.split(".")[-1] if "." in tool.name else tool.name
            async_adk_tool.__doc__ = tool.description or f"Tool: {tool.name}"
            return FunctionTool(func=async_adk_tool)

        adk_tools.append(create_async_wrapper(universal_tool))

    return adk_tools


def build_adk_agent(
    *,
    name: str,
    description: str,
    instruction: str,
    model_identifier: str,
    tool_service: Any = None,
    universal_tools: Optional[Iterable[Any]] = None,
    request_factory: Optional[Callable[[Any, Dict[str, Any]], ToolRequest]] = None,
    settings: Any = None,
) -> Optional[Any]:
    """Create an ADK Agent with the provided configuration and tools."""
    try:
        from google.adk.agents import Agent  # type: ignore
        from ...framework.adk.model_factory import AdkModelFactory
    except ImportError:
        return None

    model = AdkModelFactory.create_model(model_identifier, settings)

    tools: List[Any] = []
    if universal_tools:
        tools = create_function_tools(tool_service, universal_tools, request_factory=request_factory)

    return Agent(
        name=name,
        description=description,
        instruction=instruction,
        model=model,
        tools=tools,
    )
