# -*- coding: utf-8 -*-
"""Tests for AdkAgentHooks behavior."""

import pytest

from aether_frame.agents.adk.adk_agent_hooks import AdkAgentHooks
from aether_frame.contracts import AgentRequest, TaskRequest, TaskResult, TaskStatus


class StubAgent:
    def __init__(self):
        self.adk_agent = None


@pytest.mark.asyncio
async def test_hooks_handle_lifecycle_without_dependencies():
    hooks = AdkAgentHooks(StubAgent())
    await hooks.on_agent_created()
    await hooks.on_agent_destroyed()


@pytest.mark.asyncio
async def test_hooks_pre_and_post_execution():
    hooks = AdkAgentHooks(StubAgent())
    request = AgentRequest(task_request=TaskRequest(task_id="t1", task_type="chat", description="desc"))
    result = TaskResult(task_id="t1", status=TaskStatus.SUCCESS)

    await hooks.before_execution(request)
    await hooks.after_execution(request, result)


@pytest.mark.asyncio
async def test_hooks_on_error():
    hooks = AdkAgentHooks(StubAgent())
    request = AgentRequest(task_request=TaskRequest(task_id="t2", task_type="chat", description="desc"))
    await hooks.on_error(request, RuntimeError("boom"))
