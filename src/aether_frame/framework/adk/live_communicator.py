# -*- coding: utf-8 -*-
"""ADK Live Communicator Implementation."""

import base64
import inspect
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from ...contracts import InteractionResponse
from ..base.live_communicator import LiveCommunicator

if TYPE_CHECKING:
    # ADK imports for type checking only - actual import handled at runtime
    try:
        from google.adk.runners import LiveRequestQueue
    except ImportError:
        # Fallback for development/testing environments
        LiveRequestQueue = Any


class SessionHistoryRecorder:
    """Best-effort helper that mirrors user inputs into the ADK SessionService."""

    def __init__(
        self,
        session_service: Any,
        *,
        app_name: Optional[str],
        user_id: Optional[str],
        session_id: Optional[str],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._session_service = session_service
        self._app_name = app_name
        self._user_id = user_id
        self._session_id = session_id
        self._logger = logger or logging.getLogger(__name__)
        self._session = None

    async def record_user_text(self, text: str) -> None:
        if not text or not self._session_service or not self._app_name or not self._session_id or not self._user_id:
            return

        try:
            if not await self._ensure_session():
                return

            from google.adk.events import Event
            from google.genai import types

            event = Event(
                invocation_id=str(uuid4()),
                author="user",
                content=types.Content(role="user", parts=[types.Part(text=text)]),
                timestamp=datetime.now(timezone.utc),
            )
            append_call = self._session_service.append_event(self._session, event)
            if inspect.isawaitable(append_call):
                await append_call
        except Exception:
            self._logger.debug("Failed to record user message to SessionService", exc_info=True)

    async def _ensure_session(self) -> bool:
        if self._session is not None:
            return True

        try:
            session_call = self._session_service.get_session(
                app_name=self._app_name,
                user_id=self._user_id,
                session_id=self._session_id,
            )
            session_obj = await session_call if inspect.isawaitable(session_call) else session_call
            self._session = session_obj
            if not self._session:
                self._logger.debug("SessionService returned no session for %s", self._session_id)
            return self._session is not None
        except Exception:
            self._logger.debug("Failed to fetch session for history recording", exc_info=True)
            self._session = None
            return False


class AdkLiveCommunicator(LiveCommunicator):
    """
    ADK-specific implementation of LiveCommunicator protocol.

    This class provides the concrete implementation for bidirectional
    communication during live execution, using ADK's LiveRequestQueue for
    message passing following ADK's documented patterns.
    """

    def __init__(
        self,
        live_request_queue: "LiveRequestQueue",
        *,
        history_recorder: Optional[SessionHistoryRecorder] = None,
    ):
        """
        Initialize ADK Live Communicator.

        Args:
            live_request_queue: ADK's LiveRequestQueue instance for
            bidirectional communication
        """
        self._live_request_queue = live_request_queue
        self._closed = False
        self._history_recorder = history_recorder

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
        await self._record_user_text(response_text)

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
        await self._record_user_text(cancellation_text)

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
        await self._record_user_text(message)

    def close(self) -> None:
        """Close the communication channel and cleanup resources."""
        if not self._closed:
            self._closed = True
            # Use ADK's documented close method
            self._live_request_queue.close()

    async def _record_user_text(self, message: str) -> None:
        if self._history_recorder is None:
            return
        try:
            await self._history_recorder.record_user_text(message)
        except Exception:
            # Recording should not block the live flow; log at debug level.
            logging.getLogger(__name__).debug(
                "Failed to mirror user message to session history", exc_info=True
            )
