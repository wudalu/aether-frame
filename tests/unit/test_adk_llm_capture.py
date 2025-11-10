# -*- coding: utf-8 -*-
import logging
from types import SimpleNamespace

import pytest

from aether_frame.framework.adk.llm_callbacks import (
    CAPTURE_STATE_KEY,
    build_llm_capture_callbacks,
    build_identity_strip_callback,
    chain_before_model_callbacks,
)
from aether_frame.contracts.requests import TaskRequest
from aether_frame.contracts.contexts import UserContext


class _DummyRequest:
    def model_dump(self, mode: str = "json"):
        return {"mode": mode, "data": "payload"}


class _DummyResponse:
    def model_dump(self, mode: str = "json"):
        return {"mode": mode, "result": "ok"}


class _DummyContext:
    def __init__(self):
        self.state = {}
        self.agent_name = "dummy-agent"
        self.invocation_id = "invocation-123"


class _StubDomainAgent:
    def __init__(self):
        self.agent_id = "agent-123"
        self.runtime_context = {"session_id": "adk-session", "user_id": "runtime-user"}
        self.logger = logging.getLogger("test")
        self._active_task_request = TaskRequest(
            task_id="task-1",
            task_type="chat",
            description="desc",
            user_context=UserContext(user_id="user-42"),
            session_id="business-session",
        )


@pytest.mark.asyncio
async def test_llm_capture_callbacks_stash_metadata_and_log(caplog):
    agent = _StubDomainAgent()
    before_agent_cb, before_model_cb, after_model_cb = build_llm_capture_callbacks(agent)

    ctx = _DummyContext()

    before_agent_cb(ctx)
    assert CAPTURE_STATE_KEY in ctx.state
    metadata = ctx.state[CAPTURE_STATE_KEY]
    assert metadata["task_id"] == "task-1"
    assert metadata["session_id"] == "business-session"
    assert metadata["user_id"] == "user-42"

    caplog.set_level(logging.INFO, logger="aether_frame.adk.llm_capture")

    before_model_cb(ctx, _DummyRequest())
    after_model_cb(ctx, _DummyResponse())

    records = [rec for rec in caplog.records if rec.name == "aether_frame.adk.llm_capture"]
    assert len(records) == 2
    assert "Captured ADK LLM request" in records[0].message
    assert "Captured ADK LLM response" in records[1].message


def test_chain_before_model_callbacks_respects_short_circuit():
    call_order = []

    def cb1(ctx, request):
        call_order.append("cb1")
        return {"forced": "response"}

    def cb2(ctx, request):
        call_order.append("cb2")
        return None

    chained = chain_before_model_callbacks(cb1, cb2)
    ctx = _DummyContext()
    request = SimpleNamespace()

    result = chained(ctx, request)

    assert result == {"forced": "response"}
    assert call_order == ["cb1"]


def test_identity_strip_callback_removes_adk_boilerplate():
    domain_agent = SimpleNamespace(
        adk_agent=SimpleNamespace(name="agent-123", description="Domain Agent"),
        config={"description": "fallback"},
        agent_id="agent-123",
    )
    callback = build_identity_strip_callback(domain_agent)

    system_instruction = (
        "Original instruction."
        "\n\nYou are an agent. Your internal name is \"agent-123\"."
        "\n\n The description about you is \"Domain Agent\""
        "\n\nAnother line."
    )
    request = SimpleNamespace(config=SimpleNamespace(system_instruction=system_instruction))

    callback(_DummyContext(), request)

    assert "Your internal name" not in request.config.system_instruction
    assert "The description about you" not in request.config.system_instruction
    assert "Original instruction." in request.config.system_instruction
    assert "Another line." in request.config.system_instruction
