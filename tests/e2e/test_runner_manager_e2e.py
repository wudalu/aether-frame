# -*- coding: utf-8 -*-
"""End-to-End Tests for RunnerManager with DeepSeek Configuration."""

import pytest
from datetime import datetime

from src.aether_frame.contracts import AgentConfig, FrameworkType
from src.aether_frame.framework.adk.runner_manager import RunnerManager


class TestRunnerManagerE2E:
    """Test RunnerManager with realistic DeepSeek configurations."""

    @pytest.fixture
    async def runner_manager(self):
        """Create RunnerManager for testing."""
        manager = RunnerManager()
        yield manager
        
        # Cleanup all runners after test
        runner_ids = list(manager.runners.keys())
        for runner_id in runner_ids:
            await manager.cleanup_runner(runner_id)

    @pytest.mark.asyncio
    async def test_runner_creation_with_deepseek_config(self, runner_manager):
        """Test creating runner with DeepSeek configuration."""
        
        deepseek_config = AgentConfig(
            agent_type="deepseek_coding_assistant",
            system_prompt="You are DeepSeek Coder, an expert programming assistant.",
            model_config={
                "model": "deepseek-coder",
                "temperature": 0.1,
                "max_tokens": 4000,
                "stop_sequences": ["```"]
            },
            available_tools=["code_executor", "file_reader", "documentation_search"],
            framework_config={
                "provider": "deepseek",
                "api_base": "https://api.deepseek.com",
                "model_type": "coder",
                "context_window": 16384,
                "code_optimization": True
            }
        )
        
        # Create runner and session
        runner_id, session_id = await runner_manager.get_or_create_runner(deepseek_config)
        
        # Verify runner creation
        assert runner_id is not None
        assert session_id is not None
        assert runner_id in runner_manager.runners
        assert session_id in runner_manager.session_to_runner
        
        # Verify runner context
        runner_context = runner_manager.runners[runner_id]
        assert runner_context["config_hash"] is not None
        assert runner_context["agent_config"] == deepseek_config
        assert session_id in runner_context["sessions"]
        
        print(f"✅ DeepSeek runner created: {runner_id}")
        print(f"✅ Session created: {session_id}")
        
        return runner_id, session_id

    @pytest.mark.asyncio
    async def test_runner_reuse_with_identical_config(self, runner_manager):
        """Test that identical configurations reuse the same runner."""
        
        # Create identical DeepSeek configs
        config1 = AgentConfig(
            agent_type="deepseek_assistant",
            system_prompt="You are a helpful DeepSeek assistant.",
            model_config={"model": "deepseek-chat", "temperature": 0.7},
            framework_config={"provider": "deepseek"}
        )
        
        config2 = AgentConfig(
            agent_type="deepseek_assistant", 
            system_prompt="You are a helpful DeepSeek assistant.",
            model_config={"model": "deepseek-chat", "temperature": 0.7},
            framework_config={"provider": "deepseek"}
        )
        
        # Create first runner/session
        runner_id1, session_id1 = await runner_manager.get_or_create_runner(config1)
        
        # Create second runner/session with identical config
        runner_id2, session_id2 = await runner_manager.get_or_create_runner(config2)
        
        # Should reuse same runner but create different session
        assert runner_id1 == runner_id2  # Same runner
        assert session_id1 != session_id2  # Different sessions
        
        # Verify both sessions exist in same runner
        runner_context = runner_manager.runners[runner_id1]
        assert session_id1 in runner_context["sessions"]
        assert session_id2 in runner_context["sessions"]
        assert len(runner_context["sessions"]) == 2
        
        print(f"✅ Runner reused: {runner_id1}")
        print(f"✅ Session 1: {session_id1}")
        print(f"✅ Session 2: {session_id2}")

    @pytest.mark.asyncio
    async def test_different_configs_create_different_runners(self, runner_manager):
        """Test that different configurations create separate runners."""
        
        # Different DeepSeek configurations
        configs = [
            AgentConfig(
                agent_type="deepseek_coder",
                system_prompt="You are DeepSeek Coder.",
                model_config={"model": "deepseek-coder", "temperature": 0.1},
                framework_config={"provider": "deepseek", "focus": "coding"}
            ),
            AgentConfig(
                agent_type="deepseek_chat",
                system_prompt="You are DeepSeek Chat.",
                model_config={"model": "deepseek-chat", "temperature": 0.7},
                framework_config={"provider": "deepseek", "focus": "conversation"}
            ),
            AgentConfig(
                agent_type="deepseek_analyst",
                system_prompt="You are DeepSeek Data Analyst.",
                model_config={"model": "deepseek-chat", "temperature": 0.3},
                available_tools=["data_processor", "chart_generator"],
                framework_config={"provider": "deepseek", "focus": "analysis"}
            )
        ]
        
        runner_sessions = []
        
        for i, config in enumerate(configs):
            runner_id, session_id = await runner_manager.get_or_create_runner(config)
            runner_sessions.append((runner_id, session_id))
            print(f"✅ Config {i}: Runner {runner_id}, Session {session_id}")
        
        # Verify all runners are different
        runner_ids = [rs[0] for rs in runner_sessions]
        assert len(set(runner_ids)) == len(configs)  # All unique
        
        # Verify all sessions are different  
        session_ids = [rs[1] for rs in runner_sessions]
        assert len(set(session_ids)) == len(configs)  # All unique
        
        print(f"✅ Created {len(configs)} different runners for different configs")

    @pytest.mark.asyncio
    async def test_session_retrieval_by_id(self, runner_manager):
        """Test retrieving runner context by session ID."""
        
        config = AgentConfig(
            agent_type="deepseek_retrieval_test",
            system_prompt="You are a retrieval test assistant.",
            model_config={"model": "deepseek-chat", "temperature": 0.5},
            framework_config={"provider": "deepseek", "test": "retrieval"}
        )
        
        # Create runner and session
        runner_id, session_id = await runner_manager.get_or_create_runner(config)
        
        # Retrieve runner context by session ID
        retrieved_context = await runner_manager.get_runner_by_session(session_id)
        
        # Verify retrieval
        assert retrieved_context is not None
        assert retrieved_context == runner_manager.runners[runner_id]
        assert session_id in retrieved_context["sessions"]
        
        # Test retrieval with non-existent session
        invalid_context = await runner_manager.get_runner_by_session("invalid_session_123")
        assert invalid_context is None
        
        print(f"✅ Session retrieval working: {session_id}")

    @pytest.mark.asyncio
    async def test_runner_manager_statistics(self, runner_manager):
        """Test runner manager statistics and monitoring."""
        
        # Create multiple runners with different configs
        configs = [
            AgentConfig(
                agent_type=f"test_agent_{i}",
                system_prompt=f"You are test agent {i}.",
                model_config={"model": "deepseek-chat", "temperature": 0.1 * i},
                framework_config={"provider": "deepseek", "index": i}
            )
            for i in range(3)
        ]
        
        created_sessions = []
        for config in configs:
            runner_id, session_id = await runner_manager.get_or_create_runner(config)
            created_sessions.append((runner_id, session_id))
        
        # Get statistics
        stats = await runner_manager.get_runner_stats()
        
        # Verify statistics
        assert stats["total_runners"] == 3
        assert stats["total_sessions"] == 3
        assert stats["total_configs"] == 3
        assert len(stats["runners"]) == 3
        
        # Verify runner details in stats
        for runner_info in stats["runners"]:
            assert "runner_id" in runner_info
            assert "config_hash" in runner_info
            assert "session_count" in runner_info
            assert "created_at" in runner_info
            assert runner_info["session_count"] == 1  # Each runner has 1 session
        
        print(f"✅ Statistics: {stats['total_runners']} runners, {stats['total_sessions']} sessions")

    @pytest.mark.asyncio
    async def test_runner_cleanup(self, runner_manager):
        """Test runner cleanup functionality."""
        
        config = AgentConfig(
            agent_type="cleanup_test",
            system_prompt="You are a cleanup test assistant.",
            model_config={"model": "deepseek-chat", "temperature": 0.4},
            framework_config={"provider": "deepseek", "cleanup": True}
        )
        
        # Create runner and session
        runner_id, session_id = await runner_manager.get_or_create_runner(config)
        
        # Verify creation
        assert runner_id in runner_manager.runners
        assert session_id in runner_manager.session_to_runner
        
        # Cleanup runner
        cleanup_success = await runner_manager.cleanup_runner(runner_id)
        
        # Verify cleanup
        assert cleanup_success is True
        assert runner_id not in runner_manager.runners
        assert session_id not in runner_manager.session_to_runner
        
        # Verify stats after cleanup
        stats = await runner_manager.get_runner_stats()
        assert stats["total_runners"] == 0
        assert stats["total_sessions"] == 0
        
        print(f"✅ Runner cleanup successful: {runner_id}")

    @pytest.mark.asyncio
    async def test_complex_deepseek_workflow(self, runner_manager):
        """Test complex workflow with multiple DeepSeek configurations."""
        
        print("🧪 Testing complex DeepSeek workflow...")
        
        # Step 1: Create coding session
        coding_config = AgentConfig(
            agent_type="deepseek_coder_advanced",
            system_prompt="You are an advanced DeepSeek Coder with expertise in Python, JavaScript, and system design.",
            model_config={
                "model": "deepseek-coder",
                "temperature": 0.05,
                "max_tokens": 8000,
                "stop_sequences": ["```", "END_CODE"]
            },
            available_tools=["code_executor", "file_manager", "git_ops", "test_runner"],
            framework_config={
                "provider": "deepseek",
                "model_type": "coder",
                "optimization_level": "advanced",
                "code_review": True,
                "auto_test": True
            }
        )
        
        coding_runner_id, coding_session_id = await runner_manager.get_or_create_runner(coding_config)
        print(f"✅ Coding session: {coding_session_id}")
        
        # Step 2: Create analysis session
        analysis_config = AgentConfig(
            agent_type="deepseek_analyst_advanced",
            system_prompt="You are an advanced data analyst using DeepSeek for complex data analysis and insights.",
            model_config={
                "model": "deepseek-chat",
                "temperature": 0.2,
                "max_tokens": 6000
            },
            available_tools=["data_processor", "statistical_analyzer", "chart_generator", "report_builder"],
            framework_config={
                "provider": "deepseek",
                "model_type": "chat",
                "analysis_mode": "advanced",
                "visualization": True,
                "statistical_depth": "comprehensive"
            }
        )
        
        analysis_runner_id, analysis_session_id = await runner_manager.get_or_create_runner(analysis_config)
        print(f"✅ Analysis session: {analysis_session_id}")
        
        # Step 3: Create another coding session (should reuse runner)
        coding_config_2 = AgentConfig(
            agent_type="deepseek_coder_advanced",  # Same as first
            system_prompt="You are an advanced DeepSeek Coder with expertise in Python, JavaScript, and system design.",
            model_config={
                "model": "deepseek-coder",
                "temperature": 0.05,
                "max_tokens": 8000,
                "stop_sequences": ["```", "END_CODE"]
            },
            available_tools=["code_executor", "file_manager", "git_ops", "test_runner"],
            framework_config={
                "provider": "deepseek",
                "model_type": "coder",
                "optimization_level": "advanced",
                "code_review": True,
                "auto_test": True
            }
        )
        
        coding_runner_id_2, coding_session_id_2 = await runner_manager.get_or_create_runner(coding_config_2)
        print(f"✅ Second coding session: {coding_session_id_2}")
        
        # Verify runner reuse
        assert coding_runner_id == coding_runner_id_2  # Same runner
        assert coding_session_id != coding_session_id_2  # Different sessions
        
        # Step 4: Test session retrieval
        coding_context = await runner_manager.get_runner_by_session(coding_session_id)
        analysis_context = await runner_manager.get_runner_by_session(analysis_session_id)
        coding_context_2 = await runner_manager.get_runner_by_session(coding_session_id_2)
        
        assert coding_context is not None
        assert analysis_context is not None
        assert coding_context_2 is not None
        assert coding_context == coding_context_2  # Same runner context
        
        # Step 5: Verify final state
        stats = await runner_manager.get_runner_stats()
        assert stats["total_runners"] == 2  # coding + analysis
        assert stats["total_sessions"] == 3  # 2 coding + 1 analysis
        
        # Verify coding runner has 2 sessions
        coding_runner_context = runner_manager.runners[coding_runner_id]
        assert len(coding_runner_context["sessions"]) == 2
        
        # Verify analysis runner has 1 session
        analysis_runner_context = runner_manager.runners[analysis_runner_id]
        assert len(analysis_runner_context["sessions"]) == 1
        
        print(f"🎉 Complex workflow completed successfully!")
        print(f"   Runners: {stats['total_runners']}")
        print(f"   Sessions: {stats['total_sessions']}")
        print(f"   Coding runner sessions: {len(coding_runner_context['sessions'])}")
        print(f"   Analysis runner sessions: {len(analysis_runner_context['sessions'])}")
        
        return {
            "coding_runner_id": coding_runner_id,
            "analysis_runner_id": analysis_runner_id,
            "sessions": [coding_session_id, analysis_session_id, coding_session_id_2],
            "stats": stats
        }


if __name__ == "__main__":
    # Quick test runner
    import asyncio
    
    async def run_quick_manager_test():
        print("🧪 Quick RunnerManager test...")
        
        manager = RunnerManager()
        
        try:
            config = AgentConfig(
                agent_type="quick_test",
                system_prompt="Quick test",
                model_config={"model": "deepseek-chat"},
                framework_config={"provider": "deepseek"}
            )
            
            runner_id, session_id = await manager.get_or_create_runner(config)
            print(f"✅ Quick test: Runner {runner_id}, Session {session_id}")
            
            stats = await manager.get_runner_stats()
            print(f"✅ Stats: {stats}")
            
        finally:
            # Cleanup
            runner_ids = list(manager.runners.keys())
            for rid in runner_ids:
                await manager.cleanup_runner(rid)
            print("🧹 Cleanup completed")
    
    asyncio.run(run_quick_manager_test())
