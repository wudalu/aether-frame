# -*- coding: utf-8 -*-
"""Session recovery record and store abstractions for ADK lifecycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from types import SimpleNamespace
from typing import Dict, List, Optional

from ...contracts import AgentConfig


@dataclass(frozen=True)
class SessionRecoveryRecord:
    """Persisted payload for restoring a cleared chat session."""

    chat_session_id: str
    user_id: str
    agent_id: str
    agent_config: Optional[AgentConfig]
    chat_history: List[Dict[str, object]]
    archived_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, object]:
        """Return a serialisable view useful for logging or external stores."""

        agent_config_dict: Optional[Dict[str, object]] = None
        if self.agent_config is not None:
            agent_config_dict = asdict(self.agent_config)

        return {
            "chat_session_id": self.chat_session_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "agent_config": agent_config_dict,
            "chat_history_length": len(self.chat_history) if self.chat_history else 0,
            "archived_at": self.archived_at.isoformat(),
        }


class SessionRecoveryStore:
    """Abstract persistence for session recovery records."""

    def save(self, record: SessionRecoveryRecord) -> None:
        raise NotImplementedError

    def load(self, chat_session_id: str) -> Optional[SessionRecoveryRecord]:
        raise NotImplementedError

    def purge(self, chat_session_id: str) -> None:
        raise NotImplementedError


class InMemorySessionRecoveryStore(SessionRecoveryStore):
    """Simple in-memory store for development and unit testing."""

    def __init__(self):
        self._records: Dict[str, SessionRecoveryRecord] = {}
        self._lock = RLock()

    def save(self, record: SessionRecoveryRecord) -> None:  # noqa: D401
        """Store or overwrite the recovery record."""

        with self._lock:
            self._records[record.chat_session_id] = record

    def load(self, chat_session_id: str) -> Optional[SessionRecoveryRecord]:
        with self._lock:
            return self._records.get(chat_session_id)

    def purge(self, chat_session_id: str) -> None:
        with self._lock:
            self._records.pop(chat_session_id, None)


class InMemoryArchiveSessionService:
    """Mock SessionService with archive APIs backed by SessionRecoveryStore."""

    def __init__(self, recovery_store: Optional[SessionRecoveryStore] = None):
        self.sessions: Dict[str, SimpleNamespace] = {}
        self.recovery_store = recovery_store or InMemorySessionRecoveryStore()
        self.shutdown_called = False

    async def create_session(self, app_name: str, user_id: str, session_id: str) -> SimpleNamespace:
        session = SimpleNamespace(app_name=app_name, user_id=user_id, session_id=session_id)
        self.sessions[session_id] = session
        return session

    async def delete_session(self, app_name: str, user_id: str, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    async def archive_session(self, record: SessionRecoveryRecord) -> None:
        self.recovery_store.save(record)

    async def load_archived_session(self, chat_session_id: str) -> Optional[SessionRecoveryRecord]:
        return self.recovery_store.load(chat_session_id)

    async def purge_archived_session(self, chat_session_id: str) -> None:
        self.recovery_store.purge(chat_session_id)

    async def shutdown(self) -> None:
        self.shutdown_called = True

    def get_recovery_store(self) -> SessionRecoveryStore:
        """Expose underlying recovery store for lifecycle manager reuse."""

        return self.recovery_store
