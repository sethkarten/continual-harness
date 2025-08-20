#!/usr/bin/env python3
"""
Test runner for Pokemon Emerald emulator tests

Usage:
    python tests/run_tests.py                    # Run all tests
    python tests/run_tests.py test_fps_adjustment # Run specific test
"""

import os
import sys
import subprocess
import importlib.util

def run_test(test_name):
    """Run a specific test"""
    test_file = f"tests/{test_name}.py"
    
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return False
    
    print(f"🧪 Running test: {test_name}")
    print("=" * 50)
    
    try:
        # Run the test
        result = subprocess.run([
            sys.executable, test_file
        ], capture_output=False, text=True)
        
        if result.returncode == 0:
            print(f"✅ Test {test_name} passed!")
            return True
        else:
            print(f"❌ Test {test_name} failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error running test {test_name}: {e}")
        return False

def run_all_tests():
    """Run all tests in the tests directory"""
    print("🧪 Pokemon Emerald Emulator Test Suite")
    print("=" * 50)
    
    # Find all test files
    test_files = []
    for file in os.listdir("tests"):
        if file.startswith("test_") and file.endswith(".py"):
            test_name = file[:-3]  # Remove .py extension
            test_files.append(test_name)
    
    if not test_files:
        print("❌ No test files found in tests/ directory")
        return False
    
    print(f"Found {len(test_files)} test(s):")
    for test in test_files:
        print(f"  - {test}")
    print()
    print("💡 Note: For pytest-style tests, run:")
    print("   python -m pytest tests/test_fps_adjustment_pytest.py -v")
    print("   python -m pytest tests/test_server_map_validation.py -v")
    print("💡 Note: Test state files are located in tests/states/")
    print("💡 Note: Map reference files are saved in tests/map_references/")
    print()
    
    # Run each test
    results = []
    for test in test_files:
        success = run_test(test)
        results.append((test, success))
        print()  # Add spacing between tests
    
    # Print summary
    print("📋 Test Summary")
    print("=" * 30)
    
    passed_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    for test, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test}: {status}")
    
    print(f"\nResults: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("🎉 All tests passed!")
        return True
    else:
        print("⚠️  Some tests failed.")
        return False

def main():
    """Main function"""
    # Check if we're in the right directory
    if not os.path.exists("server/app.py"):
        print("❌ Error: This test runner must be run from the project root directory")
        print("Please run: python tests/run_tests.py")
        sys.exit(1)
    
    # Check if tests directory exists
    if not os.path.exists("tests"):
        print("❌ Error: tests/ directory not found")
        sys.exit(1)
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        success = run_test(test_name)
        sys.exit(0 if success else 1)
    else:
        # Run all tests
        success = run_all_tests()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 