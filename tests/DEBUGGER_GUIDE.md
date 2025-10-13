# Enhanced Interactive Tool Debugger Guide

The enhanced interactive tool debugger provides comprehensive debugging capabilities for Aether Frame's tool integration system.

## Features

### 🛠️ **Core Debugging Scenarios**
1. **Tool Service Integration Test** - Validates ToolService initialization and MCP server connections
2. **MCP Connection Test** - Tests direct MCP server connectivity and tool discovery
3. **Tool Execution Debug (Sync)** - Debug synchronous tool execution with detailed logging
4. **Tool Execution Debug (Streaming)** - Test streaming tool execution with performance analysis
5. **Direct MCP Tool Call** - Direct MCP server tool invocation for low-level debugging
6. **Comprehensive Scenario Test** - Full end-to-end testing of all components

### 🔍 **Advanced Testing Features**
7. **Tool Resolver Test** - Test tool name resolution strategies (simple → full names)
8. **Streaming Performance Analysis** - Compare sync vs streaming performance metrics
9. **Error & Edge Case Testing** - Test error handling with invalid inputs and edge cases
10. **Predefined Test Scenarios** - Run curated test scenarios for common debugging needs
11. **Load Testing** - Concurrent tool execution testing with performance metrics

### 📊 **Session Management**
12. **Session Summary** - View current debugging session statistics and logs
13. **Save Session** - Save detailed logs and results to JSON files

## Usage

### Basic Usage
```bash
# Activate virtual environment
source .venv/bin/activate

# Start interactive debugger
python tests/interactive_tool_debugger.py
```

### Test Scenarios Available

| Scenario | Description | Parameters |
|----------|-------------|------------|
| `echo_basic` | Basic echo tool test | `{"text": "Hello from debugger"}` |
| `echo_streaming` | Echo with streaming | `{"text": "Streaming test", "delay": 1}` |
| `timestamp_test` | Timestamp tool | `{}` |
| `mcp_search` | MCP search tool | `{"query": "test query", "limit": 5}` |
| `permission_test` | Permission testing | `{}` (expects error) |

### Configuration Options

The debugger supports custom MCP server configurations:

```python
config = {
    "enable_mcp": True,
    "mcp_servers": [
        {
            "name": "local_server",
            "endpoint": "http://localhost:8000/mcp",
            "timeout": 30
        }
    ]
}
```

## Key Features

### 🔄 **Automatic Fallbacks**
- Simulates streaming when real streaming is not available
- Graceful handling of missing contract classes
- Robust error handling with detailed logging

### 📈 **Performance Analysis**
- Real-time execution timing
- Streaming vs synchronous performance comparison
- Concurrent load testing with detailed metrics
- Request success rates and throughput analysis

### 🧪 **Edge Case Testing**
- Non-existent tool handling
- Invalid parameter validation
- Large input processing
- Special character handling
- Permission boundary testing

### 📋 **Comprehensive Logging**
- Structured JSON log files with timestamps
- Session-based log organization
- Multiple log levels (DEBUG, INFO, WARNING, ERROR)
- Execution context and metadata tracking

## Sample Session Output

```
🛠️  Aether Frame Interactive Tool Debugger v2.0
==================================================
Enhanced with comprehensive debugging scenarios:
• Tool Resolution Testing
• Streaming Performance Analysis  
• Error & Edge Case Testing
• Load Testing & Concurrent Execution
• Predefined Test Scenarios
==================================================

Choose a debugging scenario:
1. 📋 Tool Service Integration Test
2. 🔗 MCP Connection Test
...
14. 🚪 Exit
```

## Debug Log Location

All session logs are saved to:
```
tests/debug_logs/
├── tool_debug_YYYYMMDD_HHMMSS.log    # Main log file
└── session_SESSIONID_SCENARIO.json   # Session data
```

## Troubleshooting

### Common Issues

1. **MCP Connection Failed**
   - Verify MCP server is running on configured port
   - Check endpoint URL and timeout settings
   - Review server configuration in debugger

2. **Tool Not Found**
   - Use Tool Resolver Test (option 7) to test name resolution
   - Check available tools list in Tool Service Integration Test
   - Verify tool registration in ToolService

3. **Streaming Issues**
   - Use Streaming Performance Analysis (option 8)
   - Check if tool supports streaming via tool capabilities
   - Review MCP server streaming implementation

### Performance Issues

Use Load Testing (option 11) to identify:
- Concurrent execution bottlenecks
- Memory usage patterns
- Connection pool limitations
- Tool execution timeouts

## Integration with Development

The debugger integrates with the existing Aether Frame architecture:
- Uses real ToolService and ToolResolver instances
- Compatible with all MCP server implementations
- Supports the complete tool execution pipeline
- Validates streaming and error handling mechanisms

For production debugging, the session logs can be analyzed to identify patterns and performance issues in tool execution workflows.