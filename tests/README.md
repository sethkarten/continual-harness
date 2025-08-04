# Pokemon Emerald Emulator Tests

This directory contains tests for the Pokemon Emerald emulator FPS adjustment system.

## Directory Structure

```
tests/
├── states/                    # Test state files
│   ├── simple_test.state     # Base overworld state (30 FPS)
│   ├── dialog.state          # Dialog state (120 FPS)
│   ├── dialog2.state         # Dialog state 2 (120 FPS - currently failing)
│   ├── after_dialog.state    # After dialog state (30 FPS)
│   └── torchic.state         # Additional test state
├── test_fps_adjustment_pytest.py  # Main FPS adjustment tests
├── run_tests.py              # Test runner script
└── README.md                 # This file
```

## Test States

### `simple_test.state`
- **Expected FPS**: 30
- **Description**: Normal overworld state without dialog
- **Purpose**: Verify base FPS is working correctly

### `dialog.state`
- **Expected FPS**: 120 (4x speedup)
- **Description**: State with active dialog
- **Purpose**: Verify dialog detection and FPS boost

### `dialog2.state`
- **Expected FPS**: 120 (4x speedup)
- **Description**: Another dialog state (currently not detected as dialog)
- **Purpose**: Test dialog detection robustness
- **Status**: Currently failing - needs investigation

### `after_dialog.state`
- **Expected FPS**: 30
- **Description**: State after dialog has ended
- **Purpose**: Verify FPS reverts to normal after dialog timeout

## Running Tests

### Using pytest (Recommended)
```bash
# Run all FPS adjustment tests
conda activate mgba && python -m pytest tests/test_fps_adjustment_pytest.py -v

# Run specific test
conda activate mgba && python -m pytest tests/test_fps_adjustment_pytest.py::test_fps_adjustment_summary -v

# Run all tests in the tests directory
conda activate mgba && python -m pytest tests/ -v
```

### Using the test runner
```bash
# Run all tests
conda activate mgba && python tests/run_tests.py

# Run specific test
conda activate mgba && python tests/run_tests.py test_fps_adjustment_pytest
```

## Test Results

The FPS adjustment system should:
1. ✅ Run at 30 FPS in normal overworld state
2. ✅ Speed up to 120 FPS (4x) when dialog is detected
3. ❌ Speed up to 120 FPS for dialog2.state (currently failing)
4. ✅ Revert to 30 FPS when dialog ends

## Notes

- The `dialog2.state` test is expected to fail until the dialog detection logic is improved
- All state files are now centralized in `tests/states/` for better organization
- Tests use a timeout-based approach where dialog FPS runs for 5 seconds then reverts 