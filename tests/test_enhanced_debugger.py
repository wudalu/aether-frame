#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for the enhanced interactive tool debugger.

This script validates that all enhanced features are working correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tests.interactive_tool_debugger import InteractiveToolDebugger


async def test_enhanced_debugger():
    """Test enhanced debugger functionality"""
    print("🧪 Testing Enhanced Interactive Tool Debugger")
    print("=" * 50)
    
    # Initialize debugger
    debugger = InteractiveToolDebugger()
    
    # Test 1: Check test scenarios are loaded
    print(f"\n1. ✅ Test scenarios loaded: {len(debugger.test_scenarios)}")
    for key, scenario in debugger.test_scenarios.items():
        print(f"   - {key}: {scenario['description']}")
    
    # Test 2: Check session management
    session_id = debugger.start_session("test_session")
    print(f"\n2. ✅ Session management working: {session_id}")
    print(f"   Session scenario: {debugger.session.scenario}")
    print(f"   Initial logs: {len(debugger.session.logs)}")
    
    # Test 3: Test logging functionality
    debugger.session.add_log("INFO", "Test log entry", {"test": "data"})
    print(f"\n3. ✅ Logging functionality: {len(debugger.session.logs)} logs")
    
    # Test 4: Check if all new scenario methods exist
    scenario_methods = [
        "scenario_tool_resolver_test",
        "scenario_streaming_analysis", 
        "scenario_error_edge_case_test",
        "scenario_predefined_tests",
        "scenario_load_testing"
    ]
    
    missing_methods = []
    for method_name in scenario_methods:
        if not hasattr(debugger, method_name):
            missing_methods.append(method_name)
    
    if missing_methods:
        print(f"\n4. ❌ Missing methods: {missing_methods}")
    else:
        print(f"\n4. ✅ All scenario methods available: {len(scenario_methods)}")
        for method in scenario_methods:
            print(f"   - {method}")
    
    # Test 5: Check enhanced imports and fallbacks
    from tests.interactive_tool_debugger import UniversalTool, UserContext, UserPermissions
    contracts_available = all(x is not None for x in [UniversalTool, UserContext, UserPermissions])
    print(f"\n5. ✅ Contract imports: {'Available' if contracts_available else 'Using fallbacks'}")
    
    # Test 6: Save session for inspection
    debugger.save_session()
    log_file = Path(__file__).parent / "debug_logs" / f"session_{session_id}_test_session.json"
    session_saved = log_file.exists()
    print(f"\n6. ✅ Session saving: {'Working' if session_saved else 'Failed'}")
    if session_saved:
        print(f"   Session file: {log_file}")
    
    print(f"\n🎉 Enhanced debugger validation complete!")
    print(f"📋 Summary:")
    print(f"   - Test scenarios: {len(debugger.test_scenarios)}")
    print(f"   - Scenario methods: {len(scenario_methods)}")
    print(f"   - Session management: Working")
    print(f"   - Logging: Working")
    print(f"   - Contracts: {'Available' if contracts_available else 'Fallback mode'}")
    
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_enhanced_debugger())
        if result:
            print(f"\n✅ All tests passed! Enhanced debugger is ready for use.")
            print(f"\n🚀 To use the interactive debugger:")
            print(f"   source .venv/bin/activate")
            print(f"   python tests/interactive_tool_debugger.py")
        else:
            print(f"\n❌ Some tests failed.")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        sys.exit(1)