# -*- coding: utf-8 -*-
"""Shared helpers for ADK execution logging and failure metadata."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from ..common.unified_logging import ExecutionContext, create_execution_context
from ..contracts.enums import ErrorCategory

logger = logging.getLogger(__name__)


def initialize_execution_context(
    agent_id: str,
    metadata: Dict[str, Any],
    fallback_key: str,
) -> Optional[ExecutionContext]:
    """
    Create an ExecutionContext for ADK agent runs.

    Args:
        agent_id: Identifier of the current agent
        metadata: Metadata collected prior to execution
        fallback_key: Fallback identifier when metadata lacks execution/task ids
    """
    context_seed = metadata.get("execution_id") or metadata.get("task_id") or fallback_key
    context_id = f"{agent_id}_{context_seed}".replace(" ", "_")

    try:
        exec_context = create_execution_context(context_id)
    except Exception:
        logger.debug("Failed to initialize execution context for %s", context_id, exc_info=True)
        return None

    exec_context.step("ADK_BEFORE_EXECUTION", component="AdkAgentHooks")
    exec_context.log_key_data(
        "ADK agent request metadata",
        metadata,
        component="AdkAgentHooks",
    )
    return exec_context


def log_context_execution_start(
    exec_context: Optional[ExecutionContext],
    data: Dict[str, Any],
    *,
    component: str = "AdkObserver",
) -> None:
    """Emit execution start data to ExecutionContext."""
    if not exec_context:
        return
    exec_context.step("ADK_EXECUTION_START", component=component)
    exec_context.log_key_data(
        "ADK execution start",
        data,
        component=component,
    )


def log_context_execution_complete(
    exec_context: Optional[ExecutionContext],
    data: Dict[str, Any],
    *,
    success: bool,
    component: str = "AdkObserver",
) -> None:
    """Emit execution completion data to ExecutionContext."""
    if not exec_context:
        return
    exec_context.step("ADK_EXECUTION_COMPLETE", component=component)
    exec_context.log_key_data(
        "ADK execution complete",
        data,
        component=component,
    )
    exec_context.log_flow_end(success=success, summary_data=data)


def log_context_execution_error(
    exec_context: Optional[ExecutionContext],
    error: Exception,
    data: Dict[str, Any],
    *,
    component: str = "AdkObserver",
) -> None:
    """Emit execution error data to ExecutionContext."""
    if not exec_context:
        return
    exec_context.step("ADK_EXECUTION_ERROR", component=component)
    exec_context.log_error(
        "ADK execution error",
        error=error,
        data=data,
        component=component,
    )
    exec_context.log_flow_end(success=False, summary_data=data)


def inject_agent_snapshots(agent: Any, metadata: Dict[str, Any]) -> None:
    """Attach cached input/token snapshots from agent to metadata if missing."""
    input_snapshot = getattr(agent, "_last_input_snapshot", None)
    if input_snapshot and "input_preview" not in metadata:
        metadata["input_preview"] = input_snapshot

    token_usage = getattr(agent, "_last_usage_metadata", None)
    if token_usage and "token_usage" not in metadata:
        metadata["token_usage"] = token_usage


def derive_failure_details(error: Exception) -> Dict[str, Any]:
    """Infer failure metadata fields from exception."""
    details: Dict[str, Any] = {}
    failure_reason = getattr(error, "failure_reason", None)
    if not failure_reason:
        failure_reason = type(error).__name__.lower()
    details["failure_reason"] = failure_reason

    error_category_value = getattr(error, "error_category", None)
    if isinstance(error_category_value, ErrorCategory):
        details["error_category"] = error_category_value.value
    elif isinstance(error_category_value, str):
        details["error_category"] = error_category_value
    else:
        details["error_category"] = _map_error_category(error).value

    retriable = getattr(error, "is_retriable", None)
    if retriable is not None:
        details["is_retriable"] = bool(retriable)

    return details


def _map_error_category(error: Exception) -> ErrorCategory:
    """Best-effort mapping from exception type to ErrorCategory."""
    if error.__class__.__name__ == "GeneratorExit":
        return ErrorCategory.STREAM_INTERRUPTED
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return ErrorCategory.SYSTEM
    return ErrorCategory.SYSTEM
