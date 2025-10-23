from types import SimpleNamespace

import pytest

from aether_frame.agents.adk.adk_domain_agent import AdkDomainAgent
from aether_frame.contracts import AgentRequest, FileReference, KnowledgeSource, TaskRequest, TaskStatus, UniversalMessage, UserContext
from aether_frame.framework.adk.adk_session_manager import AdkSessionManager


class MemoryServiceStub:
    def __init__(self):
        self.store_calls = []
        self.search_calls = []

    async def store_memory(self, *args, **kwargs):
        self.store_calls.append({"args": args, "kwargs": kwargs})

    async def search_memory(self, *args, **kwargs):
        self.search_calls.append({"args": args, "kwargs": kwargs})
        return SimpleNamespace(
            results=[
                SimpleNamespace(text="Knowledge snippet: docs overview."),
                SimpleNamespace(text="Knowledge snippet: docs deep dive."),
            ]
        )


class RunnerManagerStub:
    def __init__(self, memory_service: MemoryServiceStub):
        self.memory_service = memory_service
        self.agent_runner_mapping = {"agent-knowledge": "runner-1"}
        self.session_to_runner = {}
        self.settings = SimpleNamespace(
            default_app_name="test-app",
            default_user_id="user-knowledge",
        )
        self.runners = {
            "runner-1": {
                "sessions": {},
                "session_user_ids": {},
                "memory_service": memory_service,
                "app_name": "test-app",
                "user_id": "user-knowledge",
            }
        }

    async def get_runner_for_agent(self, agent_id: str) -> str:
        return self.agent_runner_mapping[agent_id]

    async def _create_session_in_runner(self, runner_id: str, task_request=None, external_session_id: str = None) -> str:
        session_id = external_session_id or "session-stub"
        runner_context = self.runners[runner_id]
        runner_context["sessions"][session_id] = object()
        if task_request and task_request.user_context:
            runner_context["session_user_ids"][session_id] = task_request.user_context.get_adk_user_id()
        self.session_to_runner[session_id] = runner_id
        return session_id

    async def get_runner_by_session(self, session_id: str):
        runner_id = self.session_to_runner.get(session_id)
        if not runner_id:
            return None
        return self.runners[runner_id]


@pytest.mark.asyncio
async def test_adk_knowledge_flow_integration(monkeypatch):
    memory_service = MemoryServiceStub()
    runner_manager = RunnerManagerStub(memory_service)
    session_manager = AdkSessionManager()

    knowledge = [
        KnowledgeSource(
            name="docs",
            source_type="vector_store",
            location="memory://docs",
            description="Primary documentation store",
        )
    ]

    task_request_initial = TaskRequest(
        task_id="initial",
        task_type="chat",
        description="Initial turn",
        agent_id="agent-knowledge",
        session_id="business-session",
        user_context=UserContext(user_id="user-knowledge"),
        available_knowledge=knowledge,
        attachments=[
            FileReference(
                file_path="uploads/design.docx",
                file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                metadata={"name": "design.docx"},
            )
        ],
    )

    coordination = await session_manager.coordinate_chat_session(
        chat_session_id=task_request_initial.session_id,
        target_agent_id=task_request_initial.agent_id,
        user_id=task_request_initial.user_context.get_adk_user_id(),
        task_request=task_request_initial,
        runner_manager=runner_manager,
    )

    assert coordination.adk_session_id in runner_manager.session_to_runner
    assert len(memory_service.store_calls) == 1, "Only knowledge should be stored"

    captured_adk_content = {}

    async def fake_run(self, runner, user_id, session_id, adk_content):
        captured_adk_content["content"] = adk_content
        return "assistant response"

    monkeypatch.setattr(
        AdkDomainAgent, "_run_adk_with_runner_and_agent", fake_run, raising=False
    )

    agent = AdkDomainAgent(agent_id="agent-knowledge", config={})
    agent.runtime_context = {
        "runner": object(),
        "session_id": coordination.adk_session_id,
        "user_id": "user-knowledge",
        "runner_context": runner_manager.runners["runner-1"],
    }
    agent.adk_agent = object()

    followup_request = TaskRequest(
        task_id="followup",
        task_type="chat",
        description="Follow-up",
        agent_id="agent-knowledge",
        session_id=task_request_initial.session_id,
        user_context=UserContext(user_id="user-knowledge"),
        messages=[UniversalMessage(role="user", content="Tell me about docs again.")],
        attachments=[
            FileReference(
                file_path="uploads/design.docx",
                file_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                metadata={"name": "design.docx"},
            )
        ],
    )

    agent_request = AgentRequest(task_request=followup_request)
    result = await agent._execute_with_adk_runner(agent_request)

    assert memory_service.search_calls, "Domain agent should query memory service"
    parts = getattr(captured_adk_content["content"], "parts", [])
    text_payload = "\n".join(getattr(part, "text", "") for part in parts)
    assert "[Retrieved Knowledge]" in text_payload
    assert "[Attachment]" in text_payload
    assert result.status == TaskStatus.SUCCESS
