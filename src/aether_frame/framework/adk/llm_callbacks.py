# -*- coding: utf-8 -*-
"""ADK callback helpers for capturing raw LLM requests and responses."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional, Tuple

try:  # Optional dependency at runtime
    from google.adk.agents.callback_context import CallbackContext  # type: ignore
    from google.adk.models.llm_request import LlmRequest  # type: ignore
    from google.adk.models.llm_response import LlmResponse  # type: ignore
except ImportError:  # pragma: no cover - ADK not installed in some environments
    CallbackContext = Any  # type: ignore
    LlmRequest = Any  # type: ignore
    LlmResponse = Any  # type: ignore

from ...contracts.requests import TaskRequest  # Imported for type checking/metadata extraction

logger = logging.getLogger("aether_frame.adk.llm_capture")

# Key used to stash per-invocation metadata on the callback context state.
CAPTURE_STATE_KEY = "aether_frame_llm_capture"

BeforeModelCallback = Callable[[CallbackContext, LlmRequest], Optional[LlmResponse]]


def build_llm_capture_callbacks(
    domain_agent: Any,
) -> Tuple[Any, Any, Any]:
    """
    Build ADK callback functions bound to the given domain agent.

    Returns:
        Tuple containing (before_agent_callback, before_model_callback, after_model_callback)

    Notes:
        The returned callbacks are intended to be passed straight into ``google.adk.agents.Agent``.
        * ``before_agent_callback`` runs once per invocation; we use it to push session metadata
          into ``CallbackContext.state`` so later callbacks can reuse it.
        * ``before_model_callback`` / ``after_model_callback`` run around every LLM call. Here we
          capture the raw request / response (prior to any transformation) and emit a structured log.
        This function is the primary integration point if the team wants to route events elsewhere.
    """

    def before_agent_callback(ctx: CallbackContext) -> None:
        metadata = _extract_metadata(domain_agent)
        if metadata:
            try:
                ctx.state[CAPTURE_STATE_KEY] = metadata
            except Exception:
                logger.debug("Failed to stash LLM capture metadata on callback context.", exc_info=True)

    def before_model_callback(
        ctx: CallbackContext,
        llm_request: LlmRequest,
    ) -> Optional[LlmResponse]:
        metadata = _metadata_with_context(ctx)
        payload = _safe_model_dump(llm_request)
        _emit_record("request", metadata, payload)
        return None

    def after_model_callback(
        ctx: CallbackContext,
        llm_response: LlmResponse,
    ) -> Optional[LlmResponse]:
        metadata = _metadata_with_context(ctx)
        payload = _safe_model_dump(llm_response)
        _emit_record("response", metadata, payload)
        return None

    return before_agent_callback, before_model_callback, after_model_callback


def _extract_metadata(domain_agent: Any) -> Dict[str, Any]:
    """Gather stable metadata from the domain agent's current task context."""
    task_request: Optional[TaskRequest] = getattr(domain_agent, "_active_task_request", None)
    runtime_context: Dict[str, Any] = getattr(domain_agent, "runtime_context", {})

    session_id = None
    user_id = None
    task_id = None

    if task_request:
        session_id = task_request.session_id or (
            task_request.session_context.get_adk_session_id()
            if getattr(task_request, "session_context", None)
            else None
        )
        task_id = task_request.task_id
        if getattr(task_request, "user_context", None):
            try:
                user_id = task_request.user_context.get_adk_user_id()
            except Exception:  # pragma: no cover - very defensive
                user_id = getattr(task_request.user_context, "user_id", None)

    session_id = session_id or runtime_context.get("session_id")
    user_id = user_id or runtime_context.get("user_id")

    metadata = {
        "agent_id": getattr(domain_agent, "agent_id", None),
        "task_id": task_id,
        "session_id": session_id,
        "user_id": user_id,
    }

    # Drop keys whose values are falsy to keep logs lean
    return {key: value for key, value in metadata.items() if value}


def _metadata_with_context(ctx: CallbackContext) -> Dict[str, Any]:
    """Merge stored metadata with runtime details from the callback context."""
    context_meta: Dict[str, Any] = {}
    try:
        state_meta = ctx.state.get(CAPTURE_STATE_KEY, {})
        if isinstance(state_meta, dict):
            context_meta.update(state_meta)
    except Exception:  # pragma: no cover - defensive
        logger.debug("Failed to read capture metadata from callback context state.", exc_info=True)

    context_meta.setdefault("invocation_id", getattr(ctx, "invocation_id", None))
    context_meta.setdefault("agent_name", getattr(ctx, "agent_name", None))
    return {k: v for k, v in context_meta.items() if v is not None}


def _safe_model_dump(model: Any) -> Any:
    """Safely dump pydantic models (LLM request/response) to JSON-compatible data."""
    if hasattr(model, "model_dump"):
        try:
            return model.model_dump(mode="json")
        except Exception:  # pragma: no cover
            logger.debug("Failed to dump model via model_dump; falling back to string.", exc_info=True)
    return json.loads(json.dumps(model, default=str))


def _emit_record(record_type: str, metadata: Dict[str, Any], payload: Any) -> None:
    """Emit a structured log record for the captured payload."""
    log_data = {
        "type": record_type,
        "metadata": metadata,
        "payload": payload,
    }
    logger.info("Captured ADK LLM %s", record_type, extra={"aether_frame": log_data})
    # If future consumers need to forward data to MQ / telemetry buses, this function is
    # the single choke point to extend. For example:
    #     mq_publisher.publish(log_data)
    # Keep the call non-blocking and swallow exceptions to avoid perturbing the request path.


def chain_before_model_callbacks(*callbacks: Optional[BeforeModelCallback]) -> Optional[BeforeModelCallback]:
    """Chain multiple before_model callbacks while preserving ADK short-circuit semantics."""
    valid_callbacks = [cb for cb in callbacks if cb]
    if not valid_callbacks:
        return None

    def _chained_callback(ctx: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
        for callback in valid_callbacks:
            result = callback(ctx, llm_request)
            if result is not None:
                return result
        return None

    return _chained_callback


def build_identity_strip_callback(domain_agent: Any) -> BeforeModelCallback:
    """Return a callback that strips ADK identity boilerplate from system instructions."""

    def _strip_identity(_: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
        _strip_adk_identity(domain_agent, llm_request)
        return None

    return _strip_identity


def _strip_adk_identity(domain_agent: Any, llm_request: LlmRequest) -> None:
    """Remove ADK-injected identity lines from the LLM system instructions."""
    config = getattr(llm_request, "config", None)
    if not config or not getattr(config, "system_instruction", None):
        return

    agent = getattr(domain_agent, "adk_agent", None)
    agent_name = getattr(agent, "name", None) or getattr(domain_agent, "agent_id", None)
    agent_description = getattr(agent, "description", None) or (
        domain_agent.config.get("description") if isinstance(domain_agent.config, dict) else None
    )

    patterns = []
    if agent_name:
        name_line = f'You are an agent. Your internal name is "{agent_name}".'
        patterns.append(name_line)
        if agent_description:
            description_line = f' The description about you is "{agent_description}"'
            patterns.insert(0, f"{name_line}\n\n{description_line}")
            patterns.append(description_line)
    else:
        name_line = None

    instruction = config.system_instruction
    updated_instruction = instruction
    for pattern in patterns:
        updated_instruction = updated_instruction.replace(pattern, "") if pattern else updated_instruction

    if updated_instruction == instruction:
        return

    sanitized_parts = [segment.strip() for segment in updated_instruction.split("\n\n") if segment.strip()]
    config.system_instruction = "\n\n".join(sanitized_parts)
