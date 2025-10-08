# ADK Session History Migration Test

## Overview

This test script (`test_adk_session_history_migration.py`) comprehensively tests the ADK session management functionality, specifically focusing on chat history extraction and injection during agent switching scenarios.

## Test Scenarios

### Scenario 1: Initial Session Creation
- **Purpose**: Test first-time session creation when no previous session exists
- **Flow**: User sends request with `agent_config` but no `agent_id`/`session_id`
- **Expected**: New ADK session is created, agent is initialized
- **Verifies**: 
  - Session ID and Agent ID are generated
  - Initial conversation is established
  - Response quality is appropriate

### Scenario 2: Session Continuation  
- **Purpose**: Test session reuse when continuing with the same agent
- **Flow**: User sends request with existing `agent_id` and `session_id`
- **Expected**: Same ADK session is reused, no new session creation
- **Verifies**:
  - Session ID remains the same
  - Agent ID remains the same
  - Conversation context is maintained

### Scenario 3: Agent Switching with History Migration
- **Purpose**: Test the core history migration functionality
- **Flow**: User sends request with new `agent_config` but same `chat_session_id`
- **Expected**: 
  1. Old session history is extracted
  2. New agent/session is created
  3. History is injected into new session
- **Verifies**:
  - New session ID is generated
  - New agent ID is generated
  - Chat history migration occurs
  - Context awareness in new agent

## Key Verification Points

### 1. Session Management
```python
# Verify session creation
assert result.session_id is not None
assert result.agent_id is not None

# Verify session reuse
assert result.session_id == previous_session_id
assert result.agent_id == previous_agent_id

# Verify session switching
assert new_session_id != old_session_id
assert new_agent_id != old_agent_id
```

### 2. History Migration Testing
The test builds a substantial conversation history and then verifies:

- **Pre-switch**: Conversation includes Python programming topics (lists, dictionaries, comprehensions)
- **Post-switch**: New agent demonstrates awareness of previous context
- **Context Indicators**: Response contains references to previous discussion topics

### 3. Bidirectional Testing
Tests switching back to a programming agent to verify:
- History accumulates across multiple switches
- Context from both previous agents is available
- System handles multiple agent transitions correctly

## Test Structure

### Message Building Strategy
The test deliberately builds a rich conversation:
1. **Initial Programming Help**: Basic Python questions
2. **Lists Discussion**: Specific technical content  
3. **List Comprehensions**: Advanced programming concepts
4. **Agent Switch**: Move to data analysis
5. **Context Verification**: Test if new agent remembers previous discussion
6. **Bidirectional Switch**: Return to programming with accumulated context

### Debug Output
The test includes comprehensive logging:
- Session ID tracking across switches
- Agent ID verification
- Message count monitoring
- Context awareness assessment
- Performance timing (implicit)

## Expected Debug Output

During agent switching, you should see ADK Session Manager debug logs like:
```
🔍 SWITCH DEBUG: Attempting to extract chat history from session {session_id}
🔍 SWITCH DEBUG: Extracted chat history: X messages
🔍 SWITCH DEBUG: Attempting to inject X messages into new session {new_session_id}
```

## Running the Test

### Via pytest
```bash
# Activate virtual environment first
source .venv/bin/activate

# Run the specific test
pytest tests/e2e/test_adk_session_history_migration.py -v

# Run with detailed output
pytest tests/e2e/test_adk_session_history_migration.py -v -s
```

### Standalone execution
```bash
# Activate virtual environment first  
source .venv/bin/activate

# Run directly
python tests/e2e/test_adk_session_history_migration.py
```

## Success Criteria

The test passes if:
1. ✅ All three scenarios execute without errors
2. ✅ Session IDs change appropriately during switches
3. ✅ Agent IDs change appropriately during switches
4. ✅ `chat_session_id` remains consistent throughout
5. ✅ New agents demonstrate context awareness (>= 2 context indicators)
6. ✅ All assertions pass for session management logic

## Failure Investigation

If the test fails, check:

1. **ADK Integration**: Ensure ADK is properly configured
2. **Session Service**: Verify ADK SessionService is available
3. **History Extraction**: Check ADK session manager logs for extraction failures
4. **History Injection**: Verify injection process completes successfully
5. **Agent Configuration**: Ensure agent configs are valid for framework

## Related Files

- **Implementation**: `src/aether_frame/framework/adk/adk_session_manager.py`
- **Session Models**: `src/aether_frame/framework/adk/adk_session_models.py` 
- **Integration Tests**: `tests/e2e/test_complete_aiassistant_flow.py`
- **Manual Testing**: `tests/manual/test_complete_e2e.py`