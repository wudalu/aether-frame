# -*- coding: utf-8 -*-
"""ADK Event Conversion Logic for Core Agent Layer."""

from typing import TYPE_CHECKING, Optional

from ...contracts import TaskChunkType, TaskStreamChunk

if TYPE_CHECKING:
    pass


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
