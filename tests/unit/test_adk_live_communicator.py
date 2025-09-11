# -*- coding: utf-8 -*-
"""Unit tests for ADK Live Communicator."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.aether_frame.contracts import InteractionResponse, InteractionType
from src.aether_frame.framework.adk.live_communicator import AdkLiveCommunicator


@pytest.fixture
def mock_live_request_queue():
    """Create a mock ADK LiveRequestQueue."""
    queue = MagicMock()
    queue.send_content = MagicMock()
    queue.close = MagicMock()
    return queue


@pytest.fixture
def adk_communicator(mock_live_request_queue):
    """Create an AdkLiveCommunicator instance with mocked queue."""
    return AdkLiveCommunicator(mock_live_request_queue)


@pytest.fixture
def sample_interaction_response():
    """Create a sample InteractionResponse for testing."""
    return InteractionResponse(
        interaction_id="test-123",
        interaction_type=InteractionType.TOOL_APPROVAL,
        approved=True,
        response_data={"tool_name": "search", "params": {"query": "test"}},
        user_message="Approved",
        metadata={"source": "ui"},
        timestamp=datetime(2023, 1, 1, 12, 0, 0)
    )


class TestAdkLiveCommunicator:
    """Test cases for AdkLiveCommunicator."""

    @patch('google.genai.types.Content')
    @patch('google.genai.types.Part')
    async def test_send_user_response(self, mock_part, mock_content, adk_communicator, mock_live_request_queue, sample_interaction_response):
        """Test sending user response through ADK queue."""
        # Setup mocks
        mock_part.from_text.return_value = "mock_part"
        mock_content.return_value = "mock_content"
        
        await adk_communicator.send_user_response(sample_interaction_response)
        
        # Verify ADK methods were called correctly
        mock_part.from_text.assert_called_once()
        mock_content.assert_called_once_with(role="user", parts=["mock_part"])
        mock_live_request_queue.send_content.assert_called_once_with(content="mock_content")
        
        # Verify the text content includes the response details
        call_args = mock_part.from_text.call_args[1]
        response_text = call_args["text"]
        assert "User response to tool_approval" in response_text
        assert "test-123" in response_text
        assert "Approved" in response_text

    @patch('google.genai.types.Content')
    @patch('google.genai.types.Part')
    async def test_send_cancellation(self, mock_part, mock_content, adk_communicator, mock_live_request_queue):
        """Test sending cancellation signal."""
        # Setup mocks
        mock_part.from_text.return_value = "mock_part"
        mock_content.return_value = "mock_content"
        
        await adk_communicator.send_cancellation("timeout")
        
        # Verify ADK methods were called correctly
        mock_part.from_text.assert_called_once()
        mock_content.assert_called_once_with(role="user", parts=["mock_part"])
        mock_live_request_queue.send_content.assert_called_once_with(content="mock_content")
        
        # Verify cancellation text format
        call_args = mock_part.from_text.call_args[1]
        cancellation_text = call_args["text"]
        assert cancellation_text == "CANCELLATION_REQUEST: timeout"

    @patch('google.genai.types.Content')
    @patch('google.genai.types.Part')
    async def test_send_cancellation_default_reason(self, mock_part, mock_content, adk_communicator, mock_live_request_queue):
        """Test sending cancellation with default reason."""
        # Setup mocks
        mock_part.from_text.return_value = "mock_part"
        mock_content.return_value = "mock_content"
        
        await adk_communicator.send_cancellation()
        
        # Verify cancellation text format with default reason
        call_args = mock_part.from_text.call_args[1]
        cancellation_text = call_args["text"]
        assert cancellation_text == "CANCELLATION_REQUEST: user_cancelled"

    @patch('google.genai.types.Content')
    @patch('google.genai.types.Part')
    async def test_send_user_message(self, mock_part, mock_content, adk_communicator, mock_live_request_queue):
        """Test sending user message."""
        # Setup mocks
        mock_part.from_text.return_value = "mock_part"
        mock_content.return_value = "mock_content"
        
        await adk_communicator.send_user_message("Hello, agent!")
        
        # Verify ADK methods were called correctly
        mock_part.from_text.assert_called_once_with(text="Hello, agent!")
        mock_content.assert_called_once_with(role="user", parts=["mock_part"])
        mock_live_request_queue.send_content.assert_called_once_with(content="mock_content")

    def test_close(self, adk_communicator, mock_live_request_queue):
        """Test closing the communicator."""
        assert not adk_communicator._closed
        
        adk_communicator.close()
        
        assert adk_communicator._closed
        mock_live_request_queue.close.assert_called_once()

    @patch('google.genai.types.Content')
    @patch('google.genai.types.Part') 
    async def test_operations_after_close_raise_error(self, mock_part, mock_content, adk_communicator, sample_interaction_response):
        """Test that operations after close raise RuntimeError."""
        adk_communicator.close()
        
        with pytest.raises(RuntimeError, match="Communicator is closed"):
            await adk_communicator.send_user_response(sample_interaction_response)
            
        with pytest.raises(RuntimeError, match="Communicator is closed"):
            await adk_communicator.send_cancellation()
            
        with pytest.raises(RuntimeError, match="Communicator is closed"):
            await adk_communicator.send_user_message("test")

    def test_close_idempotent(self, adk_communicator, mock_live_request_queue):
        """Test that multiple close calls are safe."""
        adk_communicator.close()
        adk_communicator.close()  # Should not raise error
        
        assert adk_communicator._closed
        # close should only be called once
        mock_live_request_queue.close.assert_called_once()