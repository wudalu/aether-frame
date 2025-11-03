# -*- coding: utf-8 -*-
"""High-level stream session wrapper for framework live execution."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from ..contracts import InteractionResponse, InteractionType, TaskStreamChunk
from ..framework.base.live_communicator import LiveCommunicator


@dataclass
class PendingInteraction:
    """Structured view of a pending approval interaction."""

    interaction_id: str
    tool_name: Optional[str]
    created_at_iso: str
    expires_at_iso: Optional[str]
    requires_approval: bool
    metadata: Dict[str, Any]


class StreamSession:
    """
    Wrapper around the live execution tuple returned by framework adapters.

    Provides a user-friendly API for upstream services to send user events and
    inspect approval state without depending on framework-specific classes.
    """

    def __init__(
        self,
        task_id: str,
        event_stream: AsyncIterator[TaskStreamChunk],
        communicator: LiveCommunicator,
    ) -> None:
        self._logger = logging.getLogger(f"{__name__}.{task_id}")
        self._task_id = task_id
        self._event_stream = event_stream
        self._communicator = communicator
        self._closed = False
        self._close_lock = asyncio.Lock()
        self._logger.info("Stream session created", extra={"task_id": task_id})

    # ------------------------------------------------------------------
    # Async iteration
    # ------------------------------------------------------------------
    def __aiter__(self) -> AsyncIterator[TaskStreamChunk]:
        return self._event_stream

    @property
    def task_id(self) -> str:
        return self._task_id

    # ------------------------------------------------------------------
    # Communicator passthrough helpers
    # ------------------------------------------------------------------
    async def send_user_message(self, message: str) -> None:
        self._logger.info(
            "Forwarding user message",
            extra={"task_id": self._task_id, "message_length": len(message)},
        )
        await self._communicator.send_user_message(message)

    async def send_interaction_response(self, response: InteractionResponse) -> None:
        self._logger.info(
            "Forwarding interaction response",
            extra={
                "task_id": self._task_id,
                "interaction_id": response.interaction_id,
                "interaction_type": response.interaction_type.value,
                "approved": response.approved,
            },
        )
        await self._communicator.send_user_response(response)

    async def approve_tool(
        self,
        interaction_id: str,
        *,
        approved: bool,
        user_message: Optional[str] = None,
        response_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Convenience helper to submit a tool approval/denial."""
        self._logger.info(
            "Submitting tool approval decision",
            extra={
                "task_id": self._task_id,
                "interaction_id": interaction_id,
                "approved": approved,
            },
        )
        await self.send_interaction_response(
            InteractionResponse(
                interaction_id=interaction_id,
                interaction_type=InteractionType.TOOL_APPROVAL,
                approved=approved,
                user_message=user_message,
                response_data=response_data,
                metadata=metadata or {},
            )
        )

    async def cancel(self, reason: str = "user_cancelled") -> None:
        self._logger.info(
            "Cancelling stream session",
            extra={"task_id": self._task_id, "reason": reason},
        )
        await self._communicator.send_cancellation(reason)

    async def close(self) -> None:
        """
        Close the session gracefully.

        This will attempt to close the communicator and underlying stream if it
        exposes an ``aclose`` coroutine.
        """
        async with self._close_lock:
            if self._closed:
                return
            self._closed = True

            broker = getattr(self._communicator, "broker", None)
            if broker is not None:
                self._logger.info(
                    "Closing approval broker", extra={"task_id": self._task_id}
                )
                broker.close()

            try:
                self._communicator.close()
            except Exception:
                # Communicators are best effort during shutdown
                pass

            aclose = getattr(self._event_stream, "aclose", None)
            if callable(aclose):
                try:
                    await aclose()
                except Exception:
                    pass
            self._logger.info("Stream session closed", extra={"task_id": self._task_id})

    # ------------------------------------------------------------------
    # Approval inspection helpers
    # ------------------------------------------------------------------
    async def list_pending_interactions(self) -> List[PendingInteraction]:
        """Return a snapshot of pending approvals if the communicator exposes a broker."""
        broker = getattr(self._communicator, "broker", None)
        if broker is None:
            return []

        inspector = getattr(broker, "list_pending_interactions", None)
        if inspector is None:
            return []

        raw_items = await inspector()
        interactions: List[PendingInteraction] = []
        for item in raw_items:
            interactions.append(
                PendingInteraction(
                    interaction_id=item["interaction_id"],
                    tool_name=item.get("tool_name"),
                    created_at_iso=item.get("created_at"),
                    expires_at_iso=item.get("expires_at"),
                    requires_approval=item.get("requires_approval", True),
                    metadata=item.get("metadata", {}),
                )
            )
        self._logger.info(
            "Queried pending interactions",
            extra={"task_id": self._task_id, "count": len(interactions)},
        )
        return interactions


def create_stream_session(
    task_id: str,
    live_result: tuple[AsyncIterator[TaskStreamChunk], LiveCommunicator],
) -> StreamSession:
    """Factory helper to wrap a ``LiveExecutionResult`` into a ``StreamSession``."""
    event_stream, communicator = live_result
    return StreamSession(task_id=task_id, event_stream=event_stream, communicator=communicator)
