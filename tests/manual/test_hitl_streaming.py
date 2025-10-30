#!/usr/bin/env python3
"""
Manual HITL streaming test for DeepSeek.

Runs a single live session that forces a tool proposal, waits for the
interaction request chunk, and programmatically sends an approval
response via the communicator to verify that the pipeline resumes and
completes cleanly.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import Optional
from uuid import uuid4

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_MCP_SERVER_PATH = PROJECT_ROOT / "tests" / "tools" / "mcp" / "real_streaming_server.py"
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
    """Poll until the TCP port becomes available."""
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
        [sys.executable, str(REAL_MCP_SERVER_PATH)],
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


async def run_hitl_stream() -> None:
    from aether_frame.bootstrap import create_system_components, shutdown_system
    from aether_frame.config.settings import Settings
    from aether_frame.contracts import (
        AgentConfig,
        ExecutionContext,
        FrameworkType,
        InteractionResponse,
        InteractionType,
        TaskChunkType,
        TaskRequest,
        TaskStatus,
        UniversalMessage,
        UserContext,
    )

    settings = Settings()
    settings.default_model = os.getenv("HITL_TEST_MODEL", os.getenv("DEFAULT_MODEL", "deepseek-chat"))
    settings.enable_mcp_tools = True
    settings.mcp_servers = [
        {
            "name": "real-streaming-server",
            "endpoint": "http://localhost:8002/mcp",
        }
    ]

    components = await create_system_components(settings)
    server_proc = None
    try:
        server_proc = _start_real_mcp_server()
        await _wait_for_port("127.0.0.1", REAL_MCP_PORT)

        adk_adapter = await components.framework_registry.get_adapter(FrameworkType.ADK)
        if not adk_adapter:
            raise RuntimeError("ADK adapter unavailable.")
        adk_adapter._config.setdefault("tool_approval_timeout_seconds", 30.0)
        adk_adapter._config.setdefault("tool_approval_timeout_policy", "auto_cancel")

        progressive_tool = "real-streaming-server.progressive_search"
        user_context = UserContext(user_id="hitl_tester")
        system_prompt = (
            "You are a meticulous research assistant. Always begin by outlining a numbered plan. "
            "After planning, you MUST call the tool 'real-streaming-server.progressive_search' with the "
            "requested query before giving your final answer."
        )

        creation_request = TaskRequest(
            task_id=f"hitl_create_{uuid4().hex[:8]}",
            task_type="chat",
            description="Create DeepSeek agent for HITL streaming test",
            messages=[],
            agent_config=AgentConfig(
                agent_type="hitl_stream_tester",
                system_prompt=system_prompt,
                model_config={
                    "model": settings.default_model,
                    "temperature": 0.1,
                    "tool_choice": {
                        "type": "function",
                        "function": {"name": progressive_tool},
                    },
                },
                available_tools=[progressive_tool],
            ),
            user_context=user_context,
            metadata={"phase": "agent_creation"},
        )

        creation_result = await components.execution_engine.execute_task(creation_request)
        if creation_result.status != TaskStatus.SUCCESS:
            raise RuntimeError(f"Agent creation failed: {creation_result.error_message}")

        agent_id = creation_result.agent_id
        session_id = creation_result.session_id or creation_result.metadata.get("chat_session_id")
        if not agent_id or not session_id:
            raise RuntimeError("Agent creation response missing identifiers.")

        message = UniversalMessage(
            role="user",
            content=(
                "Research recent AI streaming infrastructure updates. "
                "1) Present a plan labeled 'Plan Step:'. "
                "2) Call the progressive_search tool with query 'AI streaming infrastructure updates'. "
                "3) Summarize the findings concisely."
            ),
            metadata={"requires_tool": True},
        )

        live_request = TaskRequest(
            task_id=f"hitl_live_{uuid4().hex[:8]}",
            task_type="chat",
            description="HITL streaming conversation",
            messages=[message],
            agent_id=agent_id,
            session_id=session_id,
            user_context=user_context,
            metadata={"phase": "live_execution", "tool_expected": progressive_tool},
        )

        execution_context = ExecutionContext(
            execution_id=f"hitl_exec_{uuid4().hex[:8]}",
            framework_type=FrameworkType.ADK,
            execution_mode="live",
        )

        live_stream, communicator = await components.execution_engine.execute_task_live(
            live_request, execution_context
        )

        tool_proposal_seen = False
        reminder_sent = False

        try:
            async for chunk in live_stream:
                chunk_summary = {
                    "sequence_id": chunk.sequence_id,
                    "type": chunk.chunk_type.value if chunk.chunk_type else None,
                    "is_final": chunk.is_final,
                    "metadata": chunk.metadata,
                }
                print(f"🔸 Chunk: {json.dumps(chunk_summary, ensure_ascii=False)}")

                if chunk.chunk_type == TaskChunkType.TOOL_PROPOSAL:
                    tool_proposal_seen = True

                interaction = (chunk.metadata or {}).get("interaction_request")
                if interaction:
                    print("⚠️  Tool approval required; sending automated approval.")
                    response = InteractionResponse(
                        interaction_id=interaction["interaction_id"],
                        interaction_type=InteractionType(interaction["interaction_type"]),
                        approved=True,
                        user_message="Approved by HITL streaming test script.",
                    )
                    await communicator.send_user_response(response)

                if (
                    not tool_proposal_seen
                    and not reminder_sent
                    and chunk.sequence_id >= 10
                    and chunk.chunk_type == TaskChunkType.PROGRESS
                ):
                    reminder_sent = True
                    await communicator.send_user_message(
                        "Reminder: you must call the tool real-streaming-server.progressive_search "+
                        "with the query 'AI streaming infrastructure updates' before completing."
                    )

                if chunk.is_final and chunk.chunk_type in {TaskChunkType.RESPONSE, TaskChunkType.COMPLETE}:
                    break
        finally:
            communicator.close()

        if not tool_proposal_seen:
            raise RuntimeError("Tool proposal was not observed; HITL flow did not trigger as expected.")

        print("✅ HITL streaming session completed with tool proposal and approval.")

    finally:
        await shutdown_system(components)
        _stop_real_mcp_server(server_proc)


def main() -> None:
    _ensure_virtualenv()
    load_dotenv(PROJECT_ROOT / ".env.test")

    try:
        asyncio.run(run_hitl_stream())
    except KeyboardInterrupt:
        print("Interrupted by user.")


if __name__ == "__main__":
    main()
