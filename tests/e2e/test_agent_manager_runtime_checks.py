#!/usr/bin/env python3
"""
Unit tests for AgentManager session-based lifecycle management
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from aether_frame.agents.manager import AgentManager
from aether_frame.contracts import AgentConfig, FrameworkType


class TestAgentManagerSessionManagement:
    """Test session-based agent management in AgentManager"""

    @pytest.fixture
    def agent_manager(self):
        """Create agent manager for testing"""
        return AgentManager()

    @pytest.fixture
    def sample_agent_config(self):
        """Create sample agent config"""
        return AgentConfig(
            name="test_agent",
            agent_type="conversational_agent",
            framework_type=FrameworkType.ADK,
            model_config={"model": "gemini-1.5-flash"},
        )

    @pytest.mark.asyncio
    async def test_session_based_agent_creation(
        self, agent_manager, sample_agent_config
    ):
        """Test that agents are properly created and managed per session"""

        session_id = "test_session_001"

        # Create mock agent and factory
        mock_agent = AsyncMock()
        mock_agent.is_initialized = True

        async def mock_factory():
            return mock_agent

        # Get or create agent for session
        agent = await agent_manager.get_or_create_session_agent(
            session_id, mock_factory, sample_agent_config
        )

        # Should return the agent
        assert agent is not None
        assert agent == mock_agent

        # Verify agent is stored in session
        stored_agent = await agent_manager.get_session_agent(session_id)
        assert stored_agent == agent

    @pytest.mark.asyncio
    async def test_session_agent_reuse(self, agent_manager, sample_agent_config):
        """Test that existing session agents are reused"""

        session_id = "test_session_002"
        call_count = 0

        # Create mock agent and factory
        mock_agent = AsyncMock()
        mock_agent.is_initialized = True

        async def mock_factory():
            nonlocal call_count
            call_count += 1
            return mock_agent

        # Create agent first time
        agent1 = await agent_manager.get_or_create_session_agent(
            session_id, mock_factory, sample_agent_config
        )

        # Get agent second time - should reuse existing
        agent2 = await agent_manager.get_or_create_session_agent(
            session_id, mock_factory, sample_agent_config
        )

        # Should be the same agent instance
        assert agent1 == agent2

        # Factory should only be called once
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_session_cleanup(self, agent_manager, sample_agent_config):
        """Test that session cleanup works properly"""

        session_id = "test_session_003"

        # Create mock agent and factory
        mock_agent = AsyncMock()
        mock_agent.is_initialized = True
        mock_agent.cleanup = AsyncMock()

        async def mock_factory():
            return mock_agent

        # Create agent
        agent = await agent_manager.get_or_create_session_agent(
            session_id, mock_factory, sample_agent_config
        )
        assert agent is not None

        # Cleanup session
        success = await agent_manager.cleanup_session(session_id)
        assert success is True

        # Agent should be removed from session
        stored_agent = await agent_manager.get_session_agent(session_id)
        assert stored_agent is None

        # Agent cleanup should be called
        mock_agent.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_status_reporting(self, agent_manager, sample_agent_config):
        """Test session status reporting"""

        session_id = "test_session_004"

        # Create mock agent and factory
        mock_agent = AsyncMock()
        mock_agent.is_initialized = True

        async def mock_factory():
            return mock_agent

        # Create agent
        agent = await agent_manager.get_or_create_session_agent(
            session_id, mock_factory, sample_agent_config
        )

        # Get session status
        status = await agent_manager.get_session_status(session_id)

        assert status is not None
        assert status["session_id"] == session_id
        assert status["agent_type"] == "conversational_agent"
        assert status["framework_type"] == FrameworkType.ADK
        assert status["is_initialized"] is True
        assert "created_at" in status

    @pytest.mark.asyncio
    async def test_list_active_sessions(self, agent_manager, sample_agent_config):
        """Test listing active sessions"""

        session_ids = ["session_001", "session_002", "session_003"]

        # Create mock agent and factory
        mock_agent = AsyncMock()
        mock_agent.is_initialized = True

        async def mock_factory():
            return mock_agent

        # Create agents for multiple sessions
        for session_id in session_ids:
            await agent_manager.get_or_create_session_agent(
                session_id, mock_factory, sample_agent_config
            )

        # List active sessions
        active_sessions = await agent_manager.list_active_sessions()

        assert len(active_sessions) == 3
        for session_id in session_ids:
            assert session_id in active_sessions

    @pytest.mark.asyncio
    async def test_health_status(self, agent_manager, sample_agent_config):
        """Test health status reporting"""

        # Create mock agent and factory
        mock_agent = AsyncMock()
        mock_agent.is_initialized = True

        async def mock_factory():
            return mock_agent

        # Create some sessions
        await agent_manager.get_or_create_session_agent(
            "session_1", mock_factory, sample_agent_config
        )
        await agent_manager.get_or_create_session_agent(
            "session_2", mock_factory, sample_agent_config
        )

        # Get health status
        health = await agent_manager.get_health_status()

        assert health["total_sessions"] == 2
        assert health["status"] == "healthy"
        assert "avg_session_age_seconds" in health
        assert "max_session_age_seconds" in health

    @pytest.mark.asyncio
    async def test_expired_session_cleanup(self, agent_manager, sample_agent_config):
        """Test cleanup of expired sessions"""

        # Create mock agent and factory
        mock_agent = AsyncMock()
        mock_agent.is_initialized = True
        mock_agent.cleanup = AsyncMock()

        async def mock_factory():
            return mock_agent

        # Create agent
        session_id = "old_session"
        agent = await agent_manager.get_or_create_session_agent(
            session_id, mock_factory, sample_agent_config
        )

        # Manually set old timestamp to simulate expired session
        import datetime

        old_time = datetime.datetime.now() - timedelta(hours=2)
        agent_manager._session_metadata[session_id]["last_activity"] = old_time

        # Cleanup expired sessions (1 hour max idle)
        expired = await agent_manager.cleanup_expired_sessions(timedelta(hours=1))

        assert len(expired) == 1
        assert expired[0] == session_id

        # Session should be removed
        stored_agent = await agent_manager.get_session_agent(session_id)
        assert stored_agent is None

    def test_session_based_architecture_compliance(self, agent_manager):
        """Verify that AgentManager follows session-based architecture"""
        import inspect

        # Check that old execute methods are not present
        methods = [
            method for method in dir(agent_manager) if not method.startswith("_")
        ]

        # These old methods should NOT exist
        assert "execute_with_runtime" not in methods
        assert "execute_live_with_runtime" not in methods

        # These new session-based methods should exist
        assert "get_or_create_session_agent" in methods
        assert "get_session_agent" in methods
        assert "cleanup_session" in methods
        assert "list_active_sessions" in methods


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
