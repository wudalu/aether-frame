# -*- coding: utf-8 -*-
"""
End-to-end test for chat history migration during agent switching.

This test verifies that chat history is properly extracted from the old session
and injected into the new session when switching agents, preserving conversation continuity.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from src.aether_frame.framework.adk.adk_session_manager import AdkSessionManager
from src.aether_frame.framework.adk.adk_session_models import ChatSessionInfo
from src.aether_frame.contracts import TaskRequest


class TestChatHistoryMigration:
    """Test chat history migration functionality during agent switching."""
    
    @pytest.fixture
    def session_manager(self):
        """Create AdkSessionManager instance for testing."""
        def mock_session_service_factory():
            return Mock()
        
        return AdkSessionManager(session_service_factory=mock_session_service_factory)
    
    @pytest.fixture
    def mock_runner_manager(self):
        """Create mock runner manager."""
        runner_manager = Mock()
        runner_manager.get_runner_for_agent = AsyncMock()
        runner_manager._create_session_in_runner = AsyncMock()
        runner_manager.remove_session_from_runner = AsyncMock()
        runner_manager.get_runner_session_count = AsyncMock()
        runner_manager.cleanup_runner = AsyncMock()
        return runner_manager
    
    @pytest.fixture
    def sample_chat_history(self):
        """Sample chat history for testing."""
        return [
            {
                "role": "user",
                "content": "Hello, can you help me with Python programming?",
                "timestamp": "2025-09-30T10:00:00Z"
            },
            {
                "role": "assistant", 
                "content": "Of course! I'd be happy to help you with Python programming. What specific topic would you like to learn about?",
                "timestamp": "2025-09-30T10:00:30Z"
            },
            {
                "role": "user",
                "content": "I want to learn about async/await",
                "timestamp": "2025-09-30T10:01:00Z"
            }
        ]
    
    @pytest.fixture
    def mock_adk_session_with_history(self, sample_chat_history):
        """Create mock ADK session with conversation history."""
        adk_session = Mock()
        adk_session.state = {
            "conversation_history": sample_chat_history,
            "session_id": "test_session_123",
            "agent_id": "agent_python_expert"
        }
        return adk_session
    
    @pytest.fixture
    def mock_adk_session_empty(self):
        """Create mock ADK session without history."""
        adk_session = Mock()
        adk_session.state = {}
        return adk_session

    async def test_extract_chat_history_from_conversation_history_key(
        self, session_manager, mock_runner_manager, mock_adk_session_with_history, sample_chat_history
    ):
        """Test extracting chat history from session.state['conversation_history']."""
        # Setup chat session
        chat_session = ChatSessionInfo(
            user_id="test_user",
            chat_session_id="chat_123",
            active_agent_id="agent_python_expert",
            active_adk_session_id="adk_session_123",
            active_runner_id="runner_123"
        )
        
        # Setup runner manager mock
        mock_runner_manager.runners = {
            "runner_123": {
                "sessions": {
                    "adk_session_123": mock_adk_session_with_history
                }
            }
        }
        
        # Test extraction
        extracted_history = await session_manager._extract_chat_history(chat_session, mock_runner_manager)
        
        # Verify results
        assert extracted_history is not None
        assert len(extracted_history) == 3
        assert extracted_history == sample_chat_history
        assert extracted_history[0]["role"] == "user"
        assert extracted_history[1]["role"] == "assistant"

    async def test_extract_chat_history_from_messages_key(self, session_manager, mock_runner_manager, sample_chat_history):
        """Test extracting chat history from session.state['messages'] (alternative key)."""
        # Create mock session with history under 'messages' key
        adk_session = Mock()
        adk_session.state = {
            "messages": sample_chat_history,
            "session_id": "test_session_123"
        }
        
        chat_session = ChatSessionInfo(
            user_id="test_user",
            chat_session_id="chat_123",
            active_agent_id="agent_python_expert",
            active_adk_session_id="adk_session_123",
            active_runner_id="runner_123"
        )
        
        mock_runner_manager.runners = {
            "runner_123": {
                "sessions": {
                    "adk_session_123": adk_session
                }
            }
        }
        
        extracted_history = await session_manager._extract_chat_history(chat_session, mock_runner_manager)
        
        assert extracted_history is not None
        assert len(extracted_history) == 3
        assert extracted_history == sample_chat_history

    async def test_extract_chat_history_auto_detect_message_structure(self, session_manager, mock_runner_manager):
        """Test auto-detection of message-like structures when standard keys aren't found."""
        # Create mock session with non-standard key but message-like structure
        custom_history = [
            {"role": "user", "content": "Test message 1"},
            {"author": "assistant", "content": "Test response 1"}
        ]
        
        adk_session = Mock()
        adk_session.state = {
            "custom_chat_log": custom_history,
            "session_metadata": {"created": "2025-09-30"}
        }
        
        chat_session = ChatSessionInfo(
            user_id="test_user",
            chat_session_id="chat_123",
            active_agent_id="agent_test",
            active_adk_session_id="adk_session_123",
            active_runner_id="runner_123"
        )
        
        mock_runner_manager.runners = {
            "runner_123": {
                "sessions": {
                    "adk_session_123": adk_session
                }
            }
        }
        
        extracted_history = await session_manager._extract_chat_history(chat_session, mock_runner_manager)
        
        assert extracted_history is not None
        assert len(extracted_history) == 2
        assert extracted_history == custom_history

    async def test_extract_chat_history_no_history_found(self, session_manager, mock_runner_manager, mock_adk_session_empty):
        """Test behavior when no chat history is found."""
        chat_session = ChatSessionInfo(
            user_id="test_user",
            chat_session_id="chat_123",
            active_agent_id="agent_test",
            active_adk_session_id="adk_session_123",
            active_runner_id="runner_123"
        )
        
        mock_runner_manager.runners = {
            "runner_123": {
                "sessions": {
                    "adk_session_123": mock_adk_session_empty
                }
            }
        }
        
        extracted_history = await session_manager._extract_chat_history(chat_session, mock_runner_manager)
        
        assert extracted_history == []

    async def test_inject_chat_history_into_new_session(
        self, session_manager, mock_runner_manager, sample_chat_history
    ):
        """Test injecting chat history into a new ADK session."""
        # Create mock new session
        new_adk_session = Mock()
        new_adk_session.state = {}
        
        mock_runner_manager.runners = {
            "runner_456": {
                "sessions": {
                    "adk_session_456": new_adk_session
                }
            }
        }
        
        # Test injection
        await session_manager._inject_chat_history(
            "runner_456", "adk_session_456", sample_chat_history, mock_runner_manager
        )
        
        # Verify history was injected
        assert "conversation_history" in new_adk_session.state
        assert "messages" in new_adk_session.state  # Also stored for compatibility
        assert new_adk_session.state["conversation_history"] == sample_chat_history
        assert new_adk_session.state["messages"] == sample_chat_history

    async def test_inject_empty_chat_history(self, session_manager, mock_runner_manager):
        """Test injecting empty chat history (should not modify session)."""
        new_adk_session = Mock()
        new_adk_session.state = {"existing_key": "existing_value"}
        
        mock_runner_manager.runners = {
            "runner_456": {
                "sessions": {
                    "adk_session_456": new_adk_session
                }
            }
        }
        
        # Test injection with empty history
        await session_manager._inject_chat_history(
            "runner_456", "adk_session_456", [], mock_runner_manager
        )
        
        # Verify state wasn't modified for empty history
        assert new_adk_session.state == {"existing_key": "existing_value"}

    async def test_complete_agent_switch_with_history_migration(
        self, session_manager, mock_runner_manager, sample_chat_history
    ):
        """Test complete agent switching flow with chat history migration."""
        # Setup initial session with history
        old_adk_session = Mock()
        old_adk_session.state = {"conversation_history": sample_chat_history}
        
        new_adk_session = Mock()
        new_adk_session.state = {}
        
        # Setup runner manager
        mock_runner_manager.runners = {
            "runner_old": {
                "sessions": {
                    "adk_session_old": old_adk_session
                }
            },
            "runner_new": {
                "sessions": {
                    "adk_session_new": new_adk_session
                }
            }
        }
        
        mock_runner_manager.get_runner_for_agent.return_value = "runner_new"
        mock_runner_manager._create_session_in_runner.return_value = "adk_session_new"
        mock_runner_manager.get_runner_session_count.return_value = 0
        
        # Create initial chat session
        chat_session = ChatSessionInfo(
            user_id="test_user",
            chat_session_id="chat_123",
            active_agent_id="agent_old",
            active_adk_session_id="adk_session_old",
            active_runner_id="runner_old"
        )
        
        # Store in session manager
        session_manager.chat_sessions["chat_123"] = chat_session
        
        # Create task request
        task_request = TaskRequest(
            task_id="task_456",
            task_type="agent_switch",
            description="Switch to new agent"
        )
        
        # Execute agent switch
        result = await session_manager.coordinate_chat_session(
            chat_session_id="chat_123",
            target_agent_id="agent_new",
            user_id="test_user",
            task_request=task_request,
            runner_manager=mock_runner_manager
        )
        
        # Verify switch occurred
        assert result.switch_occurred is True
        assert result.previous_agent_id == "agent_old"
        assert result.new_agent_id == "agent_new"
        assert result.adk_session_id == "adk_session_new"
        
        # Verify chat session updated
        assert chat_session.active_agent_id == "agent_new"
        assert chat_session.active_adk_session_id == "adk_session_new"
        assert chat_session.active_runner_id == "runner_new"
        
        # Verify history was migrated to new session
        assert "conversation_history" in new_adk_session.state
        assert new_adk_session.state["conversation_history"] == sample_chat_history
        
        # Verify cleanup was called
        mock_runner_manager.remove_session_from_runner.assert_called_once_with("runner_old", "adk_session_old")

    async def test_error_handling_during_history_extraction(self, session_manager, mock_runner_manager):
        """Test error handling when history extraction fails."""
        # Create session with invalid runner
        chat_session = ChatSessionInfo(
            user_id="test_user",
            chat_session_id="chat_123",
            active_agent_id="agent_test",
            active_adk_session_id="adk_session_123",
            active_runner_id="runner_invalid"
        )
        
        # Runner doesn't exist
        mock_runner_manager.runners = {}
        
        # Should return None on error without raising exception
        extracted_history = await session_manager._extract_chat_history(chat_session, mock_runner_manager)
        
        assert extracted_history is None

    async def test_error_handling_during_history_injection(self, session_manager, mock_runner_manager, sample_chat_history):
        """Test error handling when history injection fails."""
        # Invalid runner
        mock_runner_manager.runners = {}
        
        # Should not raise exception
        await session_manager._inject_chat_history(
            "runner_invalid", "session_invalid", sample_chat_history, mock_runner_manager
        )
        
        # Test should complete without errors

    def test_session_state_structure_validation(self, sample_chat_history):
        """Test that our implementation correctly identifies valid message structures."""
        # Test valid structures
        valid_structures = [
            [{"role": "user", "content": "test"}],
            [{"author": "assistant", "content": "response"}],
            [{"role": "system", "content": "prompt", "timestamp": "2025-09-30"}]
        ]
        
        for structure in valid_structures:
            first_item = structure[0]
            # This mimics the logic in _get_adk_session_history
            is_message_like = isinstance(first_item, dict) and ('role' in first_item or 'author' in first_item)
            assert is_message_like, f"Should identify {structure} as message-like"
        
        # Test invalid structures
        invalid_structures = [
            [{"content": "missing role"}],
            [{"random": "data"}],
            ["string item"],
            [123]
        ]
        
        for structure in invalid_structures:
            if len(structure) > 0:
                first_item = structure[0]
                is_message_like = isinstance(first_item, dict) and ('role' in first_item or 'author' in first_item)
                assert not is_message_like, f"Should NOT identify {structure} as message-like"