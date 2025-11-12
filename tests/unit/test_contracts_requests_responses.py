# -*- coding: utf-8 -*-
"""Unit tests for contracts.requests/responses dataclass defaults."""

from aether_frame.contracts import TaskRequest, TaskResult, TaskStatus, UniversalMessage


def test_task_request_default_lists_are_isolated():
    req1 = TaskRequest(task_id="1", task_type="chat", description="a")
    req2 = TaskRequest(task_id="2", task_type="chat", description="b")

    req1.messages.append(UniversalMessage(role="user", content="hi"))
    assert req2.messages == []

    req1.available_tools.append("tool")
    assert req2.available_tools == []


def test_task_result_defaults_and_metadata():
    result = TaskResult(task_id="1", status=TaskStatus.SUCCESS)
    assert result.messages == []
    result.metadata["foo"] = "bar"

    other = TaskResult(task_id="2", status=TaskStatus.ERROR)
    assert other.metadata == {}
