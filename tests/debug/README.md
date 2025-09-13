# Debug Scripts

This directory contains debug and analysis scripts used during development.

## Scripts

### Debug Scripts
- `debug_adk_execution.py` - Debug ADK execution issues
- `debug_deepseek_creation.py` - Debug DeepSeek model creation
- `run_tests.py` - Test runner script (legacy)
- `verify_test_method.py` - Method verification utility

### Analysis Scripts  
- `final_streaming_analysis.py` - Streaming functionality analysis

## Usage

These scripts are used for debugging specific issues:

```bash
# Run debug scripts directly
python tests/debug/debug_adk_execution.py

# Analysis scripts
python tests/debug/final_streaming_analysis.py
```

## Note

These scripts are development tools and may not have comprehensive error handling.