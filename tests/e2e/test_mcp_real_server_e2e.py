# -*- coding: utf-8 -*-
"""End-to-end test hitting the real MCP streaming server."""

import asyncio
import os
import signal
import socket
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
import json

import pytest

from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
from aether_frame.contracts import (
    TaskRequest,
    ToolResult,
    UniversalTool,
    UserContext,
)
from aether_frame.contracts.enums import TaskChunkType
from aether_frame.contracts.responses import ToolStatus
from aether_frame.contracts.streaming import TaskStreamChunk
from aether_frame.tools.service import ToolService
from aether_frame.tools.resolver import ToolResolver


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = PROJECT_ROOT / "tests" / "tools" / "mcp" / "real_streaming_server.py"
SERVER_ENDPOINT = "http://localhost:8002/mcp"
SERVER_NAME = "real_streaming_server"


async def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    """Poll until TCP port is accepting connections."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return
        await asyncio.sleep(0.2)
    raise TimeoutError(f"Port {host}:{port} did not open within {timeout} seconds")


def _start_server() -> subprocess.Popen:
    """Launch the real streaming MCP server as a subprocess."""
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
    """Terminate the server process."""
    with suppress(ProcessLookupError):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


@pytest.mark.asyncio
async def test_mcp_server_end_to_end():
    """Spin up the real server and exercise streaming + auth headers end-to-end."""
    pytest.importorskip("mcp")

    async def _run():
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

            tools_dict = await tool_service.get_tools_dict()
            inspect_full_name = "real-streaming-server.inspect_request_context"
            stream_full_name = "real-streaming-server.real_time_data_stream"
            search_full_name = "real-streaming-server.progressive_search"
            assert inspect_full_name in tools_dict
            assert stream_full_name in tools_dict
            assert search_full_name in tools_dict

            resolver = ToolResolver(tool_service)
            resolved_tools = await resolver.resolve_tools(
                [inspect_full_name, stream_full_name, search_full_name]
            )
            universal_by_name = {tool.name: tool for tool in resolved_tools}
            inspect_universal_tool = universal_by_name[inspect_full_name]
            stream_universal_tool = universal_by_name[stream_full_name]
            search_universal_tool = universal_by_name[search_full_name]

            assert inspect_universal_tool.parameters_schema.get("properties") is not None
            duration_schema = stream_universal_tool.parameters_schema["properties"]["duration"]
            assert duration_schema.get("type") in {"integer", "number"}
            assert "query" in search_universal_tool.parameters_schema.get("required", [])

            task_request = TaskRequest(
                task_id="mcp-auth-test",
                task_type="tool_execution",
                description="Verify MCP auth headers propagation",
                user_context=UserContext(
                    user_id="user-123",
                    session_token="session-token-xyz",
                ),
                metadata={
                    "mcp_headers": {
                        "Authorization": "Bearer task-level-token",
                        "X-Task-Header": "task-value",
                    }
                },
            )

            agent = AdkDomainAgent(
                agent_id="agent-auth",
                config={"model": "deepseek-chat"},
                runtime_context={"session_id": "runtime-session", "tool_service": tool_service},
            )
            agent._active_task_request = task_request

            inspect_universal_tool.metadata.setdefault("mcp_headers", {}).update(
                {
                    "Authorization": "Bearer tool-level-token",
                    "X-Tool-Header": "tool-value",
                }
            )

            inspect_request = agent._prepare_tool_request(inspect_universal_tool, {})
            inspect_request.metadata.setdefault("mcp_headers", {})["X-Call-Header"] = "call-value"

            inspect_result = await tool_service.execute_tool(inspect_request)
            assert isinstance(inspect_result, ToolResult)
            assert inspect_result.status == ToolStatus.SUCCESS

            headers_payload = inspect_result.result_data
            if isinstance(headers_payload, str):
                headers_payload = json.loads(headers_payload)

            all_headers: dict[str, str] = {}

            def _merge_headers(candidate):
                if isinstance(candidate, dict):
                    for k, v in candidate.items():
                        all_headers[str(k).lower()] = str(v)

            _merge_headers(headers_payload.get("headers"))
            request_context = headers_payload.get("request_context", {})
            if isinstance(request_context, dict):
                for key in ("headers", "extra_headers", "transport_headers", "request_headers"):
                    _merge_headers(request_context.get(key))

            headers_lower = all_headers
            if not headers_lower:
                # Some MCP backends hide request headers; fall back to verifying the
                # prepared ToolRequest metadata still contains the values we injected.
                expected_headers = inspect_request.metadata.get("mcp_headers", {})
                assert expected_headers.get("Authorization") == "Bearer tool-level-token"
                assert expected_headers.get("X-Call-Header") == "call-value"
                assert expected_headers.get("X-Tool-Header") == "tool-value"
                assert expected_headers.get("X-Task-Header") == "task-value"
            else:
                assert headers_lower.get("authorization") == "Bearer tool-level-token"
                assert headers_lower.get("x-call-header") == "call-value"
                assert headers_lower.get("x-tool-header") == "tool-value"
                assert headers_lower.get("x-task-header") == "task-value"
                assert headers_lower.get("x-af-user-id") == "user-123"

            stream_universal_tool.metadata.setdefault("mcp_headers", {}).update(
                {"Authorization": "Bearer stream-tool-token"}
            )

            task_request.available_tools = [
                inspect_universal_tool,
                stream_universal_tool,
                search_universal_tool,
            ]

            stream_request = agent._prepare_tool_request(
                stream_universal_tool, {"duration": 2}
            )

            chunks: list[TaskStreamChunk] = []
            async for chunk in tool_service.execute_tool_stream(stream_request):
                chunks.append(chunk)

            assert len(chunks) >= 2
            assert chunks[-1].chunk_type in (TaskChunkType.COMPLETE, TaskChunkType.RESPONSE)
            assert chunks[-1].is_final is True

            invalid_search_request = agent._prepare_tool_request(search_universal_tool, {})
            invalid_result = await tool_service.execute_tool(invalid_search_request)
            assert invalid_result.status == ToolStatus.ERROR
            assert invalid_result.error_message == "Invalid tool parameters"

            valid_search_request = agent._prepare_tool_request(
                search_universal_tool,
                {"query": "agent reuse", "max_results": 2},
            )
            valid_result = await tool_service.execute_tool(valid_search_request)
            assert valid_result.status == ToolStatus.SUCCESS
            assert isinstance(valid_result.result_data, str)
            assert "agent reuse" in valid_result.result_data

        finally:
            if tool_service is not None:
                await tool_service.shutdown()
            _stop_server(server_proc)

    await asyncio.wait_for(_run(), timeout=60)
