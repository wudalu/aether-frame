# -*- coding: utf-8 -*-
"""Helpers for converting UniversalTools into ADK FunctionTool objects."""

import inspect
from typing import Any, Callable, Dict, Iterable, List, Optional

from ...contracts import ToolRequest
from ...contracts.enums import ToolStatus


def create_function_tools(
    tool_service: Any,
    universal_tools: Iterable[Any],
    request_factory: Optional[Callable[[Any, Dict[str, Any]], ToolRequest]] = None,
    approval_callback: Optional[Callable[[Any, Dict[str, Any]], Any]] = None,
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
            tool_metadata = getattr(tool, "metadata", {}) or {}
            requires_approval = bool(tool_metadata.get("requires_approval", True))

            async def async_adk_tool(**kwargs):
                if requires_approval and approval_callback:
                    approval_result = await approval_callback(tool, kwargs)
                    if isinstance(approval_result, dict):
                        if not approval_result.get("approved", True):
                            return approval_result
                        approval_metadata = approval_result
                    else:
                        if approval_result is False:
                            return {
                                "status": "cancelled",
                                "error": "Tool invocation cancelled by approval flow",
                                "tool_name": tool.name,
                                "namespace": tool.namespace,
                            }
                        approval_metadata = None
                else:
                    approval_metadata = {"requires_approval": requires_approval}

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
                error_payload = None
                if result:
                    status_value = (
                        result.status.value if hasattr(result.status, "value") else result.status
                    )
                    error_message = result.error_message or error_message
                    if getattr(result, "error", None):
                        try:
                            error_payload = result.error.to_dict()  # type: ignore[attr-defined]
                        except Exception:
                            error_payload = None

                payload = {
                    "status": status_value,
                    "error": error_message,
                    "tool_name": tool.name,
                    "namespace": tool.namespace,
                }
                if error_payload:
                    payload["error_payload"] = error_payload
                if approval_metadata and isinstance(approval_metadata, dict):
                    payload.setdefault("approval_metadata", approval_metadata)
                return payload

            async_adk_tool.__name__ = tool.name.split(".")[-1] if "." in tool.name else tool.name
            async_adk_tool.__doc__ = tool.description or f"Tool: {tool.name}"

            # Derive function signature from tool schema so ADK can expose rich metadata
            schema = getattr(tool, "parameters_schema", {}) or {}
            signature = _build_signature_from_schema(schema)
            if signature:
                async_adk_tool.__signature__ = signature
                async_adk_tool.__doc__ = _augment_doc_with_schema(
                    async_adk_tool.__doc__, schema
                )

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
    enable_streaming: bool = False,
    model_config: Optional[Dict[str, Any]] = None,
) -> Optional[Any]:
    """Create an ADK Agent with the provided configuration and tools."""
    try:
        from google.adk.agents import Agent  # type: ignore
        from ...framework.adk.model_factory import AdkModelFactory
    except ImportError:
        return None

    model = AdkModelFactory.create_model(
        model_identifier,
        settings,
        enable_streaming=enable_streaming,
        model_config=model_config,
    )

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


def _build_signature_from_schema(schema: Dict[str, Any]) -> Optional[inspect.Signature]:
    """Construct an inspect.Signature from a JSON schema-like dictionary."""
    if not isinstance(schema, dict):
        return None

    if schema.get("type") != "object" or "properties" not in schema:
        # Fallback: accept opaque payload
        param = inspect.Parameter(
            "payload",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=Dict[str, Any],
        )
        return inspect.Signature(parameters=[param])

    required_fields = set(schema.get("required", []))
    parameters: List[inspect.Parameter] = []

    for name, prop in schema.get("properties", {}).items():
        annotation = _schema_type_to_python(prop)
        if name in required_fields:
            default = inspect._empty
        else:
            default = prop.get("default", None)
        parameters.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotation,
            )
        )

    if not parameters:
        # No declared properties; allow arbitrary keyword arguments
        return inspect.Signature(
            parameters=[
                inspect.Parameter(
                    "payload",
                    inspect.Parameter.KEYWORD_ONLY,
                    annotation=Dict[str, Any],
                ),
                inspect.Parameter(
                    "kwargs",
                    inspect.Parameter.VAR_KEYWORD,
                ),
            ]
        )

    return inspect.Signature(parameters=parameters)


def _schema_type_to_python(prop_schema: Dict[str, Any]) -> Any:
    """Map JSON schema primitive types to Python hints for documentation."""
    schema_type = prop_schema.get("type")
    if schema_type == "string":
        return str
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return List[_schema_type_to_python(prop_schema.get("items", {}))]  # type: ignore[return-value]
    if schema_type == "object":
        return Dict[str, Any]
    return Any


def _augment_doc_with_schema(doc: Optional[str], schema: Dict[str, Any]) -> str:
    """Append schema field descriptions to the tool docstring."""
    lines: List[str] = []
    if doc:
        lines.append(doc)
    properties = schema.get("properties", {})
    if properties:
        lines.append("\nParameters:")
        required = set(schema.get("required", []))
        for name, prop in properties.items():
            type_name = prop.get("type", "object")
            description = prop.get("description", "")
            required_flag = " (required)" if name in required else ""
            lines.append(f"- {name}{required_flag} [{type_name}]: {description}".rstrip())
    return "\n".join(lines)
