# -*- coding: utf-8 -*-
"""Tests for the base DomainAgent abstract class."""

import pytest

from aether_frame.agents.base.domain_agent import DomainAgent
from aether_frame.contracts import AgentRequest, TaskRequest, TaskResult, TaskStatus


class SimpleAgent(DomainAgent):
    async def initialize(self):
        self._initialized = True

    async def execute(self, agent_request: AgentRequest) -> TaskResult:
        return TaskResult(task_id=agent_request.task_request.task_id, status=TaskStatus.SUCCESS)

    async def get_state(self):
        return {}

    async def cleanup(self):
        self._initialized = False

    async def execute_live(self, task_request):
        return (), None


@pytest.mark.asyncio
async def test_domain_agent_defaults_and_validation():
    agent = SimpleAgent(agent_id="agent-x", config={})
    await agent.initialize()
    assert agent.is_initialized is True

    request = AgentRequest(task_request=TaskRequest(task_id="t1", task_type="chat", description="desc"))
    assert await agent.validate_request(request) is True

    result = await agent.execute(request)
    assert result.status == TaskStatus.SUCCESS

    await agent.cleanup()
    assert agent.is_initialized is False
