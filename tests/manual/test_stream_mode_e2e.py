#!/usr/bin/env python3
"""
End-to-end stream mode test.

This script creates a live ADK session backed by DeepSeek streaming, loads the
real MCP progressive search tool, approves the tool proposal, and logs all
request/response artifacts for inspection.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
from contextlib import suppress
import enum
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from dotenv import load_dotenv

from aether_frame.bootstrap import create_system_components, shutdown_system
from aether_frame.config.settings import Settings
from aether_frame.contracts import (
    AgentConfig,
    TaskChunkType,
    TaskRequest,
    TaskStatus,
    UniversalMessage,
    UserContext,
    UserPermissions,
)
from aether_frame.execution.task_factory import TaskRequestFactory

LOGGER = logging.getLogger("stream_mode_e2e")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "logs" / "stream_mode_e2e.log"
REAL_MCP_SERVER = PROJECT_ROOT / "tests" / "tools" / "mcp" / "real_streaming_server.py"
REAL_MCP_PORT = 8002


def _ensure_virtualenv() -> None:
    expected_prefix = (PROJECT_ROOT / ".venv").resolve()
    current_prefix = Path(sys.prefix).resolve()
    if expected_prefix != current_prefix:
        print(
            "❌ This script must be executed with the project virtual environment activated.\n"
            f"   Expected venv: {expected_prefix}\n"
            f"   Current prefix: {current_prefix}"
        )
        sys.exit(1)


async def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return
        await asyncio.sleep(0.2)
    raise TimeoutError(f"Port {host}:{port} not available within {timeout} seconds.")


def _start_real_mcp_server() -> subprocess.Popen:
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + pythonpath if pythonpath else "")
    return subprocess.Popen(
        [sys.executable, str(REAL_MCP_SERVER)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )


def _stop_real_mcp_server(proc: Optional[subprocess.Popen]) -> None:
    if not proc:
        return
    with suppress(ProcessLookupError):
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def _serialize(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_serialize(v) for v in obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if hasattr(obj, "__dict__"):
        return {k: _serialize(v) for k, v in obj.__dict__.items()}
    return obj


def _log_json(title: str, payload: Dict[str, Any]) -> None:
    LOGGER.info("%s: %s", title, json.dumps(payload, ensure_ascii=False, indent=2))


async def run_stream_mode_e2e() -> None:
    settings = Settings()
    settings.default_model = os.getenv("HITL_TEST_MODEL", os.getenv("DEFAULT_MODEL", "deepseek-chat"))
    settings.enable_mcp_tools = True
    settings.mcp_servers = [
        {"name": "real-streaming-server", "endpoint": "http://localhost:8002/mcp"}
    ]

    components = await create_system_components(settings)
    server_proc: Optional[subprocess.Popen] = None

    try:
        LOGGER.info("Starting real MCP server at port %s", REAL_MCP_PORT)
        server_proc = _start_real_mcp_server()
        await _wait_for_port("127.0.0.1", REAL_MCP_PORT)
        LOGGER.info("MCP server ready")

        tool_service = components.tool_service
        task_factory: TaskRequestFactory = components.task_factory
        execution_engine = components.execution_engine

        if tool_service is None or task_factory is None:
            raise RuntimeError("Tool service and task factory must be enabled for this test.")

        progressive_tool = "real-streaming-server.progressive_search"
        user_context = UserContext(
            user_id="stream_mode_e2e",
            permissions=UserPermissions(permissions=[f"real-streaming-server.*"]),
        )
        system_prompt = (
            "You are a meticulous research assistant. Always begin by outlining a numbered plan. "
            "After planning, you MUST call the tool 'real-streaming-server.progressive_search' with "
            "the requested query and weave the tool output into the final answer."
        )

        creation_request = TaskRequest(
            task_id=f"stream_create_{uuid4().hex[:8]}",
            task_type="chat",
            description="Create agent for stream mode e2e",
            user_context=user_context,
            messages=[],
            agent_config=AgentConfig(
                agent_type="stream_mode_agent",
                system_prompt=system_prompt,
                model_config={
                    "model": settings.default_model,
                    "temperature": 0.1,
                    "tool_choice": {
                        "type": "function",
                        "function": {"name": "progressive_search"},
                    },
                },
                available_tools=[progressive_tool],
            ),
            metadata={"phase": "agent_creation"},
        )

        creation_result = await execution_engine.execute_task(creation_request)
        _log_json(
            "Agent creation result",
            {
                "status": creation_result.status.value if creation_result.status else None,
                "agent_id": creation_result.agent_id,
                "session_id": creation_result.session_id,
                "error": creation_result.error.to_dict() if creation_result.error else None,
            },
        )

        if creation_result.status != TaskStatus.SUCCESS:
            raise RuntimeError(f"Agent creation failed: {creation_result.error_message}")

        agent_id = creation_result.agent_id
        session_id = creation_result.session_id
        if not agent_id or not session_id:
            raise RuntimeError("Agent creation response missing identifiers.")

        live_request = await task_factory.create_live_chat_task(
            task_id=f"stream_live_{uuid4().hex[:8]}",
            description="Stream mode E2E conversation",
            user_context=user_context,
            messages=[
                UniversalMessage(
                    role="user",
                    content=(
                        "Research the latest AI streaming infrastructure updates. "
                        "1) Present a concise plan. "
                        "2) Call the progressive search tool with query 'AI streaming infrastructure updates'. "
                        "3) Summarize key findings."
                    ),
                    metadata={"requires_tool": True},
                )
            ],
            agent_type="stream_mode_agent",
            system_prompt=system_prompt,
            model_config={
                "model": settings.default_model,
                "temperature": 0.1,
                "tool_choice": {
                    "type": "function",
                    "function": {"name": "progressive_search"},
                },
            },
            tool_names=[progressive_tool],
            session_id=session_id,
            execution_metadata={"log_scope": "stream_mode_e2e"},
            task_metadata={"tool_expected": progressive_tool},
            agent_id=agent_id,
        )
        live_request.agent_id = agent_id
        live_request.session_id = session_id

        _log_json(
            "Live request summary",
            {
                "task_id": live_request.task_id,
                "agent_id": live_request.agent_id,
                "session_id": live_request.session_id,
                "tools": [progressive_tool],
                "execution_context": _serialize(live_request.execution_context),
                "metadata": live_request.metadata,
            },
        )

        if live_request.execution_context is None:
            raise RuntimeError("Live request missing execution context.")

        stream_session = await execution_engine.execute_task_live_session(
            live_request, live_request.execution_context
        )

        LOGGER.info("Streaming session started: task_id=%s", live_request.task_id)

        async for chunk in stream_session:
            chunk_payload = {
                "sequence_id": chunk.sequence_id,
                "chunk_type": chunk.chunk_type.value if chunk.chunk_type else None,
                "chunk_kind": chunk.chunk_kind,
                "is_final": chunk.is_final,
                "metadata": chunk.metadata,
            }
            LOGGER.info("Chunk >>> %s", json.dumps(chunk_payload, ensure_ascii=False))

            interaction = (chunk.metadata or {}).get("interaction_request")
            if interaction:
                interaction_id = interaction["interaction_id"]
                LOGGER.info("Approving tool proposal %s", interaction_id)
                await stream_session.approve_tool(
                    interaction_id,
                    approved=True,
                    user_message="Approved by stream mode e2e test script.",
                )

            if chunk.chunk_type in {TaskChunkType.RESPONSE, TaskChunkType.COMPLETE} and chunk.is_final:
                break

        await stream_session.close()
        LOGGER.info("Streaming session closed")

    finally:
        await shutdown_system(components)
        _stop_real_mcp_server(server_proc)


def main() -> None:
    _ensure_virtualenv()
    load_dotenv(PROJECT_ROOT / ".env.test")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    try:
        asyncio.run(run_stream_mode_e2e())
    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user.")


if __name__ == "__main__":
    main()
