#!/usr/bin/env python3
"""
Comprehensive ADK Runtime End-to-End Test Suite
Runs both single request and streaming request tests.
"""

import asyncio
import sys
import os
import subprocess
from datetime import datetime


def run_python_script(script_name: str) -> tuple[bool, str]:
    """Run a Python script and return success status and output."""
    try:
        print(f"\n{'='*60}")
        print(f"Running {script_name}")
        print(f"{'='*60}")
        
        # Run the script
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        # Print output
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        success = result.returncode == 0
        return success, f"Exit code: {result.returncode}"
        
    except Exception as e:
        print(f"❌ Failed to run {script_name}: {e}")
        return False, str(e)


def print_environment_info():
    """Print environment information for debugging."""
    print("ADK Runtime Test Suite")
    print("=" * 60)
    print("Environment Information:")
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Test start time: {datetime.now()}")
    
    # Check if ADK is available
    try:
        import google.adk
        print("✓ Google ADK module available")
    except ImportError:
        print("⚠️ Google ADK module not found - tests may use mock implementations")
    
    # Check Aether Frame
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
        import aether_frame
        print("✓ Aether Frame module available")
    except ImportError as e:
        print(f"❌ Aether Frame module not found: {e}")
    
    print()


async def main():
    """Run the comprehensive test suite."""
    print_environment_info()
    
    # Test results tracking
    test_results = []
    
    # Test 1: Single Request Test
    print("\n🚀 Starting Single Request Tests...")
    single_success, single_output = run_python_script("test_adk_single_request.py")
    test_results.append(("Single Request", single_success, single_output))
    
    # Test 2: Streaming Request Test
    print("\n🚀 Starting Streaming Request Tests...")
    streaming_success, streaming_output = run_python_script("test_adk_streaming_request.py")
    test_results.append(("Streaming Request", streaming_success, streaming_output))
    
    # Summary
    print("\n" + "=" * 60)
    print("COMPREHENSIVE TEST SUMMARY")
    print("=" * 60)
    
    passed_tests = 0
    total_tests = len(test_results)
    
    for test_name, success, output in test_results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} - {test_name}")
        if not success:
            print(f"   Details: {output}")
        else:
            passed_tests += 1
    
    print(f"\nResults: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All ADK runtime tests passed!")
        print("\nNext steps:")
        print("- ADK integration is working correctly")
        print("- Both single and streaming requests are functional")
        print("- Ready for interface unification refactor")
        return True
    else:
        print(f"\n💥 {total_tests - passed_tests} test(s) failed!")
        print("\nTroubleshooting:")
        print("- Check ADK installation and configuration")
        print("- Verify environment setup")
        print("- Review error logs above")
        return False


def check_prerequisites():
    """Check if prerequisites are met."""
    print("Checking prerequisites...")
    
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append("Python 3.8+ required")
    
    # Check if source directory exists
    src_path = os.path.join(os.path.dirname(__file__), "../../src")
    if not os.path.exists(src_path):
        issues.append("src/ directory not found")
    
    # Check test scripts exist
    scripts = ["test_adk_single_request.py", "test_adk_streaming_request.py"]
    for script in scripts:
        if not os.path.exists(script):
            issues.append(f"{script} not found")
    
    if issues:
        print("❌ Prerequisites not met:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✓ Prerequisites check passed")
        return True


if __name__ == "__main__":
    print("ADK Runtime Comprehensive Test Suite")
    print("This suite tests both single and streaming ADK requests end-to-end")
    print()
    
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)
    
    # Run tests
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)