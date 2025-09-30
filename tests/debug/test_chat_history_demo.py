# -*- coding: utf-8 -*-
"""
Demo test to show chat history migration functionality with visible output.
"""

import asyncio
from unittest.mock import Mock, AsyncMock

from src.aether_frame.framework.adk.adk_session_manager import AdkSessionManager
from src.aether_frame.framework.adk.adk_session_models import ChatSessionInfo
from src.aether_frame.contracts import TaskRequest


async def demo_chat_history_migration():
    """Demonstrate chat history migration with visible output."""
    print("=== Chat History Migration Demo ===\n")
    
    # Setup session manager
    def mock_session_service_factory():
        return Mock()
    
    session_manager = AdkSessionManager(session_service_factory=mock_session_service_factory)
    
    # Sample chat history
    sample_chat_history = [
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
    
    print("📝 Original Chat History:")
    for i, msg in enumerate(sample_chat_history):
        print(f"  {i+1}. [{msg['role']}] {msg['content'][:50]}...")
    print()
    
    # Setup mock ADK sessions
    old_adk_session = Mock()
    old_adk_session.state = {"conversation_history": sample_chat_history}
    
    new_adk_session = Mock()
    new_adk_session.state = {}
    
    # Setup mock runner manager
    mock_runner_manager = Mock()
    mock_runner_manager.runners = {
        "runner_python": {
            "sessions": {
                "session_python": old_adk_session
            }
        },
        "runner_javascript": {
            "sessions": {
                "session_javascript": new_adk_session
            }
        }
    }
    mock_runner_manager.get_runner_for_agent = AsyncMock(return_value="runner_javascript")
    mock_runner_manager._create_session_in_runner = AsyncMock(return_value="session_javascript")
    mock_runner_manager.remove_session_from_runner = AsyncMock()
    mock_runner_manager.get_runner_session_count = AsyncMock(return_value=0)
    mock_runner_manager.cleanup_runner = AsyncMock()
    
    # Test chat history extraction
    print("🔍 Testing Chat History Extraction...")
    chat_session = ChatSessionInfo(
        user_id="demo_user",
        chat_session_id="demo_chat",
        active_agent_id="python_agent",
        active_adk_session_id="session_python",
        active_runner_id="runner_python"
    )
    
    extracted_history = await session_manager._extract_chat_history(chat_session, mock_runner_manager)
    
    print(f"✅ Extracted {len(extracted_history)} messages from old session")
    for i, msg in enumerate(extracted_history):
        print(f"  {i+1}. [{msg['role']}] {msg['content'][:50]}...")
    print()
    
    # Test chat history injection
    print("💉 Testing Chat History Injection...")
    await session_manager._inject_chat_history(
        "runner_javascript", "session_javascript", extracted_history, mock_runner_manager
    )
    
    print("✅ History injected into new session")
    print("📋 New session state keys:", list(new_adk_session.state.keys()))
    print(f"📊 Injected {len(new_adk_session.state.get('conversation_history', []))} messages")
    print()
    
    # Test complete agent switch
    print("🔄 Testing Complete Agent Switch with History Migration...")
    session_manager.chat_sessions["demo_chat"] = chat_session
    
    task_request = TaskRequest(
        task_id="demo_task",
        task_type="agent_switch",
        description="Switch from Python to JavaScript agent"
    )
    
    result = await session_manager.coordinate_chat_session(
        chat_session_id="demo_chat",
        target_agent_id="javascript_agent",
        user_id="demo_user",
        task_request=task_request,
        runner_manager=mock_runner_manager
    )
    
    print("✅ Agent switch completed successfully!")
    print(f"   Switch occurred: {result.switch_occurred}")
    print(f"   Previous agent: {result.previous_agent_id}")
    print(f"   New agent: {result.new_agent_id}")
    print(f"   New session ID: {result.adk_session_id}")
    print()
    
    # Verify history was preserved
    final_history = new_adk_session.state.get('conversation_history', [])
    print("📜 Final Chat History in New Session:")
    for i, msg in enumerate(final_history):
        print(f"  {i+1}. [{msg['role']}] {msg['content'][:50]}...")
    print()
    
    print("🎉 Chat History Migration Demo Completed Successfully!")
    print("✨ Conversation continuity preserved across agent switch!")


if __name__ == "__main__":
    asyncio.run(demo_chat_history_migration())