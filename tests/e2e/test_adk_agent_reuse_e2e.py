from types import SimpleNamespace

import pytest

from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from src.aether_frame.contracts.configs import AgentConfig
from src.aether_frame.contracts.requests import TaskRequest
from src.aether_frame.contracts.contexts import UserContext


def _build_task_request(agent_config: AgentConfig, task_id: str) -> TaskRequest:
    return TaskRequest(
        task_id=task_id,
        task_type="e2e",
        description="ADK agent reuse flow",
        agent_config=agent_config,
        user_context=UserContext(user_id="reuser"),
    )


@pytest.mark.asyncio
async def test_adk_agent_reuse_flow(monkeypatch):
    adapter = AdkFrameworkAdapter()
    created_agents = []

    async def fake_create_domain_agent(agent_config, task_request=None):
        agent = SimpleNamespace(adk_agent=object(), runtime_context={})
        created_agents.append(agent)
        return agent

    monkeypatch.setattr(
        adapter,
        "_create_domain_agent_for_config",
        fake_create_domain_agent,
    )

    agent_config = AgentConfig(agent_type="assistant", system_prompt="Hello")

    first_context = await adapter._create_runtime_context_for_new_agent(
        _build_task_request(agent_config, "task-initial")
    )
    print(
        f"First agent created: agent_id={first_context.agent_id}, runner_id={first_context.runner_id}"
    )

    reuse_context = await adapter._create_runtime_context_for_new_agent(
        _build_task_request(agent_config, "task-reuse")
    )
    print(
        "Reused agent: agent_id=%s, runner_id=%s" % (reuse_context.agent_id, reuse_context.runner_id)
    )

    assert reuse_context.agent_id == first_context.agent_id
    assert reuse_context.runner_id == first_context.runner_id
    assert len(created_agents) == 1

    adapter.runner_manager.settings.max_sessions_per_agent = 1
    adapter.runner_manager.runners[first_context.runner_id]["sessions"] = {"existing": {}}

    overflow_context = await adapter._create_runtime_context_for_new_agent(
        _build_task_request(agent_config, "task-overflow")
    )
    print(
        "New agent created after threshold: agent_id=%s, runner_id=%s"
        % (overflow_context.agent_id, overflow_context.runner_id)
    )

    assert overflow_context.agent_id != first_context.agent_id
    assert overflow_context.runner_id != first_context.runner_id
    assert len(created_agents) == 2
