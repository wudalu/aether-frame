# -*- coding: utf-8 -*-
"""Tests for AdkLiveCommunicator using stubbed ADK dependencies."""

import sys
from types import ModuleType

import pytest

from aether_frame.contracts import InteractionResponse, InteractionType
from aether_frame.framework.adk.live_communicator import AdkLiveCommunicator


class StubPart:
    def __init__(self, text):
        self.text = text

    @classmethod
    def from_text(cls, text):
        return cls(text)


class StubContent:
    def __init__(self, role, parts):
        self.role = role
        self.parts = parts


def install_genai_stub(monkeypatch):
    module = ModuleType("google.genai.types")
    module.Part = StubPart
    module.Content = StubContent
    monkeypatch.setitem(sys.modules, "google", ModuleType("google"))
    sys.modules["google"].genai = ModuleType("genai")
    sys.modules["google"].genai.types = module
    monkeypatch.setitem(sys.modules, "google.genai", ModuleType("google.genai"))
    monkeypatch.setitem(sys.modules, "google.genai.types", module)


class StubQueue:
    def __init__(self):
        self.sent_messages = []
        self.closed = False

    def send_content(self, content):
        self.sent_messages.append(content)

    def close(self):
        self.closed = True


@pytest.fixture
def communicator(monkeypatch):
    install_genai_stub(monkeypatch)
    return AdkLiveCommunicator(StubQueue())


@pytest.mark.asyncio
async def test_send_user_response_formats_message(communicator):
    response = InteractionResponse(
        interaction_id="tool-1",
        interaction_type=InteractionType.TOOL_APPROVAL,
        approved=True,
        user_message="Looks good",
        response_data={"id": 1},
    )
    await communicator.send_user_response(response)
    message = communicator._live_request_queue.sent_messages[-1]
    assert message.role == "user"
    assert "tool-1" in message.parts[0].text


@pytest.mark.asyncio
async def test_send_cancellation_and_user_message(communicator):
    await communicator.send_cancellation("timeout")
    await communicator.send_user_message("hello")
    assert communicator._live_request_queue.sent_messages[0].parts[0].text.startswith("CANCELLATION_REQ")
    assert communicator._live_request_queue.sent_messages[1].parts[0].text == "hello"


def test_close_marks_queue_closed(communicator):
    communicator.close()
    assert communicator._live_request_queue.closed is True
