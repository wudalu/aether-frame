# -*- coding: utf-8 -*-
"""
Test to verify that RunnerManager data is preserved during settings update.
"""

import asyncio
from unittest.mock import Mock, AsyncMock

from src.aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter
from src.aether_frame.config.settings import Settings


async def test_data_preservation_during_initialize():
    """Test that RunnerManager data is preserved when initialize() is called with settings."""
    print("🧪 Testing RunnerManager data preservation during initialize...")
    
    # Create adapter
    adapter = AdkFrameworkAdapter()
    print(f"✅ AdkFrameworkAdapter created")
    
    # Simulate some data in RunnerManager
    test_runner_id = "test_runner_123"
    test_session_id = "test_session_456"
    
    # Add test data to the first RunnerManager instance
    adapter.runner_manager.runners[test_runner_id] = {
        "runner": Mock(),
        "sessions": {test_session_id: Mock()},
        "user_id": "test_user",
        "app_name": "test_app"
    }
    adapter.runner_manager.session_to_runner[test_session_id] = test_runner_id
    adapter.runner_manager.config_to_runner["test_config_hash"] = test_runner_id
    
    print(f"📝 Added test data:")
    print(f"   - runners count: {len(adapter.runner_manager.runners)}")
    print(f"   - session_to_runner count: {len(adapter.runner_manager.session_to_runner)}")
    print(f"   - config_to_runner count: {len(adapter.runner_manager.config_to_runner)}")
    
    # Get reference to the RunnerManager instance
    original_runner_manager = adapter.runner_manager
    original_id = id(original_runner_manager)
    
    # Create new settings
    new_settings = Settings()
    new_settings.default_user_id = "updated_user_456"
    
    # Call initialize with settings (this should NOT rebuild RunnerManager)
    try:
        await adapter.initialize(config=None, tool_service=None, settings=new_settings)
        print("✅ initialize() completed successfully")
    except RuntimeError as e:
        if "ADK framework is required" in str(e):
            print("⚠️  ADK not available, but that's expected in test environment")
        else:
            raise
    
    # Verify RunnerManager instance is the same
    current_runner_manager = adapter.runner_manager
    current_id = id(current_runner_manager)
    
    print(f"\n🔍 Verification Results:")
    print(f"   - Same RunnerManager instance: {original_id == current_id}")
    print(f"   - Settings updated: {current_runner_manager.settings.default_user_id == 'updated_user_456'}")
    print(f"   - runners preserved: {len(current_runner_manager.runners)} (should be 1)")
    print(f"   - session_to_runner preserved: {len(current_runner_manager.session_to_runner)} (should be 1)")
    print(f"   - config_to_runner preserved: {len(current_runner_manager.config_to_runner)} (should be 1)")
    
    # Detailed data verification
    assert original_id == current_id, "❌ RunnerManager instance should be preserved"
    assert current_runner_manager.settings.default_user_id == "updated_user_456", "❌ Settings should be updated"
    assert len(current_runner_manager.runners) == 1, "❌ Runners data should be preserved"
    assert len(current_runner_manager.session_to_runner) == 1, "❌ Session mapping should be preserved"
    assert len(current_runner_manager.config_to_runner) == 1, "❌ Config mapping should be preserved"
    assert test_runner_id in current_runner_manager.runners, "❌ Specific runner should be preserved"
    assert test_session_id in current_runner_manager.session_to_runner, "❌ Specific session mapping should be preserved"
    
    print("\n🎉 ALL TESTS PASSED!")
    print("✅ RunnerManager data preservation works correctly")
    print("✅ Settings update without rebuild is successful")


if __name__ == "__main__":
    asyncio.run(test_data_preservation_during_initialize())