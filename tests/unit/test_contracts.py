# -*- coding: utf-8 -*-
"""Tests for contract data structures."""

import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(project_root, "src"))

from aether_frame.contracts import (
    AgentConfig,
    AgentRequest,
    AgentResponse,
    AgentStatus,
    ContentPart,
    ExecutionConfig,
    ExecutionContext,
    ExecutionMode,
    FileReference,
    FrameworkType,
    ImageReference,
    KnowledgeSource,
    SessionContext,
    StrategyConfig,
    TaskComplexity,
    TaskRequest,
    TaskResult,
    TaskStatus,
    ToolCall,
    ToolRequest,
    ToolResult,
    ToolStatus,
    UniversalMessage,
    UniversalTool,
    UserContext,
)


class TestDataStructureCreation:
    """Test basic data structure creation and serialization."""

    def test_task_request_creation(self):
        """Test TaskRequest creation and basic operations."""
        user_context = UserContext(user_id="test_user", user_name="Test User")
        session_context = SessionContext(session_id="test_session")

        task_request = TaskRequest(
            task_id="test_001",
            task_type="chat",
            description="Test task description",
            user_context=user_context,
            session_context=session_context,
        )

        assert task_request.task_id == "test_001"
        assert task_request.task_type == "chat"
        assert task_request.description == "Test task description"
        assert task_request.user_context.user_id == "test_user"
        assert task_request.session_context.session_id == "test_session"

    def test_universal_message_creation(self):
        """Test UniversalMessage creation and ADK conversion."""
        message = UniversalMessage(
            role="user", content="Hello, world!", metadata={"test": "value"}
        )

        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.metadata == {"test": "value"}

    def test_tool_call_and_content_part(self):
        """Test ToolCall and ContentPart creation."""
        tool_call = ToolCall(
            tool_name="test_tool",
            parameters={"param1": "value1"},
            tool_namespace="test_namespace",
        )

        content_part = ContentPart(text="Some text", function_call=tool_call)

        assert tool_call.tool_name == "test_tool"
        assert tool_call.parameters == {"param1": "value1"}
        assert content_part.text == "Some text"
        assert content_part.function_call == tool_call

    def test_universal_tool_creation(self):
        """Test UniversalTool creation and ADK conversion."""
        tool = UniversalTool(
            name="test_tool",
            description="A test tool",
            parameters_schema={"type": "object", "properties": {}},
            namespace="test",
            required_permissions=["read"],
            supports_streaming=True,
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.required_permissions == ["read"]
        assert tool.supports_streaming is True

    def test_agent_config_creation(self):
        """Test AgentConfig creation."""
        config = AgentConfig(
            agent_type="conversational",
            system_prompt="You are a helpful conversational agent.",
            framework_type=FrameworkType.ADK,
            available_tools=["chat", "tool_use"],
            model_config={"model": "gpt-4", "temperature": 0.7},
            framework_config={"max_iterations": 10, "timeout": 300},
        )

        assert config.agent_type == "conversational"
        assert config.system_prompt == "You are a helpful conversational agent."
        assert config.framework_type == FrameworkType.ADK
        assert config.available_tools == ["chat", "tool_use"]
        assert config.model_config["model"] == "gpt-4"
        assert config.framework_config["max_iterations"] == 10
        assert config.framework_config["timeout"] == 300

    def test_execution_strategy_creation(self):
        """Test StrategyConfig creation."""
        strategy = StrategyConfig(
            strategy_name="simple_chat",
            applicable_task_types=["chat"],
            complexity_levels=[TaskComplexity.SIMPLE],
            execution_modes=[ExecutionMode.SYNC],
            target_framework=FrameworkType.ADK,
            agent_type="conversational",
        )

        assert strategy.strategy_name == "simple_chat"
        assert strategy.applicable_task_types == ["chat"]
        assert strategy.target_framework == FrameworkType.ADK
        assert strategy.agent_type == "conversational"


class TestADKCompatibility:
    """Test ADK compatibility features."""

    def test_user_context_adk_user_id(self):
        """Test UserContext ADK user ID generation."""
        # Test with explicit user_id
        user1 = UserContext(user_id="explicit_user")
        assert user1.get_adk_user_id() == "explicit_user"

        # Test with user_name
        user2 = UserContext(user_name="john_doe")
        assert user2.get_adk_user_id() == "user_john_doe"

        # Test with session_token
        user3 = UserContext(session_token="abc123456789")
        assert user3.get_adk_user_id() == "session_abc12345"

        # Test anonymous fallback
        user4 = UserContext()
        assert user4.get_adk_user_id() == "anonymous_user"

    def test_session_context_adk_session_id(self):
        """Test SessionContext ADK session ID retrieval."""
        # Test with session_id
        session1 = SessionContext(session_id="test_session")
        assert session1.get_adk_session_id() == "test_session"

        # Test with conversation_id fallback
        session2 = SessionContext(conversation_id="test_conversation")
        assert session2.get_adk_session_id() == "test_conversation"

        # Test with both (session_id takes precedence)
        session3 = SessionContext(session_id="session", conversation_id="conversation")
        assert session3.get_adk_session_id() == "session"

        # Test with neither
        session4 = SessionContext()
        assert session4.get_adk_session_id() is None

    def test_task_request_adk_conversion(self):
        """Test TaskRequest to ADK format conversion."""
        user_context = UserContext(user_id="test_user")
        session_context = SessionContext(session_id="test_session")
        message = UniversalMessage(role="user", content="Hello")
        tool = UniversalTool(name="test_tool", description="Test")
        knowledge = KnowledgeSource(
            name="test_kb", source_type="file", location="/test", description="Test KB"
        )

        task_request = TaskRequest(
            task_id="test_001",
            task_type="chat",
            description="Test task",
            user_context=user_context,
            session_context=session_context,
            messages=[message],
            available_tools=[tool],
            available_knowledge=[knowledge],
        )

        # Test basic task request properties
        assert task_request.task_id == "test_001"
        assert task_request.task_type == "chat"
        assert task_request.description == "Test task"
        assert len(task_request.messages) == 1
        assert len(task_request.available_tools) == 1
        assert len(task_request.available_knowledge) == 1


class TestComplexMessages:
    """Test complex message handling."""

    def test_universal_message_with_tool_calls(self):
        """Test UniversalMessage with tool calls."""
        tool_call = ToolCall(
            tool_name="search", parameters={"query": "test query"}, call_id="call_123"
        )

        message = UniversalMessage(
            role="assistant",
            content="I'll search for that information.",
            tool_calls=[tool_call],
        )

        # Test message properties
        assert message.role == "assistant"
        assert message.content == "I'll search for that information."
        assert len(message.tool_calls) == 1
        assert message.tool_calls[0].tool_name == "search"
        assert message.tool_calls[0].parameters == {"query": "test query"}

    def test_universal_message_with_content_parts(self):
        """Test UniversalMessage with multi-modal content."""
        text_part = ContentPart(text="Here is some text")
        tool_call = ToolCall(tool_name="get_weather", parameters={"city": "NYC"})
        function_part = ContentPart(function_call=tool_call)

        message = UniversalMessage(role="assistant", content=[text_part, function_part])

        # Test multi-modal content
        assert message.role == "assistant"
        assert isinstance(message.content, list)
        assert len(message.content) == 2
        assert message.content[0].text == "Here is some text"
        assert message.content[1].function_call.tool_name == "get_weather"
        assert message.content[1].function_call.parameters == {"city": "NYC"}


if __name__ == "__main__":
    # Run all tests
    print("🧪 Running Unit Tests for Data Contracts")
    print("=" * 50)

    test_creation = TestDataStructureCreation()
    test_adk = TestADKCompatibility()
    test_complex = TestComplexMessages()

    tests = [
        (test_creation, "test_task_request_creation"),
        (test_creation, "test_universal_message_creation"),
        (test_creation, "test_tool_call_and_content_part"),
        (test_creation, "test_universal_tool_creation"),
        (test_creation, "test_agent_config_creation"),
        (test_creation, "test_execution_strategy_creation"),
        (test_adk, "test_user_context_adk_user_id"),
        (test_adk, "test_session_context_adk_session_id"),
        (test_adk, "test_task_request_adk_conversion"),
        (test_complex, "test_universal_message_with_tool_calls"),
        (test_complex, "test_universal_message_with_content_parts"),
    ]

    passed = 0
    failed = 0

    for test_obj, test_method in tests:
        try:
            getattr(test_obj, test_method)()
            print(f"✅ {test_method}")
            passed += 1
        except Exception as e:
            print(f"❌ {test_method}: {e}")
            failed += 1

    print("=" * 50)
    print(f"📊 Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("🎉 All unit tests passed!")
    else:
        print("⚠️  Some tests failed")
