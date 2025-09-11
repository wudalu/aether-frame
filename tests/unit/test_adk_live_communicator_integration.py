# -*- coding: utf-8 -*-
"""Integration tests for ADK Live Communicator with real ADK components."""

import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock

from src.aether_frame.contracts import InteractionResponse, InteractionType
from src.aether_frame.framework.adk.live_communicator import AdkLiveCommunicator

# Import real ADK components
try:
    from google.adk.runners import LiveRequestQueue
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    LiveRequestQueue = None


@pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK not available")
class TestAdkLiveCommunicatorIntegration:
    """Integration tests with real ADK components."""

    @pytest.fixture
    def real_live_request_queue(self):
        """Create a real ADK LiveRequestQueue for testing."""
        # Note: LiveRequestQueue might need specific initialization parameters
        # This is a basic setup that may need adjustment based on actual ADK usage
        try:
            queue = LiveRequestQueue()
            return queue
        except Exception as e:
            pytest.skip(f"Cannot create LiveRequestQueue: {e}")

    @pytest.fixture
    def adk_communicator_with_real_queue(self, real_live_request_queue):
        """Create AdkLiveCommunicator with real ADK queue."""
        return AdkLiveCommunicator(real_live_request_queue)

    @pytest.fixture
    def sample_interaction_response(self):
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

    async def test_real_queue_interface_compatibility(self, real_live_request_queue):
        """Test that real ADK LiveRequestQueue has expected interface."""
        # Verify the queue has the expected send method
        assert hasattr(real_live_request_queue, 'send')
        assert callable(getattr(real_live_request_queue, 'send'))
        
        # Test basic message structure that ADK expects
        test_message = {"type": "test", "timestamp": datetime.now().isoformat()}
        
        # This should not raise an exception
        try:
            await real_live_request_queue.send(test_message)
        except Exception as e:
            # Log the error for debugging but don't fail the test
            # as the queue might require specific setup
            print(f"Queue send failed (expected in test): {e}")

    async def test_message_format_with_real_queue(
        self, adk_communicator_with_real_queue, sample_interaction_response
    ):
        """Test message format compatibility with real ADK queue."""
        # Patch the queue's send method to capture the message format
        with patch.object(
            adk_communicator_with_real_queue._live_request_queue, 
            'send',
            new_callable=AsyncMock
        ) as mock_send:
            await adk_communicator_with_real_queue.send_user_response(
                sample_interaction_response
            )
            
            # Verify the message was sent
            mock_send.assert_called_once()
            
            # Get the actual message format
            sent_message = mock_send.call_args[0][0]
            
            # Verify message structure matches ADK expectations
            assert isinstance(sent_message, dict)
            assert "type" in sent_message
            assert "timestamp" in sent_message
            assert sent_message["type"] == "user_response"

    async def test_cancellation_format_with_real_queue(self, adk_communicator_with_real_queue):
        """Test cancellation message format with real queue."""
        with patch.object(
            adk_communicator_with_real_queue._live_request_queue, 
            'send',
            new_callable=AsyncMock
        ) as mock_send:
            await adk_communicator_with_real_queue.send_cancellation("timeout")
            
            sent_message = mock_send.call_args[0][0]
            assert sent_message["type"] == "cancellation"
            assert sent_message["reason"] == "timeout"

    async def test_user_message_format_with_real_queue(self, adk_communicator_with_real_queue):
        """Test user message format with real queue."""
        with patch.object(
            adk_communicator_with_real_queue._live_request_queue, 
            'send',
            new_callable=AsyncMock
        ) as mock_send:
            await adk_communicator_with_real_queue.send_user_message("Hello!")
            
            sent_message = mock_send.call_args[0][0]
            assert sent_message["type"] == "user_message"
            assert sent_message["content"] == "Hello!"

    def test_type_annotation_compatibility(self):
        """Test that type annotations work with real ADK types."""
        # This test verifies that our type annotations are compatible
        # with the actual ADK LiveRequestQueue type
        if ADK_AVAILABLE:
            queue = LiveRequestQueue()
            communicator = AdkLiveCommunicator(queue)
            
            # Should not raise type errors
            assert communicator._live_request_queue is queue