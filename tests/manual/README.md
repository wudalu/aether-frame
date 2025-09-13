# Manual Test Scripts

This directory contains manual test scripts that are used for development and debugging purposes.

## Test Categories

### ADK Tests
- `test_adk_comprehensive.py` - Comprehensive ADK functionality tests
- `test_adk_single_request.py` - Single request ADK tests  
- `test_adk_streaming_request.py` - ADK streaming functionality tests
- `test_real_adk_flow.py` - Real ADK workflow tests

### DeepSeek Tests  
- `test_deepseek_factory.py` - DeepSeek model factory tests
- `test_deepseek_streaming.py` - DeepSeek streaming tests
- `test_deepseek_streaming_comprehensive.py` - Comprehensive DeepSeek streaming tests

### Infrastructure Tests
- `test_model_configuration.py` - Model configuration tests
- `test_streaming_infrastructure.py` - Streaming infrastructure tests
- `test_end_to_end.py` - End-to-end integration tests

## Usage

These tests are typically run manually during development:

```bash
# Run a specific manual test
python tests/manual/test_adk_comprehensive.py

# Or using pytest for better output
pytest tests/manual/test_adk_comprehensive.py -v
```

## Note

These tests may require specific environment setup or ADK/DeepSeek API access.