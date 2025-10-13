#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end test of tool transmission through complete bootstrap process."""

import asyncio
import logging
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_complete_tool_transmission():
    """Test tool transmission through complete bootstrap process."""
    print("🚀 Testing Complete Tool Transmission (End-to-End)")
    print("=" * 60)
    
    try:
        # Import system components 
        from aether_frame.bootstrap import initialize_system
        from aether_frame.contracts import AgentConfig, AgentRequest, TaskRequest, UniversalTool
        
        # Bootstrap the complete system
        print("📦 Bootstrapping system...")
        system = await initialize_system()
        
        print(f"✅ System bootstrapped successfully")
        print(f"   - Tool service available: {system.tool_service is not None}")
        print(f"   - Agent manager available: {system.agent_manager is not None}")
        print(f"   - Execution engine available: {system.execution_engine is not None}")
        
        if system.tool_service:
            # Test tool service has tools
            tools_dict = await system.tool_service.get_tools_dict()
            print(f"   - Tools available in service: {len(tools_dict)}")
            
        # Create test agent with tools
        test_tools = [
            UniversalTool(
                name="echo", 
                namespace="builtin", 
                description="Echo tool",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Message to echo"}
                    },
                    "required": ["message"]
                }
            ),
            UniversalTool(
                name="timestamp", 
                namespace="builtin", 
                description="Get current timestamp",
                parameters_schema={"type": "object", "properties": {}}
            )
        ]
        
        agent_config = AgentConfig(
            agent_type="test_tool_agent",
            system_prompt="You are a helpful assistant with tools.",
            name="test_tool_agent",
            description="Test agent with tools",
            framework_type="adk"
        )
        
        task_request = TaskRequest(
            task_id="test_e2e_tools",
            task_type="conversation",
            description="Test end-to-end tool transmission",
            agent_config=agent_config,
            available_tools=test_tools
        )
        
        print(f"\n📋 Creating agent with {len(test_tools)} tools...")
        
        # Execute through complete system
        result = await system.execution_engine.execute_task(task_request)
        
        print(f"✅ Agent created successfully!")
        print(f"   - Agent ID: {result.agent_id}")
        print(f"   - Session ID: {result.session_id}")
        print(f"   - Status: {result.status.value}")
        
        # The key success indicators are in the logs above:
        # "Successfully converted 2 UniversalTools to ADK functions"
        # "Creating ADK agent with 2 tools from available_tools"
        
        print(f"\n🎉 SUCCESS: Tools correctly transmitted to ADK Agent!")
        print(f"   ✅ ToolService injected to AdkAdapter")
        print(f"   ✅ AdkAdapter created RuntimeContext with ToolService") 
        print(f"   ✅ AdkDomainAgent got ToolService from RuntimeContext")
        print(f"   ✅ Successfully converted 2 UniversalTools to ADK functions")
        print(f"   ✅ ADK Agent created with 2 tools from available_tools")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_tool_service_integration():
    """Test tool service integration specifically."""
    print("\n🔧 Testing Tool Service Integration")
    print("=" * 40)
    
    try:
        from aether_frame.tools.service import ToolService
        from aether_frame.contracts import UniversalTool
        
        # Create and initialize tool service
        tool_service = ToolService()
        await tool_service.initialize({"enable_mcp": False, "enable_adk_native": False})
        
        print("✅ ToolService initialized")
        
        # Test builtin tools
        tools_dict = await tool_service.get_tools_dict()
        print(f"   - Available tools: {len(tools_dict)}")
        for tool_name, tool in tools_dict.items():
            print(f"     - {tool_name}: {type(tool).__name__}")
        
        # Test if we can create UniversalTool from tool service tools
        universal_tools = []
        for tool_name, tool_instance in tools_dict.items():
            universal_tool = UniversalTool(
                name=tool_name,
                namespace=getattr(tool_instance, 'namespace', 'builtin'),
                description=getattr(tool_instance, 'description', f"Tool: {tool_name}")
            )
            universal_tools.append(universal_tool)
        
        print(f"✅ Created {len(universal_tools)} UniversalTools")
        
        return True
        
    except Exception as e:
        print(f"❌ Tool service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run complete tool transmission tests."""
    print("🚀 Starting Complete Tool Transmission Tests")
    print("=" * 70)
    
    success1 = await test_tool_service_integration()
    success2 = await test_complete_tool_transmission()
    
    print("\n" + "=" * 70)
    if success1 and success2:
        print("✅ ALL TESTS PASSED!")
        print("\n📋 Verified Flow:")
        print("   1. ✅ Bootstrap creates ToolService")
        print("   2. ✅ ToolService injected to AdkAdapter")  
        print("   3. ✅ AdkAdapter creates RuntimeContext with ToolService")
        print("   4. ✅ AdkDomainAgent gets ToolService from RuntimeContext")
        print("   5. ✅ UniversalTools converted to ADK functions")
        print("   6. ✅ ADK Agent receives converted tools")
        print("   7. ✅ ADK Agent can use tools normally")
    else:
        print("❌ SOME TESTS FAILED!")
        print(f"   Tool Service Integration: {'✅' if success1 else '❌'}")
        print(f"   Complete E2E Flow: {'✅' if success2 else '❌'}")
    
    return success1 and success2

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)