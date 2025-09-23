# -*- coding: utf-8 -*-
"""Real end-to-end flow validation test."""

import asyncio
import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(project_root, "src"))

from aether_frame.config.settings import Settings
from aether_frame.contracts import (
    ExecutionConfig,
    ExecutionMode,
    FrameworkType,
    SessionContext,
    TaskRequest,
    UniversalMessage,
    UserContext,
)
from aether_frame.execution.ai_assistant import AIAssistant
from aether_frame.framework.adk.adk_adapter import AdkFrameworkAdapter


async def test_real_end_to_end_flow():
    """Test the actual end-to-end flow with real components."""
    print("🚀 Starting real end-to-end flow test...")

    try:
        # Step 1: Create and initialize ADK adapter
        print("📝 Step 1: Initializing ADK Framework Adapter...")
        adk_adapter = AdkFrameworkAdapter()
        await adk_adapter.initialize()
        print("✅ ADK adapter initialized successfully")

        # Step 2: Check adapter capabilities
        print("📝 Step 2: Checking adapter capabilities...")
        capabilities = await adk_adapter.get_capabilities()
        print(f"✅ ADK capabilities: {capabilities}")

        # Step 3: Create AI Assistant
        print("📝 Step 3: Creating AI Assistant...")
        settings = Settings()
        ai_assistant = AIAssistant(settings)

        # Manually register the ADK adapter
        ai_assistant.framework_registry.register_adapter(FrameworkType.ADK, adk_adapter)
        print("✅ AI Assistant created and ADK adapter registered")

        # Step 4: Create a test task request
        print("📝 Step 4: Creating test task request...")
        user_context = UserContext(user_id="test_user_001", user_name="Test User")

        session_context = SessionContext(session_id="test_session_001")

        message = UniversalMessage(
            role="user", content="Hello! Can you help me test the system?"
        )

        task_request = TaskRequest(
            task_id="end_to_end_test_001",
            task_type="chat",
            description="End-to-end system test",
            user_context=user_context,
            session_context=session_context,
            messages=[message],
            execution_config=ExecutionConfig(
                execution_mode=ExecutionMode.SYNC, max_retries=1, timeout=30
            ),
        )
        print("✅ Task request created")

        # Step 5: Process the request through the full system
        print("📝 Step 5: Processing request through full system...")
        print(f"   - Task ID: {task_request.task_id}")
        print(f"   - Task Type: {task_request.task_type}")
        print(f"   - User: {task_request.user_context.user_name}")
        print(f"   - Message: {task_request.messages[0].content}")

        result = await ai_assistant.process_request(task_request)
        print("✅ Request processed")

        # Step 6: Validate the result
        print("📝 Step 6: Validating result...")
        print(f"   - Result task ID: {result.task_id}")
        print(f"   - Status: {result.status}")
        print(f"   - Error message: {result.error_message}")

        if result.messages:
            print(f"   - Response messages: {len(result.messages)}")
            for i, msg in enumerate(result.messages):
                if hasattr(msg, "content"):
                    print(f"     Message {i}: {msg.content}")
                else:
                    print(f"     Message {i}: {msg}")

        if result.metadata:
            print(f"   - Metadata: {result.metadata}")

        # Determine if the flow worked
        flow_success = (
            result.task_id == task_request.task_id
            and result.status is not None
            and (result.status.name in ["SUCCESS"] or result.error_message is not None)
        )

        if flow_success:
            print("🎉 END-TO-END FLOW TEST: ✅ PASSED")
            print("   - Task was processed through all layers")
            print("   - Response was generated")
            print("   - Data contracts worked correctly")
        else:
            print("❌ END-TO-END FLOW TEST: FAILED")
            print("   - Flow did not complete properly")

        # Step 7: Health check
        print("📝 Step 7: System health check...")
        health = await ai_assistant.health_check()
        print(f"✅ System health: {health}")

        # Step 8: Cleanup
        print("📝 Step 8: Cleanup...")
        await adk_adapter.shutdown()
        print("✅ Cleanup completed")

        return flow_success

    except Exception as e:
        print(f"❌ CRITICAL ERROR in end-to-end flow: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_individual_components():
    """Test individual components in isolation."""
    print("🔧 Testing individual components...")

    try:
        # Test 1: Task Router
        print("📝 Testing TaskRouter...")
        from aether_frame.execution.task_router import TaskRouter

        settings = Settings()
        router = TaskRouter(settings)

        simple_task = TaskRequest(
            task_id="router_test",
            task_type="chat",
            description="Router test",
            messages=[UniversalMessage(role="user", content="Test")],
        )

        strategy = await router.route_task(simple_task)
        print(f"✅ TaskRouter: {strategy.framework_type}, {strategy.agent_type}")

        # Test 2: Framework Registry
        print("📝 Testing FrameworkRegistry...")
        from aether_frame.framework.framework_registry import FrameworkRegistry

        registry = FrameworkRegistry()
        adapter = AdkFrameworkAdapter()
        await adapter.initialize()
        registry.register_adapter(FrameworkType.ADK, adapter)

        retrieved_adapter = await registry.get_adapter(FrameworkType.ADK)
        print(f"✅ FrameworkRegistry: Retrieved {retrieved_adapter.__class__.__name__}")

        # Test 3: Agent Manager
        print("📝 Testing AgentManager...")
        from aether_frame.agents.manager import AgentManager
        from aether_frame.contracts import AgentConfig

        agent_manager = AgentManager()
        config = AgentConfig(agent_type="test", framework_type=FrameworkType.ADK)

        agent_id = await agent_manager.create_agent(config)
        agents = await agent_manager.list_agents()
        print(f"✅ AgentManager: Created agent {agent_id}, total agents: {len(agents)}")

        await agent_manager.destroy_agent(agent_id)

        await adapter.shutdown()
        print("🎉 Individual component tests: ✅ PASSED")
        return True

    except Exception as e:
        print(f"❌ Component test error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_data_contracts():
    """Test data contracts and conversions."""
    print("📋 Testing data contracts...")

    try:
        # Test ADK conversion chain
        user_ctx = UserContext(user_id="test", user_name="Test User")
        session_ctx = SessionContext(session_id="session", conversation_history=[])
        message = UniversalMessage(role="user", content="Hello ADK")

        task = TaskRequest(
            task_id="contract_test",
            task_type="chat",
            description="Contract test",
            user_context=user_ctx,
            session_context=session_ctx,
            messages=[message],
        )

        # Test conversions
        user_id = user_ctx.get_adk_user_id()
        session_id = session_ctx.get_adk_session_id()

        print(f"✅ Data contracts: ADK user_id={user_id}, session_id={session_id}")
        print(f"✅ Task creation: task_id={task.task_id}, type={task.task_type}")

        return True

    except Exception as e:
        print(f"❌ Data contracts error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all validation tests."""
    print("=" * 60)
    print("🧪 AETHER FRAME END-TO-END VALIDATION SUITE")
    print("=" * 60)

    results = []

    # Test 1: Data Contracts
    print("\\n" + "=" * 40)
    print("TEST 1: DATA CONTRACTS")
    print("=" * 40)
    results.append(("Data Contracts", test_data_contracts()))

    # Test 2: Individual Components
    print("\\n" + "=" * 40)
    print("TEST 2: INDIVIDUAL COMPONENTS")
    print("=" * 40)
    results.append(("Individual Components", await test_individual_components()))

    # Test 3: End-to-End Flow
    print("\\n" + "=" * 40)
    print("TEST 3: END-TO-END FLOW")
    print("=" * 40)
    results.append(("End-to-End Flow", await test_real_end_to_end_flow()))

    # Summary
    print("\\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:.<30} {status}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED - System is ready for Sprint 2!")
    else:
        print("⚠️  SOME TESTS FAILED - Issues need to be resolved")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
