import asyncio

import pytest

from aether_frame.framework.adk.live_communicator import AdkLiveCommunicator


class DummyLiveRequestQueue:
    def __init__(self):
        self.contents = []
        self.closed = False

    def send_content(self, content):
        self.contents.append(content)

    def close(self):
        self.closed = True


class DummySession:
    def __init__(self):
        self.events = []


class DummyRecorder:
    def __init__(self, store):
        self.store = store

    async def record_user_text(self, text: str) -> None:
        self.store.append(text)


@pytest.mark.asyncio
async def test_live_stream_records_multi_turn_user_inputs():
    recorded_messages: list[str] = []

    async def send_turn(message: str):
        recorder = DummyRecorder(recorded_messages)
        communicator = AdkLiveCommunicator(
            DummyLiveRequestQueue(), history_recorder=recorder
        )
        await communicator.send_user_message(message)
        return communicator

    comm1 = await send_turn("hello turn1")
    assert recorded_messages == ["hello turn1"]
    assert not comm1._live_request_queue.closed  # noqa: SLF001

    # Simulate second turn (fresh communicator in real flow)
    comm2 = await send_turn("second turn question")
    assert recorded_messages == ["hello turn1", "second turn question"]

    # Ensure queues can still be closed independently
    comm1.close()
    comm2.close()
    assert comm1._live_request_queue.closed  # noqa: SLF001
    assert comm2._live_request_queue.closed  # noqa: SLF001
