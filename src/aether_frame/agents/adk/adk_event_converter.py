# -*- coding: utf-8 -*-
"""ADK Event Conversion Logic for Core Agent Layer."""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from uuid import uuid4

from ...contracts import (
    ContentPart,
    ErrorCode,
    TaskChunkType,
    TaskStreamChunk,
    UniversalMessage,
    build_error,
)
from ...framework.adk.multimodal_utils import (
    decode_base64_image,
    detect_image_mime_type,
    extract_base64_from_data_url,
    validate_image_format,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AdkEventConverter:
    """
    ADK-specific event conversion logic for domain agent layer.

    This class encapsulates ADK framework-specific event handling and conversion
    to framework-agnostic TaskStreamChunk format. It belongs in the Core Agent Layer
    as it handles ADK-specific execution details rather than framework abstraction.

    Architecture Compliance:
    - Framework Abstraction Layer: Provides runtime context, delegates to agents
    - Core Agent Layer (THIS LAYER): Handles ADK-specific event conversion logic
    """

    def __init__(self):
        """Initialize the ADK event converter."""
        # Track in-flight tool interactions so results can reference proposals
        self._pending_tool_interactions: Dict[str, str] = {}
        self._fallback_plan_state: Dict[str, Dict[str, Any]] = {}

    def convert_adk_event_to_chunk(
        self, adk_event: "AdkEvent", task_id: str, sequence_id: int
    ) -> List[TaskStreamChunk]:
        """
        Convert an ADK Event to TaskStreamChunk format.

        This method handles ADK-specific event structure and converts it to
        the framework-agnostic streaming format used by the application.

        Args:
            adk_event: The ADK event to convert
            task_id: The task ID for this execution
            sequence_id: Sequential ID for this chunk

        Returns:
            List[TaskStreamChunk] emitted for this event (empty if filtered)
        """
        try:
            metadata: Dict[str, Any] = self._safe_metadata(adk_event)
            event_type = (
                getattr(adk_event, "event_type", None)
                or metadata.get("event_type")
                or getattr(adk_event, "type", None)
            )
            logger.debug(
                "ADK event received: type=%s author=%s partial=%s finish=%s metadata=%s",
                event_type,
                getattr(adk_event, "author", None),
                getattr(adk_event, "partial", None),
                getattr(getattr(adk_event, "finish_reason", None), "value", getattr(adk_event, "finish_reason", None)),
                metadata or None,
            )

            # Plan streaming comes first so we do not treat plan text as assistant delta
            plan_chunk = self._try_convert_plan_event(
                adk_event, task_id, sequence_id, metadata
            )
            if plan_chunk:
                return [plan_chunk]

            # Handle text content from agent responses
            if (
                hasattr(adk_event, "content")
                and adk_event.content
                and hasattr(adk_event.content, "parts")
                and adk_event.content.parts
                and len(adk_event.content.parts) > 0
            ):

                first_part = adk_event.content.parts[0]

                # Handle tool function call proposals
                if hasattr(first_part, "function_call") and first_part.function_call:
                    proposal_chunk = self._convert_function_call_event(
                        task_id, sequence_id, adk_event, first_part.function_call, metadata
                    )
                    return [proposal_chunk]

                # Handle tool execution responses
                tool_result_chunks = self._try_convert_tool_result(
                    task_id, sequence_id, adk_event, first_part, metadata
                )
                if tool_result_chunks:
                    return tool_result_chunks

                # Handle text responses
                if hasattr(first_part, "text") and first_part.text:
                    # Determine if this is partial or final content
                    is_partial = getattr(adk_event, "partial", False)

                    return [
                        TaskStreamChunk(
                            task_id=task_id,
                            chunk_type=(
                                TaskChunkType.RESPONSE
                                if not is_partial
                                else TaskChunkType.PROGRESS
                            ),
                            sequence_id=sequence_id,
                            content=first_part.text,
                            is_final=not is_partial,
                            metadata={
                                "author": getattr(adk_event, "author", "agent"),
                                "adk_event_id": getattr(adk_event, "id", ""),
                                "turn_complete": getattr(adk_event, "turn_complete", False),
                                "stage": "assistant",
                                **metadata,
                            },
                            chunk_kind="response.delta" if is_partial else "response.final",
                        )
                    ]

            # Handle turn completion and other control signals
            if hasattr(adk_event, "turn_complete") and adk_event.turn_complete:
                self._end_fallback_plan(task_id)
                return [
                    TaskStreamChunk(
                        task_id=task_id,
                        chunk_type=TaskChunkType.COMPLETE,
                        sequence_id=sequence_id,
                        content="Turn completed",
                        is_final=True,
                        metadata={"author": getattr(adk_event, "author", "agent"), "stage": "control"},
                        chunk_kind="turn.complete",
                    )
                ]

            # Handle errors
            if hasattr(adk_event, "error_code") and adk_event.error_code:
                self._end_fallback_plan(task_id)
                return [
                    TaskStreamChunk(
                        task_id=task_id,
                        chunk_type=TaskChunkType.ERROR,
                        sequence_id=sequence_id,
                        content=build_error(
                            ErrorCode.FRAMEWORK_EXECUTION,
                            getattr(adk_event, "error_message", "Unknown error"),
                            source="adk_event",
                            details={"error_code": adk_event.error_code},
                        ).to_dict(),
                        is_final=True,
                        metadata={
                            "error_code": adk_event.error_code,
                            "author": getattr(adk_event, "author", "system"),
                            "stage": "error",
                            **metadata,
                        },
                        chunk_kind="error",
                    )
                ]

            # Filter out events that don't need to be exposed
            return []

        except Exception as e:
            # If event conversion fails, create an error chunk
            self._end_fallback_plan(task_id)
            return [
                TaskStreamChunk(
                    task_id=task_id,
                    chunk_type=TaskChunkType.ERROR,
                    sequence_id=sequence_id,
                    content=build_error(
                        ErrorCode.INTERNAL_ERROR,
                        f"Event conversion error: {str(e)}",
                        source="adk_event_converter",
                        details={"original_event": repr(adk_event)},
                    ).to_dict(),
                    is_final=True,
                    metadata={
                        "error_type": "event_conversion_error",
                        "original_event": str(adk_event) if adk_event else "None",
                        "stage": "error",
                    },
                    chunk_kind="error",
                )
            ]

    def _try_convert_plan_event(
        self,
        adk_event: "AdkEvent",
        task_id: str,
        sequence_id: int,
        metadata: Dict[str, Any],
    ) -> Optional[TaskStreamChunk]:
        """Detect planning events emitted by ADK and convert them to plan chunks."""
        stage_hint = metadata.get("stage") or metadata.get("category")
        event_type = getattr(adk_event, "event_type", None)

        is_plan_delta = stage_hint in {"plan", "plan_delta", "planning"} or event_type in {
            "plan",
            "plan_delta",
            "planning",
        }
        is_plan_summary = stage_hint in {"plan_summary", "plan_result"} or event_type in {
            "plan_summary",
            "plan_result",
        }

        if not (is_plan_delta or is_plan_summary):
            fallback_plan_chunk = self._fallback_plan_event(
                adk_event, task_id, sequence_id, metadata
            )
            if fallback_plan_chunk:
                return fallback_plan_chunk
            return None

        plan_text = metadata.get("plan_text") or getattr(adk_event, "plan", None)
        if not plan_text:
            plan_text = self._extract_first_part_text(adk_event)

        if not plan_text:
            return None

        chunk_type = (
            TaskChunkType.PLAN_SUMMARY if is_plan_summary else TaskChunkType.PLAN_DELTA
        )
        chunk_kind = "plan.summary" if chunk_type == TaskChunkType.PLAN_SUMMARY else "plan.delta"

        staged_metadata = dict(metadata)
        staged_metadata.setdefault("stage", "plan")

        return TaskStreamChunk(
            task_id=task_id,
            chunk_type=chunk_type,
            sequence_id=sequence_id,
            content={"text": plan_text},
            is_final=False,
            metadata=staged_metadata,
            chunk_kind=chunk_kind,
        )

    def _fallback_plan_event(
        self,
        adk_event: "AdkEvent",
        task_id: str,
        sequence_id: int,
        metadata: Dict[str, Any],
    ) -> Optional[TaskStreamChunk]:
        """Best-effort plan detection when ADK metadata lacks explicit plan markers."""
        stage_hint = metadata.get("stage")
        if stage_hint not in (None, "assistant"):
            return None

        text = self._extract_first_part_text(adk_event)
        if not text:
            return None

        normalized = text.strip()
        lower_text = normalized.lower()

        state = self._fallback_plan_state.get(task_id)
        if not state or not state.get("active"):
            if not self._looks_like_plan_start(lower_text):
                return None
            state = {"active": True, "chunk_count": 0}
            self._fallback_plan_state[task_id] = state
        else:
            if state["chunk_count"] >= 512:
                self._end_fallback_plan(task_id)
                return None

        if self._looks_like_plan_end(lower_text):
            self._end_fallback_plan(task_id)
            return None

        chunk_type = TaskChunkType.PLAN_DELTA
        chunk_kind = "plan.delta"
        if lower_text.startswith("plan summary"):
            chunk_type = TaskChunkType.PLAN_SUMMARY
            chunk_kind = "plan.summary"

        staged_metadata = dict(metadata)
        staged_metadata.setdefault("stage", "plan")

        state["chunk_count"] += 1

        chunk = TaskStreamChunk(
            task_id=task_id,
            chunk_type=chunk_type,
            sequence_id=sequence_id,
            content={"text": text},
            is_final=False,
            metadata=staged_metadata,
            chunk_kind=chunk_kind,
        )

        if chunk_type == TaskChunkType.PLAN_SUMMARY:
            self._end_fallback_plan(task_id)

        return chunk

    @staticmethod
    def _looks_like_plan_start(lower_text: str) -> bool:
        if not lower_text:
            return False
        if lower_text.startswith("plan"):
            return True
        return False

    @staticmethod
    def _looks_like_plan_end(lower_text: str) -> bool:
        if not lower_text:
            return False
        endings = (
            "final answer",
            "answer:",
            "based on",
            "final summary",
            "overall summary",
            "in summary",
            "overall",
        )
        return lower_text.startswith(endings)

    def _end_fallback_plan(self, task_id: str) -> None:
        """Stop treating subsequent chunks as plan deltas for the given task."""
        self._fallback_plan_state.pop(task_id, None)

    def _convert_function_call_event(
        self,
        task_id: str,
        sequence_id: int,
        adk_event: "AdkEvent",
        function_call: Any,
        metadata: Dict[str, Any],
    ) -> TaskStreamChunk:
        """Convert ADK function call events into tool proposals."""
        self._end_fallback_plan(task_id)
        tool_name = getattr(function_call, "name", None) or metadata.get("tool_name")
        tool_namespace = metadata.get("tool_namespace")
        tool_short_name = tool_name.split(".")[-1] if isinstance(tool_name, str) else tool_name
        tool_full_name = (
            metadata.get("tool_full_name")
            or (f"{tool_namespace}.{tool_short_name}" if tool_namespace and tool_short_name else tool_name)
            or tool_name
        )
        tool_args = getattr(function_call, "args", None) or metadata.get("tool_args")

        interaction_id = metadata.get("interaction_id") or getattr(function_call, "id", None)
        if not interaction_id:
            interaction_id = f"tool-{uuid4().hex}"

        tool_call_key = self._derive_tool_call_key(adk_event, function_call, interaction_id)
        self._pending_tool_interactions[tool_call_key] = interaction_id

        staged_metadata = dict(metadata)
        staged_metadata.update(
            {
                "author": getattr(adk_event, "author", "agent"),
                "stage": "tool",
                "tool_name": tool_short_name or tool_name,
                "tool_short_name": tool_short_name or tool_name,
                "tool_full_name": tool_full_name,
                "tool_namespace": tool_namespace,
                "requires_approval": staged_metadata.get("requires_approval", True),
            }
        )

        return TaskStreamChunk(
            task_id=task_id,
            chunk_type=TaskChunkType.TOOL_PROPOSAL,
            sequence_id=sequence_id,
            content={
                "tool_name": tool_name,
                "tool_short_name": tool_short_name or tool_name,
                "tool_full_name": tool_full_name,
                "tool_namespace": tool_namespace,
                "arguments": tool_args,
            },
            is_final=False,
            metadata=staged_metadata,
            interaction_id=interaction_id,
            chunk_kind="tool.proposal",
        )

    def _try_convert_tool_result(
        self,
        task_id: str,
        sequence_id: int,
        adk_event: "AdkEvent",
        first_part: Any,
        metadata: Dict[str, Any],
    ) -> List[TaskStreamChunk]:
        """Convert ADK tool result events (function responses)."""
        response_payload = None
        tool_name = metadata.get("tool_name")
        tool_short_name = metadata.get("tool_short_name") or (tool_name.split(".")[-1] if isinstance(tool_name, str) else tool_name)
        tool_namespace = metadata.get("tool_namespace")
        tool_full_name = (
            metadata.get("tool_full_name")
            or (f"{tool_namespace}.{tool_short_name}" if tool_namespace and tool_short_name else tool_name)
            or tool_name
        )
        tool_call_key = metadata.get("tool_call_id")

        if hasattr(first_part, "function_response") and first_part.function_response:
            response_payload = self._normalize_tool_response(first_part.function_response)
            if isinstance(first_part.function_response, dict):
                tool_name = first_part.function_response.get("name") or tool_name
                tool_call_key = first_part.function_response.get("id") or tool_call_key
            else:
                tool_name = getattr(first_part.function_response, "name", tool_name)
                tool_call_key = getattr(first_part.function_response, "id", tool_call_key)
            tool_short_name = tool_name.split(".")[-1] if isinstance(tool_name, str) else tool_name

        # Some ADK implementations track tool output via metadata stage
        stage_hint = metadata.get("stage")
        if not response_payload and stage_hint in {"tool_result", "tool_response"}:
            response_payload = metadata.get("tool_result") or metadata.get("tool_output")

        if not response_payload:
            return []

        if not tool_call_key:
            tool_call_key = self._derive_tool_call_key(adk_event, first_part, tool_name or "")

        interaction_id = self._pending_tool_interactions.pop(tool_call_key, None)

        staged_metadata = dict(metadata)
        staged_metadata.update(
            {
                "author": getattr(adk_event, "author", "system"),
                "stage": "tool",
                "tool_name": tool_short_name or tool_name,
                "tool_short_name": tool_short_name or tool_name,
                "tool_full_name": tool_full_name,
                "tool_namespace": tool_namespace,
            }
        )

        result_chunk = TaskStreamChunk(
            task_id=task_id,
            chunk_type=TaskChunkType.TOOL_RESULT,
            sequence_id=sequence_id,
            content=response_payload,
            is_final=False,
            metadata=staged_metadata,
            interaction_id=interaction_id,
            chunk_kind="tool.result",
        )

        self._end_fallback_plan(task_id)

        if interaction_id is not None:
            return [result_chunk]

        proposal_metadata = dict(metadata)
        proposal_metadata["stage"] = "tool"
        proposal_metadata["author"] = getattr(adk_event, "author", "agent")

        proposal_chunk = TaskStreamChunk(
            task_id=task_id,
            chunk_type=TaskChunkType.TOOL_PROPOSAL,
            sequence_id=sequence_id,
            content={
                "tool_name": tool_name,
                "tool_short_name": tool_short_name,
                "tool_full_name": tool_full_name,
                "tool_namespace": tool_namespace,
                "arguments": metadata.get("tool_args") or {},
            },
            is_final=False,
            metadata=proposal_metadata,
            chunk_kind="tool.proposal",
        )

        synthesized_interaction_id = metadata.get("interaction_id") or tool_call_key or f"tool-{uuid4().hex}"
        proposal_chunk.interaction_id = synthesized_interaction_id
        result_chunk.interaction_id = synthesized_interaction_id

        return [proposal_chunk, result_chunk]

    def _safe_metadata(self, adk_event: "AdkEvent") -> Dict[str, Any]:
        """Return metadata dict for the event without modifying original object."""
        combined: Dict[str, Any] = {}
        for attr_name in ("metadata", "custom_metadata"):
            metadata = getattr(adk_event, attr_name, None)
            if isinstance(metadata, dict):
                combined.update(metadata)
        return combined

    def _extract_first_part_text(self, adk_event: "AdkEvent") -> Optional[str]:
        """Attempt to extract first text part from an ADK event."""
        try:
            parts = getattr(adk_event, "content", None)
            if not parts or not hasattr(parts, "parts") or not parts.parts:
                return None

            first_part = parts.parts[0]
            if hasattr(first_part, "text") and first_part.text:
                return first_part.text
        except Exception:
            return None
        return None

    def _derive_tool_call_key(self, adk_event: "AdkEvent", part: Any, fallback: str) -> str:
        """Derive a stable key used to correlate tool proposals and results."""
        if hasattr(part, "id") and part.id:
            return str(part.id)
        if hasattr(part, "name") and part.name:
            return f"{part.name}"
        if hasattr(adk_event, "id") and adk_event.id:
            return str(adk_event.id)
        return fallback

    def _normalize_tool_response(self, response: Any) -> Any:
        """Normalize ADK function_response payloads to JSON-serialisable structures."""
        if isinstance(response, dict):
            return response.get("result") or response
        result_attr = getattr(response, "result", None)
        if result_attr is not None:
            return result_attr
        # Fall back to string conversion
        return str(response)

    def convert_universal_message_to_adk(self, universal_message: UniversalMessage) -> Optional[dict]:
        """
        Convert UniversalMessage to ADK-compatible message format.
        
        This method handles both text-only and multimodal messages, converting
        base64-encoded images to the format expected by ADK/Gemini models.
        
        Args:
            universal_message: The UniversalMessage to convert
            
        Returns:
            ADK-compatible message dict or None if conversion fails
        """
        try:
            # Handle string content (text-only message)
            if isinstance(universal_message.content, str):
                return {
                    "role": universal_message.role,
                    "parts": [{"text": universal_message.content}]
                }
            
            # Handle multimodal content (list of ContentPart)
            if isinstance(universal_message.content, list):
                adk_parts = []
                
                for content_part in universal_message.content:
                    if isinstance(content_part, ContentPart):
                        # Handle text parts
                        if content_part.text:
                            adk_parts.append({"text": content_part.text})
                        
                        # Handle image parts
                        elif content_part.image_reference:
                            image_part = self._convert_image_reference_to_adk(content_part.image_reference)
                            if image_part:
                                adk_parts.append(image_part)
                            # Note: If image conversion fails, we skip this part but continue
                        
                        # Handle function calls
                        elif content_part.function_call:
                            adk_parts.append({
                                "function_call": {
                                    "name": content_part.function_call.tool_name,
                                    "args": content_part.function_call.parameters
                                }
                            })
                    
                    # Handle direct string content in list
                    elif isinstance(content_part, str):
                        adk_parts.append({"text": content_part})
                
                # Always return a message, even if parts list is empty
                return {
                    "role": universal_message.role,
                    "parts": adk_parts
                }
            
            logger.warning(f"Unable to convert universal message with content type: {type(universal_message.content)}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to convert universal message to ADK format: {str(e)}")
            return None

    def _convert_image_reference_to_adk(self, image_ref) -> Optional[dict]:
        """
        Convert ImageReference to ADK inline_data format.
        
        Args:
            image_ref: ImageReference object with image data
            
        Returns:
            ADK-compatible image part dict or None if conversion fails
        """
        try:
            # Check if image_ref has the required attributes
            if not hasattr(image_ref, 'metadata') or not image_ref.metadata:
                logger.warning("ImageReference missing metadata")
                return None
            
            # Get base64 data from metadata
            base64_data = image_ref.metadata.get('base64_data')
            if not base64_data:
                logger.warning("ImageReference missing base64_data in metadata")
                return None
            
            # Extract MIME type and base64 data
            mime_type, clean_base64 = extract_base64_from_data_url(base64_data)
            
            # Auto-detect MIME type if not provided
            if not mime_type:
                mime_type = detect_image_mime_type(clean_base64)
            
            if not mime_type:
                logger.warning("Could not determine image MIME type")
                return None
            
            # Validate image format
            if not validate_image_format(mime_type):
                logger.warning(f"Unsupported image format: {mime_type}")
                return None
            
            # Decode base64 to bytes
            image_bytes = decode_base64_image(clean_base64)
            if not image_bytes:
                logger.warning("Failed to decode base64 image data")
                return None
            
            # Return ADK-compatible inline_data format
            return {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": image_bytes
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to convert image reference to ADK format: {str(e)}")
            return None

    def convert_universal_messages_to_adk_content(self, messages: List[UniversalMessage]) -> List[dict]:
        """
        Convert a list of UniversalMessage objects to ADK-compatible format.
        
        Args:
            messages: List of UniversalMessage objects
            
        Returns:
            List of ADK-compatible message dicts
        """
        adk_messages = []
        
        for message in messages:
            adk_message = self.convert_universal_message_to_adk(message)
            if adk_message:
                adk_messages.append(adk_message)
            else:
                logger.warning(f"Skipped message due to conversion failure: {message.role}")
        
        return adk_messages

    async def create_mock_live_stream(
        self, task_id: str, content: str = "Mock live response"
    ):
        """
        Create a mock live stream for testing purposes.

        Args:
            task_id: The task ID for this execution
            content: Content for the mock response

        Yields:
            TaskStreamChunk: Mock stream chunks
        """
        # Progress chunk
        yield TaskStreamChunk(
            task_id=task_id,
            chunk_type=TaskChunkType.PROGRESS,
            sequence_id=0,
            content="Processing request...",
            is_final=False,
            metadata={"framework": "adk", "mock": True},
        )

        # Response chunk
        yield TaskStreamChunk(
            task_id=task_id,
            chunk_type=TaskChunkType.RESPONSE,
            sequence_id=1,
            content=content,
            is_final=False,
            metadata={"framework": "adk", "mock": True},
        )

        # Completion chunk
        yield TaskStreamChunk(
            task_id=task_id,
            chunk_type=TaskChunkType.COMPLETE,
            sequence_id=2,
            content="Live execution completed",
            is_final=True,
            metadata={"framework": "adk", "mock": True},
        )
