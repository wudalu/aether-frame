# -*- coding: utf-8 -*-
"""ADK Event Conversion Logic for Core Agent Layer."""

import logging
from typing import TYPE_CHECKING, List, Optional, Union

from ...contracts import TaskChunkType, TaskStreamChunk, UniversalMessage, ContentPart
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
        pass

    def convert_adk_event_to_chunk(
        self, adk_event: "AdkEvent", task_id: str, sequence_id: int
    ) -> Optional[TaskStreamChunk]:
        """
        Convert an ADK Event to TaskStreamChunk format.

        This method handles ADK-specific event structure and converts it to
        the framework-agnostic streaming format used by the application.

        Args:
            adk_event: The ADK event to convert
            task_id: The task ID for this execution
            sequence_id: Sequential ID for this chunk

        Returns:
            TaskStreamChunk if the event should be exposed, None if filtered
        """
        try:
            # Handle text content from agent responses
            if (
                hasattr(adk_event, "content")
                and adk_event.content
                and hasattr(adk_event.content, "parts")
                and adk_event.content.parts
                and len(adk_event.content.parts) > 0
            ):

                first_part = adk_event.content.parts[0]

                # Handle text responses
                if hasattr(first_part, "text") and first_part.text:
                    # Determine if this is partial or final content
                    is_partial = getattr(adk_event, "partial", False)

                    return TaskStreamChunk(
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
                        },
                    )

                # Handle function calls (tool requests)
                if hasattr(first_part, "function_call") and first_part.function_call:
                    return TaskStreamChunk(
                        task_id=task_id,
                        chunk_type=TaskChunkType.TOOL_CALL_REQUEST,
                        sequence_id=sequence_id,
                        content={
                            "function_name": first_part.function_call.name,
                            "arguments": first_part.function_call.args,
                        },
                        is_final=False,
                        metadata={
                            "author": getattr(adk_event, "author", "agent"),
                            "requires_approval": True,  # TODO: Make this configurable
                        },
                    )

            # Handle turn completion and other control signals
            if hasattr(adk_event, "turn_complete") and adk_event.turn_complete:
                return TaskStreamChunk(
                    task_id=task_id,
                    chunk_type=TaskChunkType.COMPLETE,
                    sequence_id=sequence_id,
                    content="Turn completed",
                    is_final=True,
                    metadata={"author": getattr(adk_event, "author", "agent")},
                )

            # Handle errors
            if hasattr(adk_event, "error_code") and adk_event.error_code:
                return TaskStreamChunk(
                    task_id=task_id,
                    chunk_type=TaskChunkType.ERROR,
                    sequence_id=sequence_id,
                    content=getattr(adk_event, "error_message", "Unknown error"),
                    is_final=True,
                    metadata={
                        "error_code": adk_event.error_code,
                        "author": getattr(adk_event, "author", "system"),
                    },
                )

            # Filter out events that don't need to be exposed
            return None

        except Exception as e:
            # If event conversion fails, create an error chunk
            return TaskStreamChunk(
                task_id=task_id,
                chunk_type=TaskChunkType.ERROR,
                sequence_id=sequence_id,
                content=f"Event conversion error: {str(e)}",
                is_final=True,
                metadata={
                    "error_type": "event_conversion_error",
                    "original_event": str(adk_event) if adk_event else "None",
                },
            )

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
