# -*- coding: utf-8 -*-
"""Unit tests targeting AdkDomainAgent execution paths and error handling."""

from types import ModuleType, SimpleNamespace

import builtins
import pytest
import sys

from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
from aether_frame.contracts import (
    AgentRequest,
    TaskChunkType,
    TaskRequest,
    TaskStatus,
    UniversalMessage,
)


def _install_genai_stub(monkeypatch):
    """Install a lightweight google.genai.types stub for content creation."""
    import sys

    if "google.genai" in sys.modules:
        return

    genai_module = ModuleType("google.genai")
    types_module = ModuleType("google.genai.types")

    class Part:
        def __init__(self, text=None, inline_data=None):
            self.text = text
            self.inline_data = inline_data

    class Content:
        def __init__(self, role, parts):
            self.role = role
            self.parts = parts
            self.text = "\n".join(part.text for part in parts if getattr(part, "text", None))

    class Blob:
        def __init__(self, mime_type, data):
            self.mime_type = mime_type
            self.data = data

    types_module.Part = Part
    types_module.Content = Content
    types_module.Blob = Blob
    genai_module.types = types_module

    google_pkg = ModuleType("google")
    google_pkg.genai = genai_module

    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)


def _build_agent_request():
    task_request = TaskRequest(
        task_id="task-123",
        task_type="chat",
        description="desc",
        messages=[UniversalMessage(role="user", content="Explain coverage.")],
    )
    return AgentRequest(task_request=task_request)


@pytest.mark.asyncio
async def test_execute_with_adk_runner_missing_runtime_context():
    agent = AdkDomainAgent(agent_id="agent-ctx", config={})
    agent.runtime_context = {}

    result = await agent._execute_with_adk_runner(_build_agent_request())

    assert result.status == TaskStatus.ERROR
    assert "runtime context" in result.error_message
    assert result.metadata["missing_components"] == ["runner", "session_id"]


@pytest.mark.asyncio
async def test_execute_with_adk_runner_handles_runner_exception(monkeypatch):
    agent = AdkDomainAgent(agent_id="agent-runner", config={})
    agent.runtime_context = {"runner": object(), "session_id": "session-1", "user_id": "alice"}

    async def failing_run(*args, **kwargs):
        raise RuntimeError("runner exploded")

    monkeypatch.setattr(agent, "_run_adk_with_runner_and_agent", failing_run)

    result = await agent._execute_with_adk_runner(_build_agent_request())

    assert result.status == TaskStatus.ERROR
    assert result.metadata["error_stage"] == "adk_domain_agent.runner_execution"
    assert result.metadata["error_type"] == "RuntimeError"


class _FakeEvent:
    def __init__(self, text, *, is_final=False):
        part = SimpleNamespace(text=text)
        self.content = SimpleNamespace(parts=[part], text=text)
        self._is_final = is_final

    def is_final_response(self):
        return self._is_final


class _FakeRunner:
    def __init__(self, events):
        self._events = events

    def run_async(self, *_, **__):
        async def iterator():
            for event in self._events:
                yield event

        return iterator()


@pytest.mark.asyncio
async def test_run_adk_with_runner_selects_best_response(monkeypatch):
    _install_genai_stub(monkeypatch)
    agent = AdkDomainAgent(agent_id="agent-select", config={})
    agent.runtime_context["adk_session"] = SimpleNamespace(id="adk-session")
    agent.adk_agent = object()

    events = [
        _FakeEvent("Short draft", is_final=False),
        _FakeEvent(
            "This is a longer, well-formed explanation:\n- bullet point details",
            is_final=True,
        ),
    ]
    runner = _FakeRunner(events)

    response = await agent._run_adk_with_runner_and_agent(
        runner, user_id="bob", session_id="session-2", adk_content="Hello from user"
    )

    assert "longer, well-formed explanation" in response
    assert "bullet point" in response


@pytest.mark.asyncio
async def test_run_adk_with_runner_returns_mock_on_import_error(monkeypatch):
    real_import = builtins.__import__

    def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("google.genai"):
            raise ImportError("no genai")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    agent = AdkDomainAgent(agent_id="agent-mock", config={})

    result = await agent._run_adk_with_runner_and_agent(
        runner=_FakeRunner([]),
        user_id="eve",
        session_id="session-3",
        adk_content="Ping",
    )

    assert result == "Mock ADK processed: Ping"


@pytest.mark.asyncio
async def test_run_adk_with_runner_wraps_runner_errors(monkeypatch):
    _install_genai_stub(monkeypatch)
    agent = AdkDomainAgent(agent_id="agent-error-wrap", config={})
    agent.adk_agent = object()

    class BrokenRunner:
        def run_async(self, *_, **__):
            raise ValueError("run_async failed")

    with pytest.raises(RuntimeError) as excinfo:
        await agent._run_adk_with_runner_and_agent(
            BrokenRunner(), user_id="sam", session_id="session-4", adk_content="content"
        )

    assert "ADK Runner execution failed" in str(excinfo.value)


def test_convert_adk_response_to_task_result_error_branch(monkeypatch):
    agent = AdkDomainAgent(agent_id="agent-convert", config={})

    class ExplodingMessage:
        def __init__(self, *_, **__):
            raise ValueError("boom")

    monkeypatch.setattr(
        "aether_frame.agents.adk.adk_domain_agent.UniversalMessage", ExplodingMessage
    )

    result = agent._convert_adk_response_to_task_result("payload", "task-xyz")

    assert result.status == TaskStatus.ERROR
    assert "Failed to convert ADK response" in result.error_message


@pytest.mark.asyncio
async def test_create_error_live_result_emits_error_chunk():
    agent = AdkDomainAgent(agent_id="agent-live", config={})

    stream, communicator = agent._create_error_live_result("task-live", "fatal")
    chunk = await stream.__anext__()

    assert chunk.chunk_type == TaskChunkType.ERROR
    assert chunk.is_final is True
    assert chunk.metadata["stage"] == "error"

    assert communicator.send_user_message("noop") is None
    assert communicator.send_user_response({"text": "noop"}) is None


@pytest.mark.asyncio
async def test_execute_handles_runner_exception(monkeypatch):
    agent = AdkDomainAgent(agent_id="agent-exec", config={})
    agent.runtime_context = {"runner": object(), "session_id": "sess-1", "user_id": "user"}
    agent._tools_initialized = True

    async def failing_execute(*args, **kwargs):
        raise RuntimeError("runner failed")

    monkeypatch.setattr(agent, "_execute_with_adk_runner", failing_execute)

    task_request = TaskRequest(task_id="t-exec", task_type="chat", description="desc")
    agent_request = AgentRequest(task_request=task_request)

    result = await agent.execute(agent_request)
    assert result.status == TaskStatus.ERROR
    assert result.metadata["error_stage"] == "adk_domain_agent.execute"
    assert result.metadata["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_execute_with_adk_runner_initializes_tools(monkeypatch):
    agent = AdkDomainAgent(agent_id="agent-tools", config={})
    agent.runtime_context = {"runner": SimpleNamespace(), "session_id": "sess-2", "user_id": "user"}
    created_payloads = []

    async def fake_create(tools=None):
        created_payloads.append(tools)

    async def fake_run(*args, **kwargs):
        return "response text"

    monkeypatch.setattr(agent, "_create_adk_agent", fake_create)
    monkeypatch.setattr(agent, "_run_adk_with_runner_and_agent", fake_run)
    async def fake_memory(*args, **kwargs):
        return []

    monkeypatch.setattr(agent, "_retrieve_memory_snippets", fake_memory)
    monkeypatch.setattr(agent, "_convert_messages_to_adk_content", lambda msgs: "converted")

    universal_tool = SimpleNamespace(name="demo.tool")
    task_request = TaskRequest(
        task_id="t-tools",
        task_type="chat",
        description="desc",
        available_tools=[universal_tool],
        messages=[UniversalMessage(role="user", content="hi")],
    )
    agent_request = AgentRequest(task_request=task_request)

    result = await agent.execute(agent_request)
    assert result.status == TaskStatus.SUCCESS
    assert agent._tools_initialized is True
    assert created_payloads[0][0] is universal_tool


@pytest.mark.asyncio
async def test_execute_live_without_runner_returns_error():
    agent = AdkDomainAgent(agent_id="agent-live-error", config={})
    agent.runtime_context = {"session_id": "sess-3", "user_id": "user"}

    task_request = TaskRequest(task_id="t-live", task_type="chat", description="desc")

    stream, _ = await agent.execute_live(task_request)
    chunk = await stream.__anext__()
    assert chunk.chunk_type == TaskChunkType.ERROR
    assert chunk.is_final is True
    assert chunk.metadata.get("framework") == "adk"


@pytest.mark.asyncio
async def test_execute_live_missing_live_queue(monkeypatch):
    agent = AdkDomainAgent(agent_id="agent-live-import", config={})
    agent.runtime_context = {
        "runner": SimpleNamespace(),
        "session_id": "sess-4",
        "user_id": "user",
    }

    # Ensure import fails
    monkeypatch.setitem(sys.modules, "google", ModuleType("google"))
    task_request = TaskRequest(task_id="t-live2", task_type="chat", description="desc")

    stream, _ = await agent.execute_live(task_request)
    chunk = await stream.__anext__()
    assert chunk.chunk_type == TaskChunkType.ERROR
    assert chunk.is_final is True
    assert chunk.metadata.get("framework") == "adk"


def test_convert_adk_response_success():
    agent = AdkDomainAgent(agent_id="agent-convert-ok", config={})
    result = agent._convert_adk_response_to_task_result("payload", "task-success")
    assert result.status == TaskStatus.SUCCESS
    assert result.messages[0].content == "payload"
