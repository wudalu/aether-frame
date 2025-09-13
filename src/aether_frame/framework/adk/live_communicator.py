# -*- coding: utf-8 -*-
"""ADK Live Communicator Implementation."""

import base64
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ...contracts import InteractionResponse
from ..base.live_communicator import LiveCommunicator

if TYPE_CHECKING:
    # ADK imports for type checking only - actual import handled at runtime
    try:
        from google.adk.runners import LiveRequestQueue
    except ImportError:
        # Fallback for development/testing environments
        LiveRequestQueue = Any


class AdkLiveCommunicator(LiveCommunicator):
    """
    ADK-specific implementation of LiveCommunicator protocol.

    This class provides the concrete implementation for bidirectional
    communication during live execution, using ADK's LiveRequestQueue for
    message passing following ADK's documented patterns.
    """

    def __init__(self, live_request_queue: "LiveRequestQueue"):
        """
        Initialize ADK Live Communicator.

        Args:
            live_request_queue: ADK's LiveRequestQueue instance for
            bidirectional communication
        """
        self._live_request_queue = live_request_queue
        self._closed = False

    async def send_user_response(self, response: InteractionResponse) -> None:
        """
        Send user response to the executing agent through ADK's LiveRequestQueue.

        Based on ADK documentation, we convert InteractionResponse to proper
        ADK Content format and use send_content() method.

        Args:
            response: User's response to an interaction request
        """
        if self._closed:
            raise RuntimeError("Communicator is closed")

        # Import ADK types at runtime
        try:
            from google.genai.types import Content, Part
        except ImportError:
            raise RuntimeError("ADK types not available")

        # For user responses, we send the response as text content
        # Include metadata in the text to preserve interaction context
        response_text = f"User response to {response.interaction_type.value} (ID: {response.interaction_id}): "
        response_text += f"{'Approved' if response.approved else 'Denied'}"

        if response.user_message:
            response_text += f" - {response.user_message}"

        if response.response_data:
            response_text += f" - Additional data: {response.response_data}"

        # Create proper ADK Content
        content = Content(role="user", parts=[Part.from_text(text=response_text)])

        # Send through ADK's LiveRequestQueue using documented method
        self._live_request_queue.send_content(content=content)

    async def send_cancellation(self, reason: str = "user_cancelled") -> None:
        """
        Send cancellation signal to stop execution.

        Args:
            reason: Optional reason for cancellation
        """
        if self._closed:
            raise RuntimeError("Communicator is closed")

        # Import ADK types at runtime
        try:
            from google.genai.types import Content, Part
        except ImportError:
            raise RuntimeError("ADK types not available")

        # Send cancellation as text message to agent
        cancellation_text = f"CANCELLATION_REQUEST: {reason}"
        content = Content(role="user", parts=[Part.from_text(text=cancellation_text)])

        # Send through ADK's LiveRequestQueue
        self._live_request_queue.send_content(content=content)

    async def send_user_message(self, message: str) -> None:
        """
        Send a regular user message during live session.

        Args:
            message: User message to send to the agent
        """
        if self._closed:
            raise RuntimeError("Communicator is closed")

        # Import ADK types at runtime
        try:
            from google.genai.types import Content, Part
        except ImportError:
            raise RuntimeError("ADK types not available")

        # Create proper ADK Content for regular user message
        content = Content(role="user", parts=[Part.from_text(text=message)])

        # Send through ADK's LiveRequestQueue using documented method
        self._live_request_queue.send_content(content=content)

    def close(self) -> None:
        """Close the communication channel and cleanup resources."""
        if not self._closed:
            self._closed = True
            # Use ADK's documented close method
            self._live_request_queue.close()
