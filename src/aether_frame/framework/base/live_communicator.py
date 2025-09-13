# -*- coding: utf-8 -*-
"""Live Communication Protocol for Framework Abstraction Layer."""

from typing import Protocol

from ...contracts import InteractionResponse


class LiveCommunicator(Protocol):
    """
    Protocol for bidirectional communication during live execution.

    This protocol defines the interface for real-time communication between
    the executing agent and the client during interactive workflows. Framework
    adapters must provide implementations of this protocol.
    """

    async def send_user_response(self, response: InteractionResponse) -> None:
        """
        Send user response to the executing agent.

        Args:
            response: User's response to an interaction request
        """
        ...

    async def send_cancellation(self, reason: str = "user_cancelled") -> None:
        """
        Send cancellation signal to stop execution.

        Args:
            reason: Optional reason for cancellation
        """
        ...

    async def send_user_message(self, message: str) -> None:
        """
        Send a regular user message during live session.

        Args:
            message: User message to send to the agent
        """
        ...

    def close(self) -> None:
        """Close the communication channel and cleanup resources."""
        ...
