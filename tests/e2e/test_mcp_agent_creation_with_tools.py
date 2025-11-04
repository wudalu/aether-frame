import asyncio
import os
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

import pytest

from aether_frame.agents.adk.tool_conversion import create_function_tools
from aether_frame.contracts import AgentConfig, AgentRequest, FrameworkType, TaskRequest, TaskResult
from aether_frame.contracts.enums import TaskStatus
from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from aether_frame.tools.service import ToolService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = PROJECT_ROOT / "tests" / "tools" / "mcp" / "real_streaming_server.py"
SERVER_ENDPOINT = "http://localhost:8002/mcp"


async def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            with suppress(Exception):
                await writer.wait_closed()
            return
        except OSError:
            await asyncio.sleep(0.2)
    raise TimeoutError(f"Port {host}:{port} did not open within {timeout} seconds")


def _start_server() -> subprocess.Popen:
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(PROJECT_ROOT) + (os.pathsep + pythonpath if pythonpath else "")
    )
    return subprocess.Popen(
        [sys.executable, str(SERVER_PATH)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )


def _stop_server(proc: subprocess.Popen) -> None:
    with suppress(ProcessLookupError):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


@pytest.mark.asyncio
async def test_agent_creation_with_tools_executes_mcp_tool(monkeypatch):
    pytest.importorskip("mcp")

    server_proc = _start_server()
    tool_service: ToolService | None = None

    try:
        await _wait_for_port("localhost", 8002)

        tool_service = ToolService()
        await tool_service.initialize(
            {
                "enable_mcp": True,
                "mcp_servers": [
                    {
                        "name": "real-streaming-server",
                        "endpoint": SERVER_ENDPOINT,
                        "timeout": 30,
                    }
                ],
            }
        )

        adapter = AdkFrameworkAdapter()
        await adapter.initialize(tool_service=tool_service)

        agent_config = AgentConfig(
            agent_type="stream_agent",
            system_prompt="You stream data",
            available_tools=["real-streaming-server.real_time_data_stream"],
        )

        captured: dict[str, object] = {}

        def fake_build_adk_agent(
            *,
            name: str,
            description: str,
            instruction: str,
            model_identifier: str,
            tool_service,
            universal_tools,
            request_factory,
            settings,
            enable_streaming=False,
            model_config=None,
            framework_config=None,
            before_agent_callback=None,
            before_model_callback=None,
            after_model_callback=None,
        ):
            captured["build_called"] = True
            universal_list = list(universal_tools or [])
            tools = create_function_tools(
                tool_service,
                universal_list,
                request_factory=request_factory,
            )
            captured["universal_tools"] = universal_list

            class DummyAgent:
                def __init__(self, tools):
                    self.tools = tools
                    self.name = "dummy"

            return DummyAgent(tools)

        monkeypatch.setattr(
            "aether_frame.agents.adk.adk_domain_agent.build_adk_agent",
            fake_build_adk_agent,
        )

        domain_agent = await adapter._create_domain_agent_for_config(agent_config)

        assert captured.get("build_called") is True
        assert len(domain_agent.adk_agent.tools) == 1
        first_tool = domain_agent.adk_agent.tools[0]
        result = await first_tool.func(duration=1)
        assert result["status"] == "success"
        assert "Real-time data point" in result["result"]

        async def _noop(*args, **kwargs):
            return None

        captured["agent_request_tools"] = None

        async def fake_execute_with_adk_runner(agent_request):
            captured["agent_request_tools"] = agent_request.task_request.available_tools
            tool_result = await domain_agent.adk_agent.tools[0].func(duration=1)
            return TaskResult(
                task_id="chat",
                status=TaskStatus.SUCCESS,
                tool_results=[tool_result],
            )

        domain_agent.runtime_context.update({"runner": object(), "session_id": "sess"})
        domain_agent.hooks.before_execution = _noop
        domain_agent.hooks.after_execution = _noop
        domain_agent.hooks.on_error = _noop
        domain_agent._execute_with_adk_runner = fake_execute_with_adk_runner

        chat_request = TaskRequest(
            task_id="chat",
            task_type="conversation",
            description="Chat without tool override",
            available_tools=[],
        )
        agent_request = AgentRequest(
            agent_type="stream_agent",
            framework_type=FrameworkType.ADK,
            task_request=chat_request,
            session_id="sess",
        )

        task_result = await domain_agent.execute(agent_request)
        assert captured["agent_request_tools"] == []
        assert task_result.tool_results
        assert task_result.tool_results[0]["status"] == "success"

    finally:
        if tool_service is not None:
            await tool_service.shutdown()
        _stop_server(server_proc)
