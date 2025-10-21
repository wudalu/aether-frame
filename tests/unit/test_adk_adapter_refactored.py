# -*- coding: utf-8 -*-
"""Unit tests for refactored ADK Framework Adapter."""

from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.aether_frame.contracts import (
    AgentConfig,
    ExecutionContext,
    FrameworkType,
    LiveExecutionResult,
    TaskRequest,
    TaskResult,
    TaskStatus,
    TaskComplexity,
)
from src.aether_frame.execution.task_router import ExecutionStrategy
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter

"""
=== ADK ADAPTER FUNCTION ANALYSIS ===

This file contains comprehensive analysis of all functions in ADK Framework Adapter,
including their purpose, call chains, and whether they're in the main execution path.

LAST UPDATED: 2025-01-15
ANALYSIS VERSION: v1.0 - Post-Session-Refactor

=== PUBLIC INTERFACE METHODS (Main Call Chain) ===

1. __init__(self)
   PURPOSE: Initialize adapter with session-based architecture
   CALL CHAIN: FrameworkRegistry -> AdkFrameworkAdapter() -> __init__
   MAIN PATH: ✅ YES - Required for adapter creation
   CHANGES: Updated to use session-based management instead of task-based
   
2. async def initialize(self, config: Optional[Dict[str, Any]] = None)
   PURPOSE: Initialize ADK session service with STRONG DEPENDENCY CHECKING
   CALL CHAIN: FrameworkRegistry._initialize_adapter() -> adapter.initialize()
   MAIN PATH: ✅ YES - Required before any task execution
   CHANGES: 🔄 MAJOR REFACTOR - Now implements strong dependency checking
   BEHAVIOR: Raises RuntimeError if ADK dependencies not available (system should fail to start)
   
3. def is_ready(self) -> bool  [REPLACES is_available]
   PURPOSE: Check if adapter is ready for task execution (not availability)
   CALL CHAIN: Internal readiness checks
   MAIN PATH: ⚠️ SECONDARY - Readiness verification, not availability
   CHANGES: 🆕 NEW METHOD - Replaces problematic is_available concept
   PURPOSE: Execute task through session-based persistent agents
   CALL CHAIN: TaskRouter -> FrameworkAdapter.execute_task() -> AdkAdapter.execute_task()
   MAIN PATH: ✅ YES - Core execution method
   CHANGES: Major refactor - now uses session-based agent lifecycle
   FLOW: extract_session_id -> get_or_create_session_agent -> domain_agent.execute
4. async def execute_task(self, task_request: TaskRequest, strategy: ExecutionStrategy) -> TaskResult
   PURPOSE: Execute task in live/streaming mode with persistent session agents
   CALL CHAIN: TaskRouter -> FrameworkAdapter.execute_task_live() -> AdkAdapter.execute_task_live()
   MAIN PATH: ✅ YES - Live execution method
   CHANGES: No longer cleans up agent after communication ends
5. async def execute_task_live(self, task_request: TaskRequest, context: ExecutionContext) -> LiveExecutionResult
   PURPOSE: Check if ADK framework is available and initialized
   CALL CHAIN: FrameworkRegistry.get_available_frameworks() -> adapter.is_available()
   MAIN PATH: ✅ YES - Used for framework selection
   CHANGES: None
6. async def shutdown(self)
   PURPOSE: Cleanup all session agents and runners
   CALL CHAIN: FrameworkRegistry.shutdown_all_adapters() -> adapter.shutdown()
   MAIN PATH: ✅ YES - Required for clean shutdown
   CHANGES: Now cleans up session agents and session runners
   
7. async def get_capabilities(self) -> List[str]
   PURPOSE: Return ADK framework capabilities
   CALL CHAIN: FrameworkRegistry.get_framework_status() -> adapter.get_capabilities()
   MAIN PATH: ⚠️ SECONDARY - Used for metadata/status reporting
   CHANGES: None
   
8. async def health_check(self) -> Dict[str, Any]
   PURPOSE: Return health status and metrics
   CALL CHAIN: FrameworkRegistry.get_framework_status() -> adapter.health_check()
   MAIN PATH: ⚠️ SECONDARY - Used for monitoring
   CHANGES: Now reports active_sessions instead of active_agents
   
=== SESSION MANAGEMENT METHODS (Core Architecture) ===

9. def _extract_session_id(self, task_request: TaskRequest) -> str
   PURPOSE: Extract or generate session ID for agent lifecycle management
   CALL CHAIN: execute_task -> _extract_session_id
   MAIN PATH: ✅ YES - Critical for session-based architecture
   CHANGES: ✨ NEW METHOD - Implements session ID extraction logic
   
10. async def _get_or_create_session_agent(self, session_id, task_request, strategy) -> "AdkDomainAgent"
    PURPOSE: Get existing session agent or create new one (core ADK pattern)
    CALL CHAIN: execute_task -> _get_or_create_session_agent
    MAIN PATH: ✅ YES - Core session management
    CHANGES: ✨ NEW METHOD - Implements persistent agent per session
    
11. async def _create_session_domain_agent(self, session_id, agent_config, session_config) -> "AdkDomainAgent"
    PURPOSE: Create domain agent with session-specific configuration and Runner
    CALL CHAIN: _get_or_create_session_agent -> _create_session_domain_agent
    MAIN PATH: ✅ YES - Agent creation with session context
    CHANGES: ✨ NEW METHOD - Integrates session config into agent creation
    
12. async def _create_session_runner(self, session_id, domain_agent, session_config)
    PURPOSE: Create ADK Runner for specific session (Runner per session pattern)
    CALL CHAIN: _create_session_domain_agent -> _create_session_runner
    MAIN PATH: ✅ YES - Required for proper ADK Runner-Agent binding
    CHANGES: ✨ NEW METHOD - Each session gets its own Runner
    
13. async def _cleanup_session(self, session_id: str) -> bool
    PURPOSE: Cleanup session agent and associated Runner
    CALL CHAIN: shutdown -> _cleanup_session, cleanup_session_by_id -> _cleanup_session
    MAIN PATH: ✅ YES - Session lifecycle management
    CHANGES: ✨ NEW METHOD - Proper session resource cleanup
    
14. async def cleanup_session_by_id(self, session_id: str) -> bool
    PURPOSE: Public method to explicitly end sessions
    CALL CHAIN: External components -> cleanup_session_by_id
    MAIN PATH: ⚠️ SECONDARY - For explicit session termination
    CHANGES: ✨ NEW METHOD - Public interface for session cleanup

=== CONTEXT AND CONFIGURATION METHODS ===

15. def _convert_contexts_to_session_config(self, task_request: TaskRequest) -> Dict[str, Any]
    PURPOSE: Convert TaskRequest contexts to comprehensive ADK Session configuration
    CALL CHAIN: _get_or_create_session_agent -> _convert_contexts_to_session_config
    MAIN PATH: ✅ YES - Context integration is essential
    CHANGES: Previously unused, now properly integrated
    
16. def _build_agent_config_from_task(self, task_request, strategy) -> AgentConfig
    PURPOSE: Build agent configuration from task request
    CALL CHAIN: _get_or_create_session_agent -> _build_agent_config_from_task
    MAIN PATH: ✅ YES - Agent configuration
    CHANGES: None
    
17. def _build_system_prompt_from_task(self, task_request: TaskRequest) -> str
    PURPOSE: Build system prompt from task context
    CALL CHAIN: _build_agent_config_from_task -> _build_system_prompt_from_task
    MAIN PATH: ✅ YES - System prompt configuration
    CHANGES: None
    
18. def _extract_model_configuration(self, task_request: TaskRequest) -> str
    PURPOSE: Extract model configuration with priority order
    CALL CHAIN: _build_agent_config_from_task -> _extract_model_configuration
    MAIN PATH: ✅ YES - Model selection
    CHANGES: None
    
19. def _extract_tool_permissions(self, task_request: TaskRequest) -> list
    PURPOSE: Extract tool permissions from task request
    CALL CHAIN: _build_agent_config_from_task -> _extract_tool_permissions
    MAIN PATH: ✅ YES - Tool access control
    CHANGES: None

=== LEGACY COMPATIBILITY METHODS ===

20. async def _create_domain_agent(self, agent_id: str, agent_config: AgentConfig) -> "AdkDomainAgent"
    PURPOSE: Legacy method for backward compatibility
    CALL CHAIN: Legacy code -> _create_domain_agent
    MAIN PATH: ❌ NO - Legacy compatibility only
    CHANGES: ♻️ REFACTORED - Now delegates to session-based creation
    
21. async def _cleanup_agent(self, agent_id: str) -> bool
    PURPOSE: Legacy cleanup method
    CALL CHAIN: Legacy code -> _cleanup_agent
    MAIN PATH: ❌ NO - Legacy compatibility only
    CHANGES: ♻️ REFACTORED - Now delegates to session cleanup

=== ARCHITECTURE SUMMARY ===

CORE EXECUTION FLOW (Main Path):
1. FrameworkRegistry.initialize() -> adapter.initialize() [STRONG DEPENDENCY CHECK]
2. TaskRouter.execute() -> adapter.execute_task()
3. _extract_session_id() -> _get_or_create_session_agent()
4. _create_session_domain_agent() -> _create_session_runner()
5. domain_agent.execute() -> TaskResult

SESSION LIFECYCLE:
- Session agents persist across multiple tasks
- Each session has its own Runner instance
- Sessions cleaned up explicitly or at shutdown

ARCHITECTURE COMPLIANCE:
✅ Follows ADK session-based pattern
✅ One persistent agent per conversation
✅ Runner per session for proper isolation
✅ Context integration through session config
✅ Proper resource cleanup
✅ Strong dependency checking (no optional ADK)

FUNCTION COUNT: 20 total functions (removed is_available)
- Main path: 12 functions
- Secondary: 3 functions
- Legacy: 2 functions
- New methods: 7 functions (added is_ready)
- Refactored: 3 methods

CRITICAL CHANGES:
- ❌ REMOVED: is_available() concept for core frameworks
- ✨ ADDED: Strong dependency checking in initialize()
- ✨ ADDED: is_ready() for readiness verification
- 🔄 UPDATED: Bootstrap process fails fast if ADK unavailable

"""


@pytest.fixture
def adk_adapter():
    """Create ADK adapter instance for testing."""
    return AdkFrameworkAdapter()


@pytest.fixture
def sample_task_request():
    """Create sample task request for testing."""
    return TaskRequest(
        task_id="test_task_001",
        task_type="chat",
        description="Test task description",
        metadata={
            "temperature": 0.8,
            "max_tokens": 500,
            "preferred_model": "gemini-1.5-flash",
        },
        available_tools=[],
        available_knowledge=[],
        user_context=None,
        session_context=None,
        execution_context=ExecutionContext(
            execution_id="exec_001",
            execution_mode="sync",
            trace_id="trace_001",
            framework_type=FrameworkType.ADK,
        ),
    )


@pytest.fixture
def sample_execution_strategy():
    """Create sample execution strategy."""
    return ExecutionStrategy(
        framework_type=FrameworkType.ADK,
        task_complexity=TaskComplexity.MODERATE,
        execution_config={},
        runtime_options={},
        execution_mode="sync",
    )


class TestAdkFrameworkAdapterRefactored:
    """Test suite for refactored ADK Framework Adapter."""

    def test_initialization(self, adk_adapter):
        """Test adapter initialization - validates session-based architecture setup."""
        assert adk_adapter.framework_type == FrameworkType.ADK
        assert not adk_adapter._initialized
        # Verify session-based architecture (not task-based) with independent contexts
        assert len(adk_adapter._session_agents) == 0
        assert len(adk_adapter._session_contexts) == 0

    @pytest.mark.asyncio
    async def test_initialize_with_strong_dependency_checking(self, adk_adapter):
        """Test initialization with strong ADK dependency checking."""
        pytest.importorskip("google.adk.runners")
        # ADK initialization should succeed or fail completely
        await adk_adapter.initialize()

        assert adk_adapter._initialized

    @pytest.mark.asyncio
    async def test_initialize_failure_raises_exception(self, adk_adapter):
        """Test that ADK initialization failure raises RuntimeError."""
        import builtins

        original_import = builtins.__import__

        def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.startswith("google.adk"):
                raise ImportError("ADK not found")
            return original_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=failing_import):
            with pytest.raises(RuntimeError, match="ADK framework is required"):
                await adk_adapter.initialize()

    def test_is_ready_method(self, adk_adapter):
        """Test is_ready method replaces is_available for readiness checking."""
        # Before initialization
        assert not adk_adapter.is_ready()

        # Mock initialized state
        adk_adapter._initialized = True

        assert adk_adapter.is_ready()

    @pytest.mark.asyncio
    async def test_get_capabilities(self, adk_adapter):
        """Test capabilities reporting - secondary path method."""
        capabilities = await adk_adapter.get_capabilities()

        expected_capabilities = [
            "conversational_agents",
            "memory_management",
            "observability",
            "tool_integration",
            "session_management",
            "state_persistence",
        ]

        assert capabilities == expected_capabilities

    @pytest.mark.asyncio
    async def test_health_check(self, adk_adapter):
        """Test health check functionality - secondary path method."""
        # Before initialization
        health = await adk_adapter.health_check()
        assert health["framework"] == "adk"
        assert health["status"] == "not_initialized"
        # Verify reports session count, not agent count
        assert health["active_sessions"] == 0

        # After initialization
        pytest.importorskip("google.adk.runners")
        await adk_adapter.initialize()
        health = await adk_adapter.health_check()
        assert health["status"] == "healthy"

    def test_session_id_extraction_ensures_user_isolation(
        self, adk_adapter, sample_task_request
    ):
        """Test session ID extraction ensures proper user isolation - CRITICAL SECURITY."""
        from src.aether_frame.contracts import SessionContext, UserContext

        # Test 1: Different users with same session_context.session_id should get different session_ids
        sample_task_request.user_context = UserContext(user_id="alice")
        sample_task_request.session_context = SessionContext(session_id="chat_123")
        alice_session_id = adk_adapter._extract_session_id(sample_task_request)

        sample_task_request.user_context = UserContext(user_id="bob")
        sample_task_request.session_context = SessionContext(
            session_id="chat_123"
        )  # Same session_id!
        bob_session_id = adk_adapter._extract_session_id(sample_task_request)

        # CRITICAL: Must be different to prevent session leakage
        assert alice_session_id != bob_session_id
        assert alice_session_id == "alice:chat_123"
        assert bob_session_id == "bob:chat_123"

        # Test 2: Same user with different session_context.session_id should get different session_ids
        sample_task_request.user_context = UserContext(user_id="alice")
        sample_task_request.session_context = SessionContext(session_id="chat_456")
        alice_session_id_2 = adk_adapter._extract_session_id(sample_task_request)

        assert alice_session_id != alice_session_id_2
        assert alice_session_id_2 == "alice:chat_456"

        # Test 3: No session_context should use default
        sample_task_request.session_context = None
        alice_default = adk_adapter._extract_session_id(sample_task_request)
        assert alice_default == "alice:default"

    def test_convert_contexts_ensures_user_isolated_session_id(
        self, adk_adapter, sample_task_request
    ):
        """Test context conversion ensures session_id includes user isolation."""
        from src.aether_frame.contracts import SessionContext, UserContext

        # Setup contexts
        sample_task_request.user_context = UserContext(
            user_id="test_user",
            preferences={"model": "gemini-1.5-pro", "temperature": 0.5},
        )
        sample_task_request.session_context = SessionContext(
            session_id="session_123", session_state={"previous_topic": "AI"}
        )

        session_config = adk_adapter._convert_contexts_to_session_config(
            sample_task_request
        )

        assert session_config["user_id"] == "test_user"
        # session_id should be user-isolated
        assert session_config["session_id"] == "test_user:session_123"
        assert "user_pref_model" in session_config["initial_state"]
        assert session_config["initial_state"]["previous_topic"] == "AI"

    def test_build_agent_config_from_task(
        self, adk_adapter, sample_task_request, sample_execution_strategy
    ):
        """Test building agent config from task request - main path method."""
        agent_config = adk_adapter._build_agent_config_from_task(
            sample_task_request, sample_execution_strategy
        )

        assert isinstance(agent_config, AgentConfig)
        assert agent_config.framework_type == FrameworkType.ADK
        assert agent_config.agent_type == "chat"
        assert agent_config.name.startswith("task_agent_")
        assert agent_config.model_config["model"] == "gemini-1.5-flash"
        assert agent_config.model_config["temperature"] == 0.8
        assert agent_config.model_config["max_tokens"] == 500

    def test_build_system_prompt_from_task(self, adk_adapter, sample_task_request):
        """Test system prompt building - main path method."""
        prompt = adk_adapter._build_system_prompt_from_task(sample_task_request)

        assert "conversational AI assistant" in prompt
        assert "Test task description" in prompt

    def test_extract_tool_permissions(self, adk_adapter, sample_task_request):
        """Test tool permissions extraction - main path method."""
        permissions = adk_adapter._extract_tool_permissions(sample_task_request)

        # Empty tools list should return empty permissions
        assert permissions == []

    def test_extract_model_configuration(self, adk_adapter, sample_task_request):
        """Test model configuration extraction - main path method."""
        model = adk_adapter._extract_model_configuration(sample_task_request)

        assert model == "gemini-1.5-flash"

    @pytest.mark.asyncio
    async def test_execute_task_session_based_success(
        self, adk_adapter, sample_task_request, sample_execution_strategy
    ):
        """Test successful task execution with session-based architecture."""
        await adk_adapter.initialize()

        # Mock domain agent
        mock_agent = AsyncMock()
        mock_task_result = Mock()
        mock_task_result.result_data = {"response": "test response"}
        mock_task_result.messages = []
        mock_agent.execute.return_value = mock_task_result

        with patch.object(
            adk_adapter, "_get_or_create_session_agent", return_value=mock_agent
        ) as mock_get_agent:
            result = await adk_adapter.execute_task(
                sample_task_request, sample_execution_strategy
            )

            assert isinstance(result, TaskResult)
            assert result.task_id == "test_task_001"
            assert result.status == TaskStatus.SUCCESS
            assert result.result_data == {"response": "test response"}
            assert result.metadata["framework"] == "adk"
            # Should include session_id instead of agent_id
            assert "session_id" in result.metadata

            mock_get_agent.assert_called_once()
            mock_agent.execute.assert_called_once_with(sample_task_request)
            # Agent should NOT be cleaned up (persistent session agent)

    @pytest.mark.asyncio
    async def test_execute_task_failure(
        self, adk_adapter, sample_task_request, sample_execution_strategy
    ):
        """Test task execution failure."""
        await adk_adapter.initialize()
        sample_task_request.agent_id = "agent_123"
        sample_task_request.session_id = "session_456"

        with patch.object(
            adk_adapter,
            "_handle_conversation",
            side_effect=Exception("Test error"),
        ):
            result = await adk_adapter.execute_task(
                sample_task_request, sample_execution_strategy
            )

            assert isinstance(result, TaskResult)
            assert result.task_id == "test_task_001"
            assert result.status == TaskStatus.ERROR
            assert "ADK execution failed" in result.error_message
            assert result.session_id == "session_456"
            assert result.agent_id == "agent_123"
            assert result.metadata.get("request_mode") == "conversation_existing_session"

    @pytest.mark.asyncio
    async def test_execute_task_live_session_based_success(
        self, adk_adapter, sample_task_request
    ):
        """Test successful live task execution with session-based architecture."""
        await adk_adapter.initialize()

        # Mock domain agent and live execution results
        mock_agent = AsyncMock()
        mock_event_stream = AsyncMock()
        mock_communicator = Mock()
        mock_communicator.close = AsyncMock()
        mock_agent.execute_live.return_value = (mock_event_stream, mock_communicator)

        execution_context = ExecutionContext(
            execution_id="test_exec",
            execution_mode="live",
            framework_type=FrameworkType.ADK,
        )

        with patch.object(
            adk_adapter, "_get_or_create_session_agent", return_value=mock_agent
        ):
            event_stream, communicator = await adk_adapter.execute_task_live(
                sample_task_request, execution_context
            )

            assert event_stream == mock_event_stream
            assert communicator == mock_communicator
            mock_agent.execute_live.assert_called_once_with(sample_task_request)
            # Agent should NOT be cleaned up after communicator close (persistent session)

    @pytest.mark.asyncio
    async def test_execute_task_live_failure(self, adk_adapter, sample_task_request):
        """Test live task execution failure."""
        await adk_adapter.initialize()

        execution_context = ExecutionContext(
            execution_id="test_exec",
            execution_mode="live",
            framework_type=FrameworkType.ADK,
        )

        with patch.object(
            adk_adapter,
            "_get_or_create_session_agent",
            side_effect=Exception("Test error"),
        ):
            event_stream, communicator = await adk_adapter.execute_task_live(
                sample_task_request, execution_context
            )

            # Should return error stream and null communicator
            events = []
            async for event in event_stream:
                events.append(event)

            assert len(events) == 1
            assert "Live execution failed" in events[0].content
            assert hasattr(communicator, "close")

    @pytest.mark.asyncio
    async def test_shutdown_with_independent_session_contexts(self, adk_adapter):
        """Test adapter shutdown with independent session context architecture."""
        await adk_adapter.initialize()

        # Add mock session agents and independent session contexts
        mock_agent = AsyncMock()
        mock_runner = AsyncMock()
        mock_runner.shutdown = AsyncMock()
        mock_adk_session = AsyncMock()
        mock_adk_session.close = AsyncMock()
        mock_session_service = AsyncMock()
        mock_session_service.shutdown = AsyncMock()

        adk_adapter._session_agents["test_session"] = mock_agent
        adk_adapter._session_contexts["test_session"] = {
            "runner": mock_runner,
            "session_service": mock_session_service,  # 独立的session service
            "adk_session": mock_adk_session,
            "user_id": "test_user",
            "app_name": "test_app",
        }

        with patch.object(
            adk_adapter, "_cleanup_session", return_value=True
        ) as mock_cleanup:
            await adk_adapter.shutdown()

            assert not adk_adapter._initialized
            assert len(adk_adapter._session_agents) == 0
            assert len(adk_adapter._session_contexts) == 0
            mock_cleanup.assert_called_once_with("test_session")
