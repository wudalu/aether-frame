from types import SimpleNamespace

import pytest

from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
from aether_frame.contracts import AgentRequest, TaskRequest, UniversalMessage


class MemoryServiceStub:
    def __init__(self):
        self.queries = []

    async def search_memory(self, *args, **kwargs):
        self.queries.append({"args": args, "kwargs": kwargs})
        return SimpleNamespace(
            results=[
                SimpleNamespace(text="Snippet A from memory."),
                SimpleNamespace(text="Snippet B from memory."),
            ]
        )


@pytest.mark.asyncio
async def test_execute_with_adk_runner_appends_memory_snippets(monkeypatch):
    agent = AdkDomainAgent(agent_id="agent-1", config={})
    memory_service = MemoryServiceStub()
    session_id = "session-1"

    agent.runtime_context = {
        "runner": object(),
        "session_id": session_id,
        "user_id": "user-123",
        "runner_context": {
            "memory_service": memory_service,
            "app_name": "test-app",
            "session_user_ids": {session_id: "user-123"},
        },
    }
    agent.adk_agent = object()

    async def fake_run(self, runner, user_id, session_id, adk_content):
        self._captured_adk_content = adk_content
        return adk_content

    monkeypatch.setattr(
        AdkDomainAgent, "_run_adk_with_runner_and_agent", fake_run
    )

    task_request = TaskRequest(
        task_id="task-123",
        task_type="chat",
        description="desc",
        messages=[UniversalMessage(role="user", content="Tell me about docs.")],
    )
    agent_request = AgentRequest(task_request=task_request)

    result = await agent._execute_with_adk_runner(agent_request)

    assert memory_service.queries, "memory search should be triggered"
    assert "Snippet A" in result.messages[0].content
    assert "[Retrieved Knowledge]" in agent._captured_adk_content
