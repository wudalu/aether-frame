# -*- coding: utf-8 -*-
"""Approval broker for ADK live tool proposals."""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ...contracts import (
    InteractionRequest,
    InteractionResponse,
    InteractionType,
    TaskChunkType,
    TaskStreamChunk,
)
from ...framework.base.live_communicator import LiveCommunicator

logger = logging.getLogger(__name__)


@dataclass
class _PendingApproval:
    request: InteractionRequest
    chunk: TaskStreamChunk
    created_at: datetime
    timeout_task: Optional[asyncio.Task] = None
    resolved: bool = False
    signature: Optional[str] = None
    future: Optional[asyncio.Future] = None


class AdkApprovalBroker:
    """Coordinates tool approval interactions during live execution."""

    def __init__(
        self,
        communicator: LiveCommunicator,
        *,
        timeout_seconds: float = 90.0,
        fallback_policy: str = "auto_cancel",
        tool_requirements: Optional[Dict[str, bool]] = None,
    ):
        self._communicator = communicator
        self._timeout_seconds = float(timeout_seconds)
        self._fallback_policy = fallback_policy
        self._pending: Dict[str, _PendingApproval] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        self._signature_to_interaction: Dict[str, str] = {}
        self._tool_requirements = tool_requirements or {}

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    @property
    def fallback_policy(self) -> str:
        return self._fallback_policy

    async def on_chunk(self, chunk: TaskStreamChunk) -> TaskStreamChunk:
        """Process a chunk and register or resolve approvals when necessary."""
        if chunk.chunk_type == TaskChunkType.TOOL_PROPOSAL:
            await self._register_proposal(chunk)
        elif chunk.chunk_type == TaskChunkType.TOOL_RESULT:
            if chunk.interaction_id:
                await self.resolve(chunk.interaction_id, None, source="tool_result")
        return chunk

    async def _register_proposal(self, chunk: TaskStreamChunk) -> None:
        interaction_id = chunk.interaction_id or f"tool-{chunk.sequence_id}"
        chunk.interaction_id = interaction_id

        metadata = chunk.metadata or {}
        metadata.setdefault("stage", "tool")

        content = chunk.content if isinstance(chunk.content, dict) else {}
        tool_name = content.get("tool_name") or metadata.get("tool_name")
        arguments = content.get("arguments")

        requires = metadata.get("requires_approval")
        if requires is None:
            requires = self._tool_requirements.get(tool_name)
            if requires is None and tool_name and "." in tool_name:
                requires = self._tool_requirements.get(tool_name.split(".")[-1])
        if requires is None:
            requires = True
        metadata["requires_approval"] = bool(requires)
        metadata["interaction_timeout_seconds"] = self._timeout_seconds
        metadata["approval_policy"] = self._fallback_policy
        chunk.metadata = metadata

        if not metadata["requires_approval"]:
            return

        interaction_request = InteractionRequest(
            interaction_id=interaction_id,
            interaction_type=InteractionType.TOOL_APPROVAL,
            task_id=chunk.task_id,
            content={
                "tool_name": tool_name,
                "arguments": arguments,
            },
            metadata={
                "tool_name": tool_name,
                "requires_confirmation": metadata.get("requires_approval", True),
                "timeout_seconds": self._timeout_seconds,
            },
        )

        chunk.metadata["interaction_request"] = {
            "interaction_id": interaction_request.interaction_id,
            "interaction_type": interaction_request.interaction_type.value,
            "content": interaction_request.content,
            "metadata": interaction_request.metadata,
        }

        pending = _PendingApproval(
            request=interaction_request,
            chunk=chunk,
            created_at=datetime.now(timezone.utc),
        )

        signature = self._build_signature(tool_name, arguments)
        pending.signature = signature
        loop = asyncio.get_running_loop()
        pending.future = loop.create_future()

        async with self._lock:
            if self._closed:
                return
            self._pending[interaction_id] = pending
            if signature:
                self._signature_to_interaction[signature] = interaction_id
            pending.timeout_task = asyncio.create_task(
                self._handle_timeout(interaction_id), name=f"adk-approval-timeout-{interaction_id}"
            )

        logger.info(
            "Tool proposal registered",
            extra={
                "interaction_id": interaction_id,
                "task_id": chunk.task_id,
                "tool_name": tool_name,
                "requires_approval": bool(requires),
                "timeout_seconds": self._timeout_seconds,
            },
        )

    async def resolve(
        self,
        interaction_id: str,
        response: Optional[InteractionResponse],
        *,
        source: str = "user",
    ) -> None:
        """Mark a pending approval as resolved."""
        async with self._lock:
            pending = self._pending.pop(interaction_id, None)
            if pending and pending.signature:
                self._signature_to_interaction.pop(pending.signature, None)

        if not pending:
            return

        pending.resolved = True

        timeout_task = pending.timeout_task
        if timeout_task:
            timeout_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await timeout_task

        self._resolve_future(pending, response)

        logger.info(
            "Approval resolved",
            extra={
                "interaction_id": interaction_id,
                "task_id": pending.request.task_id,
                "source": source,
            },
        )

    async def finalize(self) -> None:
        """Wait for any pending approvals to resolve or time out."""
        async with self._lock:
            pending_tasks = [
                pending.timeout_task
                for pending in self._pending.values()
                if pending.timeout_task is not None
            ]
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)

    def close(self) -> None:
        """Cancel all pending tasks and prevent new registrations."""
        self._closed = True
        for pending in self._pending.values():
            if pending.timeout_task:
                pending.timeout_task.cancel()
        self._pending.clear()
        self._signature_to_interaction.clear()

    async def _handle_timeout(self, interaction_id: str) -> None:
        """Fallback when no approval response is received."""
        try:
            await asyncio.sleep(self._timeout_seconds)
        except asyncio.CancelledError:
            return

        async with self._lock:
            pending = self._pending.get(interaction_id)
            if not pending or pending.resolved or self._closed:
                return

        policy = self._fallback_policy
        if policy not in {"auto_cancel", "auto_approve"}:
            logger.warning(
                "Approval timed out with unsupported policy; leaving unresolved",
                extra={"interaction_id": interaction_id, "policy": policy},
            )
            return

        approved = policy == "auto_approve"
        response = InteractionResponse(
            interaction_id=interaction_id,
            interaction_type=InteractionType.TOOL_APPROVAL,
            approved=approved,
            metadata={"auto_timeout": True, "policy": policy},
        )

        logger.info(
            "Approval timeout fallback triggered",
            extra={"interaction_id": interaction_id, "approved": approved, "policy": policy},
        )

        try:
            await self._communicator.send_user_response(response)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to deliver fallback approval response",
                extra={"interaction_id": interaction_id, "error": str(exc)},
            )

        await self.resolve(interaction_id, response, source="timeout")

    def _resolve_future(self, pending: _PendingApproval, response: Optional[InteractionResponse]) -> None:
        if not pending.future or pending.future.done():
            return
        if response is None:
            pending.future.set_result(True)
        else:
            pending.future.set_result(bool(response.approved))

    def _build_signature(self, tool_name: Optional[str], arguments: Optional[Dict[str, Any]]) -> Optional[str]:
        if not tool_name:
            return None
        try:
            import json

            normalized_args = arguments or {}
            return json.dumps({"tool": tool_name, "args": normalized_args}, sort_keys=True, default=str)
        except Exception:  # noqa: BLE001
            return tool_name

    async def wait_for_tool_approval(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        signature = self._build_signature(tool_name, arguments)
        async with self._lock:
            interaction_id = self._signature_to_interaction.get(signature or "")
            pending = self._pending.get(interaction_id) if interaction_id else None

        if not pending or not pending.future:
            logger.info(
                "No pending approval, defaulting to allowed",
                extra={"tool_name": tool_name, "interaction_signature": signature},
            )
            return {"approved": True}

        approved = await pending.future
        response = {
            "approved": bool(approved),
            "interaction_id": pending.request.interaction_id,
        }
        if not approved:
            response.setdefault("status", "cancelled")
            response.setdefault("error", "Tool invocation cancelled by user")
        logger.info(
            "Tool approval decision obtained",
            extra={
                "interaction_id": pending.request.interaction_id,
                "tool_name": pending.request.metadata.get("tool_name"),
                "approved": bool(approved),
            },
        )
        return response

    async def list_pending_interactions(self) -> List[Dict[str, Any]]:
        """Return structured data for pending approval interactions."""
        async with self._lock:
            pending_values = list(self._pending.values())

        items: List[Dict[str, Any]] = []
        for pending in pending_values:
            expires_at = pending.created_at + timedelta(seconds=self._timeout_seconds)
            metadata = dict(pending.request.metadata or {})
            metadata.setdefault("tool_name", metadata.get("tool_name") or pending.chunk.metadata.get("tool_name"))
            metadata.setdefault("requires_confirmation", metadata.get("requires_confirmation", True))
            items.append(
                {
                    "interaction_id": pending.request.interaction_id,
                    "tool_name": metadata.get("tool_name"),
                    "created_at": pending.created_at.isoformat(),
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "requires_approval": metadata.get("requires_confirmation", True),
                    "metadata": metadata,
                }
            )
        return items


class ApprovalAwareCommunicator:
    """Live communicator wrapper that notifies the approval broker on responses."""

    def __init__(self, delegate: LiveCommunicator, broker: AdkApprovalBroker):
        self._delegate = delegate
        self._broker = broker

    async def send_user_response(self, response: InteractionResponse) -> None:
        await self._delegate.send_user_response(response)
        await self._broker.resolve(response.interaction_id, response, source="user")

    async def send_cancellation(self, reason: str = "user_cancelled") -> None:
        await self._delegate.send_cancellation(reason)

    async def send_user_message(self, message: str) -> None:
        await self._delegate.send_user_message(message)

    def close(self) -> None:
        self._broker.close()
        self._delegate.close()

    @property
    def delegate(self) -> LiveCommunicator:
        return self._delegate

    @property
    def broker(self) -> AdkApprovalBroker:
        return self._broker
