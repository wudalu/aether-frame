#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test runner for Aether Frame project."""

import sys
import os
import subprocess
import time

def run_command(command, description):
    """Run a command and return success status."""
    print(f"🔄 {description}")
    print(f"   Command: {' '.join(command)}")
    
    start_time = time.time()
    result = subprocess.run(command, capture_output=True, text=True)
    end_time = time.time()
    
    duration = end_time - start_time
    
    if result.returncode == 0:
        print(f"✅ {description} - PASSED ({duration:.2f}s)")
        if result.stdout.strip():
            print("   Output:")
            for line in result.stdout.strip().split('\n'):
                print(f"   {line}")
        return True
    else:
        print(f"❌ {description} - FAILED ({duration:.2f}s)")
        if result.stderr.strip():
            print("   Error:")
            for line in result.stderr.strip().split('\n'):
                print(f"   {line}")
        if result.stdout.strip():
            print("   Output:")
            for line in result.stdout.strip().split('\n'):
                print(f"   {line}")
        return False


def main():
    """Run all tests."""
    print("🧪 AETHER FRAME TEST SUITE")
    print("=" * 60)
    
    # Change to project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    
    tests = []
    results = []
    
    # Unit Tests
    tests.append({
        "command": ["python3", "tests/unit/test_contracts.py"],
        "description": "Unit Tests - Data Contracts"
    })
    
    # Integration Tests
    tests.append({
        "command": ["python3", "tests/integration/test_components.py"],
        "description": "Integration Tests - Components"
    })
    
    # End-to-End Tests
    tests.append({
        "command": ["python3", "tests/e2e/test_real_validation.py"],
        "description": "End-to-End Tests - Full System Validation"
    })
    
    print(f"📋 Found {len(tests)} test suites to run\\n")
    
    # Run all tests
    total_start_time = time.time()
    for i, test in enumerate(tests, 1):
        print(f"\\n[{i}/{len(tests)}] " + "=" * 40)
        success = run_command(test["command"], test["description"])
        results.append((test["description"], success))
        
        if not success:
            print("\\n⚠️  Test failed. Continuing with remaining tests...")
    
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    
    # Summary
    print("\\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for description, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{description:.<45} {status}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("=" * 60)
    print(f"📈 Results: {passed} passed, {failed} failed")
    print(f"⏱️  Total time: {total_duration:.2f}s")
    
    if failed == 0:
        print("🎉 ALL TESTS PASSED - System is ready!")
        return True
    else:
        print(f"⚠️  {failed} TEST SUITE(S) FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)