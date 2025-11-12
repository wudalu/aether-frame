# -*- coding: utf-8 -*-
"""Reusable builders for contracts used across unit tests."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from aether_frame.contracts import (
    ExecutionContext,
    FrameworkType,
    TaskRequest,
    TaskResult,
    TaskStatus,
    UniversalMessage,
    UniversalTool,
)
from aether_frame.contracts.configs import AgentConfig, ExecutionConfig
from aether_frame.contracts.enums import ExecutionMode
from aether_frame.contracts.contexts import SessionContext, UserContext


def make_message(
    content: str = "Hello there!",
    role: str = "user",
    *,
    author: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> UniversalMessage:
    """Create a simple UniversalMessage."""
    return UniversalMessage(
        role=role,
        content=content,
        author=author,
        metadata=dict(metadata or {}),
    )


def make_execution_context(
    execution_id: str = "exec-1",
    framework_type: FrameworkType = FrameworkType.ADK,
    execution_mode: str = "sync",
    *,
    timeout: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ExecutionContext:
    """Create an ExecutionContext with sensible defaults."""
    return ExecutionContext(
        execution_id=execution_id,
        framework_type=framework_type,
        execution_mode=execution_mode,
        timeout=timeout,
        metadata=dict(metadata or {}),
    )


def make_execution_config(
    *,
    execution_mode: ExecutionMode = ExecutionMode.SYNC,
    max_retries: int = 3,
    enable_logging: bool = True,
    enable_monitoring: bool = True,
) -> ExecutionConfig:
    """Create an ExecutionConfig helper."""
    return ExecutionConfig(
        execution_mode=execution_mode,
        max_retries=max_retries,
        enable_logging=enable_logging,
        enable_monitoring=enable_monitoring,
    )


def make_universal_tool(
    name: str = "builtin.echo",
    description: str = "Echo tool",
    *,
    namespace: Optional[str] = None,
    supports_streaming: bool = False,
    parameters_schema: Optional[Dict[str, Any]] = None,
) -> UniversalTool:
    """Create a UniversalTool stub."""
    return UniversalTool(
        name=name,
        description=description,
        namespace=namespace,
        supports_streaming=supports_streaming,
        parameters_schema=dict(parameters_schema or {}),
    )


def make_agent_config(
    agent_type: str = "support_agent",
    system_prompt: str = "You are helpful.",
    *,
    available_tools: Optional[Iterable[str]] = None,
    framework_config: Optional[Dict[str, Any]] = None,
) -> AgentConfig:
    """Create an AgentConfig with lightweight defaults."""
    return AgentConfig(
        agent_type=agent_type,
        system_prompt=system_prompt,
        available_tools=list(available_tools or []),
        framework_config=dict(framework_config or {}),
    )


def make_task_request(
    task_id: str = "task-1",
    task_type: str = "chat",
    description: str = "Handle a sample task",
    *,
    messages: Optional[Iterable[UniversalMessage]] = None,
    available_tools: Optional[Iterable[UniversalTool]] = None,
    available_knowledge: Optional[Iterable[Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    agent_config: Optional[AgentConfig] = None,
    execution_context: Optional[ExecutionContext] = None,
    execution_config: Optional[ExecutionConfig] = None,
    user_context: Optional[UserContext] = None,
    session_context: Optional[SessionContext] = None,
) -> TaskRequest:
    """Create a TaskRequest populated with provided overrides."""
    return TaskRequest(
        task_id=task_id,
        task_type=task_type,
        description=description,
        messages=list(messages or [make_message()]),
        available_tools=list(available_tools or []),
        available_knowledge=list(available_knowledge or []),
        metadata=dict(metadata or {}),
        session_id=session_id,
        agent_id=agent_id,
        agent_config=agent_config,
        execution_context=execution_context,
        execution_config=execution_config,
        user_context=user_context,
        session_context=session_context,
    )


def make_task_result(
    task_id: str = "task-1",
    status: TaskStatus = TaskStatus.SUCCESS,
    *,
    messages: Optional[Iterable[UniversalMessage]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> TaskResult:
    """Create a TaskResult shortcut."""
    return TaskResult(
        task_id=task_id,
        status=status,
        messages=list(messages or []),
        metadata=dict(metadata or {}),
        session_id=session_id,
        agent_id=agent_id,
    )
