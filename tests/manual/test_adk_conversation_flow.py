#!/usr/bin/env python3
"""
Manual end-to-end conversation flow test for ADK using real DeepSeek model.

Steps:
1. Load .env.test configuration and configure global logging (writes to logs/aether-frame-test.log).
2. Bootstrap the system via create_ai_assistant.
3. Create an agent (creation mode).
4. Run a single-turn conversation with a custom business session ID.
5. Run a multi-turn conversation (multiple sequential requests) using another custom session ID.

All framework and script logs are emitted to the log file configured via .env.test,
and key milestones are printed to stdout for quick inspection.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import List
from uuid import uuid4

from dotenv import load_dotenv

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.bootstrap import create_ai_assistant  # noqa: E402
from aether_frame.config.logging import setup_logging as configure_logging  # noqa: E402
from aether_frame.config.settings import Settings  # noqa: E402
from aether_frame.contracts import (  # noqa: E402
    AgentConfig,
    TaskRequest,
    TaskStatus,
    UniversalMessage,
    UserContext,
)


async def run_conversation(
    assistant,
    agent_id: str,
    session_id: str,
    user_messages: List[str],
    user_context: UserContext,
    logger: logging.Logger,
) -> None:
    """Run sequential conversation requests using the same agent and session."""
    for idx, message in enumerate(user_messages, start=1):
        task_id = f"manual_conversation_{idx}_{datetime.now().strftime('%H%M%S')}"
        request = TaskRequest(
            task_id=task_id,
            task_type="chat",
            description=f"Manual conversation step {idx}",
            messages=[UniversalMessage(role="user", content=message)],
            agent_id=agent_id,
            session_id=session_id,
            user_context=user_context,
            metadata={
                "source": "manual_conversation_flow",
                "step": idx,
                "timestamp": datetime.now().isoformat(),
            },
        )

        logger.info(
            "Submitting conversation request",
            extra={
                "task_id": task_id,
                "chat_session_id": session_id,
                "agent_id": agent_id,
                "user_message": message,
            },
        )
        result = await assistant.process_request(request)

        if result.status != TaskStatus.SUCCESS:
            logger.error(
                "Conversation step failed",
                extra={
                    "task_id": task_id,
                    "chat_session_id": session_id,
                    "agent_id": agent_id,
                    "status": result.status.value if hasattr(result.status, "value") else result.status,
                    "error_message": result.error_message,
                },
            )
            raise RuntimeError(f"Conversation step {idx} failed: {result.error_message}")

        response_preview = (
            result.messages[-1].content[:120] + "..."
            if result.messages and len(result.messages[-1].content) > 120
            else (result.messages[-1].content if result.messages else "<no response>")
        )
        logger.info(
            "Conversation step completed",
            extra={
                "task_id": task_id,
                "chat_session_id": session_id,
                "agent_id": agent_id,
                "step": idx,
                "response_preview": response_preview,
            },
        )
        print(f"[Conversation step {idx}] Response: {response_preview}")


async def main(models: List[str]) -> None:
    """Execute the manual test."""
    # Load test environment configuration (.env.test)
    load_dotenv(".env.test")
    settings = Settings()

    # Configure global logging based on settings
    configure_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        log_file_path=settings.log_file_path,
    )
    logger = logging.getLogger("manual_adk_conversation_flow")
    logger.info(
        "Manual ADK conversation flow test started",
        extra={"log_file_path": settings.log_file_path, "selected_models": models},
    )

    print("=" * 80)
    print("Manual ADK Conversation Flow Test")
    print("=" * 80)
    print(f"Global log file: {settings.log_file_path}")

    # Initialize assistant via bootstrap
    assistant = await create_ai_assistant(settings)
    print("✓ System bootstrap complete and AI assistant initialized.")
    logger.info("AI assistant initialized via bootstrap")

    user_context = UserContext(user_id="manual_conversation_user")
    model_name = models[0] if models else settings.default_model
    logger.info("Using model for manual conversation", extra={"model": model_name})

    # Step 1: Create agent (creation mode)
    creation_task_id = f"manual_create_{datetime.now().strftime('%H%M%S')}"
    creation_request = TaskRequest(
        task_id=creation_task_id,
        task_type="chat",
        description="Manual test agent creation",
        agent_config=AgentConfig(
            agent_type="manual_conversation_assistant",
            system_prompt="You are a helpful assistant for manual end-to-end testing.",
            model_config={"model": model_name, "temperature": 0.5},
            framework_config={"provider": "deepseek"},
        ),
        messages=[
            UniversalMessage(
                role="user",
                content="Initialize yourself for manual conversation testing.",
            )
        ],
        user_context=user_context,
        metadata={
            "source": "manual_conversation_flow",
            "phase": "agent_creation",
            "timestamp": datetime.now().isoformat(),
        },
    )

    logger.info("Submitting agent creation request", extra={"task_id": creation_task_id})
    creation_result = await assistant.process_request(creation_request)
    if creation_result.status != TaskStatus.SUCCESS or not creation_result.agent_id:
        raise RuntimeError(
            f"Agent creation failed: status={creation_result.status}, "
            f"error={creation_result.error_message}"
        )

    agent_id = creation_result.agent_id
    print(f"✓ Agent created successfully: {agent_id}")
    logger.info("Agent creation succeeded", extra={"agent_id": agent_id})

    # Step 2: Single conversation with custom session ID
    session_id = f"manual_session_{uuid4().hex[:12]}"
    print(f"-> Running single conversation with session_id={session_id}")
    logger.info(
        "Starting single-turn conversation",
        extra={"chat_session_id": session_id, "agent_id": agent_id},
    )
    await run_conversation(
        assistant,
        agent_id,
        session_id,
        ["Hello! Please confirm you are ready for testing."],
        user_context,
        logger,
    )
    logger.info(
        "Single-round conversation finished",
        extra={"chat_session_id": session_id, "agent_id": agent_id},
    )

    # Step 3: Multi-turn conversation with another session ID
    multi_session_id = f"manual_multi_session_{uuid4().hex[:12]}"
    print(f"-> Running multi-turn conversation with session_id={multi_session_id}")
    multi_messages = [
        "Hi assistant, what's the current date?",
        "Can you give me a short motivational quote?",
        "Thanks! Any quick productivity tip?",
    ]
    logger.info(
        "Starting multi-turn conversation",
        extra={
            "chat_session_id": multi_session_id,
            "agent_id": agent_id,
            "planned_turns": len(multi_messages),
        },
    )
    await run_conversation(
        assistant,
        agent_id,
        multi_session_id,
        multi_messages,
        user_context,
        logger,
    )
    logger.info(
        "Multi-turn conversation finished",
        extra={"chat_session_id": multi_session_id, "agent_id": agent_id, "turns": len(multi_messages)},
    )

    print("✓ Manual ADK conversation flow test completed successfully.")
    logger.info(
        "Manual ADK conversation flow test completed successfully",
        extra={"agent_id": agent_id},
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual ADK conversation flow test.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["deepseek-chat"],
        help="List of model names to test (first will be used).",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.models))
    except KeyboardInterrupt:
        print("Test interrupted by user.")
    except Exception as exc:
        logging.getLogger("manual_adk_conversation_flow").exception(
            "Manual ADK conversation flow test failed: %s", exc
        )
        raise
