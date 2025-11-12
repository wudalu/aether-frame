# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from aether_frame.framework.adk.session_recovery import (
    SessionRecoveryRecord,
    recovery_record_to_messages,
)


def test_recovery_record_to_messages_converts_entries():
    record = SessionRecoveryRecord(
        chat_session_id="chat-1",
        user_id="user-1",
        agent_id="agent-1",
        agent_config=None,
        chat_history=[
            {"role": "user", "content": "hi"},
            {"author": "assistant", "content": "hello", "metadata": {"foo": "bar"}},
        ],
        archived_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    messages = recovery_record_to_messages(record)

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "hi"
    assert messages[0].metadata["restored_from_archive"] is True
    assert "archived_at" in messages[0].metadata

    assert messages[1].role == "assistant"
    assert messages[1].metadata["foo"] == "bar"
