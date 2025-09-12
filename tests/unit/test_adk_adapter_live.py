# -*- coding: utf-8 -*-
"""Tests for ADK Framework Adapter execute_task_live functionality."""

import pytest
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator

from src.aether_frame.contracts import (
    ExecutionContext,
    FrameworkType,
    TaskRequest,
    TaskStreamChunk,
    TaskChunkType,
    UserContext,
)
from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter


# Mock ADK modules at the system level
def setup_adk_mocks():
    """Setup mock ADK modules in sys.modules."""
    # Create mock modules
    mock_adk = MagicMock()
    mock_adk_runners = MagicMock()
    mock_adk_agents = MagicMock()
    mock_run_config_module = MagicMock()
    
    # Setup mock classes
    mock_adk.Agent = MagicMock()
    mock_adk_runners.InMemoryRunner = MagicMock()
    mock_adk_runners.LiveRequestQueue = MagicMock()
    mock_run_config_module.RunConfig = MagicMock()
    mock_run_config_module.StreamingMode = MagicMock()
    
    # Setup StreamingMode enum values
    mock_run_config_module.StreamingMode.NONE = MagicMock()
    mock_run_config_module.StreamingMode.BIDI = MagicMock()
    
    # Setup agents submodule
    mock_adk_agents.run_config = mock_run_config_module
    mock_adk.agents = mock_adk_agents
    
    # Register in sys.modules
    sys.modules['google.adk'] = mock_adk
    sys.modules['google.adk.runners'] = mock_adk_runners
    sys.modules['google.adk.agents'] = mock_adk_agents
    sys.modules['google.adk.agents.run_config'] = mock_run_config_module
    
    return mock_adk, mock_adk_runners, mock_run_config_module


def cleanup_adk_mocks():
    """Clean up mock ADK modules from sys.modules."""
    modules_to_remove = [
        'google.adk',
        'google.adk.runners',
        'google.adk.agents',
        'google.adk.agents.run_config'
    ]
    for module in modules_to_remove:
        if module in sys.modules:
            del sys.modules[module]


@pytest.fixture(scope='session', autouse=True)
def adk_mocks():
    """Session-wide fixture to setup ADK mocks."""
    mocks = setup_adk_mocks()
    yield mocks
    cleanup_adk_mocks()


@pytest.fixture
def task_request():
    """Create a sample TaskRequest for testing."""
    return TaskRequest(
        task_id="test-task-123",
        task_type="chat",
        description="Test chat task",
        user_context=None,
        session_context=None,
        execution_context=None,
        messages=[],
        available_tools=[],
        available_knowledge=[],
        metadata={"test": True}
    )


@pytest.fixture
def execution_context():
    """Create a sample ExecutionContext for testing."""
    return ExecutionContext(
        execution_id="test-execution-123",
        framework_type=FrameworkType.ADK,
        execution_mode="live",
        timeout=300
    )


@pytest.fixture
async def initialized_adapter():
    """Create an initialized ADK framework adapter."""
    adapter = AdkFrameworkAdapter()
    await adapter.initialize({"test_mode": True})
    return adapter


class TestAdkFrameworkAdapterLive:
    """Test cases for AdkFrameworkAdapter live execution functionality."""

    async def test_execute_task_live_not_initialized(self, task_request, execution_context):
        """Test execute_task_live fails when adapter not initialized."""
        adapter = AdkFrameworkAdapter()
        
        with pytest.raises(RuntimeError, match="ADK framework not initialized"):
            await adapter.execute_task_live(task_request, execution_context)

    async def test_execute_task_live_basic_setup(
        self, adk_mocks, initialized_adapter, task_request, execution_context
    ):
        """Test basic setup of execute_task_live."""
        mock_adk, mock_adk_runners, mock_run_config_module = adk_mocks
        
        # Setup mocks
        mock_agent_instance = MagicMock()
        mock_adk.Agent.return_value = mock_agent_instance
        
        mock_queue_instance = MagicMock()
        mock_adk_runners.LiveRequestQueue.return_value = mock_queue_instance
        
        mock_runner_instance = MagicMock()
        mock_session_service = AsyncMock()
        mock_session = MagicMock()
        mock_session_service.create_session.return_value = mock_session
        mock_runner_instance.session_service = mock_session_service
        
        # Mock run_live to return empty async iterator
        async def empty_events():
            return
            yield  # This line will never execute, but makes it a generator
        
        mock_runner_instance.run_live.return_value = empty_events()
        mock_adk_runners.InMemoryRunner.return_value = mock_runner_instance
        
        # Execute
        result = await initialized_adapter.execute_task_live(task_request, execution_context)
        
        # Verify result structure
        event_stream, communicator = result
        assert hasattr(event_stream, '__aiter__')  # Should be async iterator
        assert hasattr(communicator, 'send_user_response')  # Should be AdkLiveCommunicator
        
        # Verify setup calls
        mock_adk.Agent.assert_called_once()
        mock_adk_runners.LiveRequestQueue.assert_called_once()
        mock_adk_runners.InMemoryRunner.assert_called_once()
        mock_session_service.create_session.assert_called_once()

    async def test_execute_task_live_with_events(
        self, adk_mocks, initialized_adapter, task_request, execution_context
    ):
        """Test execute_task_live with mock ADK events."""
        mock_adk, mock_adk_runners, mock_run_config_module = adk_mocks
        
        # Create mock ADK events
        mock_event_1 = MagicMock()
        mock_event_1.content = MagicMock()
        mock_event_1.content.parts = [MagicMock()]
        mock_event_1.content.parts[0].text = "Hello from agent!"
        mock_event_1.partial = False
        mock_event_1.author = "test_agent"
        mock_event_1.id = "event-1"
        mock_event_1.turn_complete = True
        
        mock_event_2 = MagicMock()
        mock_event_2.turn_complete = True
        mock_event_2.author = "test_agent"
        
        # Setup mocks
        mock_agent_instance = MagicMock()
        mock_adk.Agent.return_value = mock_agent_instance
        
        mock_queue_instance = MagicMock()
        mock_adk_runners.LiveRequestQueue.return_value = mock_queue_instance
        
        mock_runner_instance = MagicMock()
        mock_session_service = AsyncMock()
        mock_session = MagicMock()
        mock_session_service.create_session.return_value = mock_session
        mock_runner_instance.session_service = mock_session_service
        
        # Mock run_live to return test events
        async def mock_events():
            yield mock_event_1
            yield mock_event_2
        
        mock_runner_instance.run_live.return_value = mock_events()
        mock_adk_runners.InMemoryRunner.return_value = mock_runner_instance
        
        # Execute
        event_stream, communicator = await initialized_adapter.execute_task_live(
            task_request, execution_context
        )
        
        # Collect events from stream
        events = []
        async for event in event_stream:
            events.append(event)
        
        # Verify events
        assert len(events) >= 1  # Should have at least one converted event
        
        # Check first event (text response)
        text_event = events[0]
        assert isinstance(text_event, TaskStreamChunk)
        assert text_event.task_id == task_request.task_id
        assert text_event.chunk_type == TaskChunkType.RESPONSE
        assert text_event.content == "Hello from agent!"
        assert text_event.metadata["author"] == "test_agent"

    async def test_convert_adk_event_to_chunk_text_response(self, initialized_adapter):
        """Test conversion of ADK text event to TaskStreamChunk."""
        # Create mock ADK event
        mock_event = MagicMock()
        mock_event.content = MagicMock()
        mock_event.content.parts = [MagicMock()]
        mock_event.content.parts[0].text = "Test response"
        mock_event.partial = False
        mock_event.author = "test_agent"
        mock_event.id = "event-123"
        mock_event.turn_complete = True
        
        # Convert event
        chunk = initialized_adapter._convert_adk_event_to_chunk(
            mock_event, "test-task", 0
        )
        
        # Verify conversion
        assert chunk is not None
        assert isinstance(chunk, TaskStreamChunk)
        assert chunk.task_id == "test-task"
        assert chunk.chunk_type == TaskChunkType.RESPONSE
        assert chunk.sequence_id == 0
        assert chunk.content == "Test response"
        assert not chunk.is_final == False  # is_final should be True for non-partial
        assert chunk.metadata["author"] == "test_agent"
        assert chunk.metadata["adk_event_id"] == "event-123"
        assert chunk.metadata["turn_complete"] == True

    async def test_convert_adk_event_to_chunk_partial_text(self, initialized_adapter):
        """Test conversion of partial ADK text event."""
        # Create mock ADK event with partial=True
        mock_event = MagicMock()
        mock_event.content = MagicMock()
        mock_event.content.parts = [MagicMock()]
        mock_event.content.parts[0].text = "Partial text..."
        mock_event.partial = True
        mock_event.author = "test_agent"
        
        # Convert event
        chunk = initialized_adapter._convert_adk_event_to_chunk(
            mock_event, "test-task", 5
        )
        
        # Verify conversion
        assert chunk.chunk_type == TaskChunkType.PROGRESS  # Should be PROGRESS for partial
        assert chunk.is_final == False
        assert chunk.sequence_id == 5

    async def test_convert_adk_event_to_chunk_function_call(self, initialized_adapter):
        """Test conversion of ADK function call event."""
        # Create mock ADK event with function call
        mock_event = MagicMock()
        mock_event.content = MagicMock()
        mock_event.content.parts = [MagicMock()]
        
        # Make sure text attribute is None/False to avoid text processing
        mock_event.content.parts[0].text = None
        mock_event.content.parts[0].function_call = MagicMock()
        mock_event.content.parts[0].function_call.name = "test_tool"
        mock_event.content.parts[0].function_call.args = {"param1": "value1"}
        mock_event.author = "test_agent"
        mock_event.partial = False
        mock_event.turn_complete = False
        mock_event.error_code = None
        
        # Convert event
        chunk = initialized_adapter._convert_adk_event_to_chunk(
            mock_event, "test-task", 1
        )
        
        # Verify conversion
        assert chunk.chunk_type == TaskChunkType.TOOL_CALL_REQUEST
        assert chunk.content == {
            "function_name": "test_tool",
            "arguments": {"param1": "value1"}
        }
        assert chunk.metadata["requires_approval"] == True

    async def test_convert_adk_event_to_chunk_error(self, initialized_adapter):
        """Test conversion of ADK error event."""
        # Create mock ADK error event
        mock_event = MagicMock()
        mock_event.content = None  # No content for error events
        mock_event.error_code = "SAFETY_FILTER"
        mock_event.error_message = "Content blocked by safety filter"
        mock_event.author = "system"
        mock_event.turn_complete = False
        
        # Convert event
        chunk = initialized_adapter._convert_adk_event_to_chunk(
            mock_event, "test-task", 2
        )
        
        # Verify conversion
        assert chunk.chunk_type == TaskChunkType.ERROR
        assert chunk.content == "Content blocked by safety filter"
        assert chunk.is_final == True
        assert chunk.metadata["error_code"] == "SAFETY_FILTER"

    async def test_convert_adk_event_to_chunk_turn_complete(self, initialized_adapter):
        """Test conversion of ADK turn complete event."""
        # Create mock ADK turn complete event
        mock_event = MagicMock()
        mock_event.turn_complete = True
        mock_event.author = "test_agent"
        # No content
        mock_event.content = None
        mock_event.error_code = None
        
        # Convert event
        chunk = initialized_adapter._convert_adk_event_to_chunk(
            mock_event, "test-task", 3
        )
        
        # Verify conversion
        assert chunk.chunk_type == TaskChunkType.COMPLETE
        assert chunk.content == "Turn completed"
        assert chunk.is_final == True

    async def test_convert_adk_event_to_chunk_filtered_event(self, initialized_adapter):
        """Test filtering of irrelevant ADK events."""
        # Create mock ADK event that should be filtered out
        mock_event = MagicMock()
        mock_event.content = None
        mock_event.error_code = None
        mock_event.turn_complete = False
        
        # Convert event
        chunk = initialized_adapter._convert_adk_event_to_chunk(
            mock_event, "test-task", 4
        )
        
        # Verify filtering
        assert chunk is None

    async def test_convert_adk_event_to_chunk_conversion_error(self, initialized_adapter):
        """Test handling of event conversion errors."""
        # Create mock ADK event that will cause conversion error by raising exception
        mock_event = MagicMock()
        mock_event.content = MagicMock()
        mock_event.content.parts = [MagicMock()]
        
        # Make hasattr fail to trigger exception handling
        def failing_hasattr(obj, attr):
            if attr == 'text':
                raise AttributeError("Simulated conversion error")
            return True
        
        # Mock hasattr to raise exception  
        with patch('builtins.hasattr', side_effect=failing_hasattr):
            chunk = initialized_adapter._convert_adk_event_to_chunk(
                mock_event, "test-task", 6
            )
        
        # Verify error handling
        assert chunk is not None
        assert chunk.chunk_type == TaskChunkType.ERROR
        assert "Event conversion error" in chunk.content
        assert chunk.metadata["error_type"] == "event_conversion_error"

    async def test_execute_task_live_import_error(
        self, adk_mocks, initialized_adapter, task_request, execution_context
    ):
        """Test execute_task_live handles ADK import errors."""
        # Use patch to simulate import error by making the import fail
        def mock_import_error(*args, **kwargs):
            raise ImportError("Simulated ADK import failure")
        
        # Mock the __import__ function to raise ImportError for ADK modules
        with patch('builtins.__import__', side_effect=mock_import_error):
            with pytest.raises(RuntimeError, match="ADK dependencies not available"):
                await initialized_adapter.execute_task_live(task_request, execution_context)

    async def test_execute_task_live_execution_error(
        self, adk_mocks, initialized_adapter, task_request, execution_context
    ):
        """Test execute_task_live handles execution errors."""
        mock_adk, mock_adk_runners, mock_run_config_module = adk_mocks
        
        # Setup Agent to raise exception
        mock_adk.Agent.side_effect = Exception("Agent creation failed")
        
        with pytest.raises(RuntimeError, match="Failed to start live execution"):
            await initialized_adapter.execute_task_live(task_request, execution_context)