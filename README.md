# Aether Frame

A multi-agent framework abstraction layer supporting ADK, AutoGen, and LangGraph with unified interfaces and dynamic execution modes.

## Overview

Aether Frame provides a unified abstraction layer for building multi-agent applications that can seamlessly switch between different agent frameworks. Currently implemented with ADK (Agent Development Kit) as the primary framework, with an extensible architecture designed for future multi-framework support.

**Current Implementation Status:**
- ✅ **ADK Framework Integration**: Full ADK support with agent lifecycle management
- ✅ **Session Management**: Multi-turn conversations with persistent agent sessions  
- ✅ **Agent Lifecycle**: Create, manage, and cleanup agent instances
- ✅ **Tool Integration**: Builtin tools with extensible tool service architecture
- 🚧 **Live Streaming**: Basic implementation (under development)
- 📋 **Multi-Framework**: Designed for AutoGen and LangGraph (future implementation)

## Key Features

- **ADK Framework Integration**: Complete ADK support with agent creation, session management, and tool integration
- **Session-Based Architecture**: Support for persistent multi-turn conversations with agent_id + session_id model
- **Agent Lifecycle Management**: Create, manage, and cleanup agent instances with proper resource handling
- **Unified Data Contracts**: Consistent data structures across all framework integrations (TaskRequest, TaskResult, etc.)
- **Tool Integration**: Extensible tool registry supporting builtin, MCP, ADK native, and external API tools
- **Infrastructure Services**: Built-in session management, logging, monitoring, and bootstrap initialization
- **Framework Abstraction**: Clean separation between business logic and framework specifics (ready for multi-framework expansion)

## Architecture

Aether Frame follows a layered architecture based on the Framework Abstraction Layer design:

- **Application Execution Layer**: AIAssistant, ExecutionEngine, TaskRouter
- **Framework Abstraction Layer**: FrameworkRegistry and unified interfaces for multiple agent frameworks
- **Core Agent Layer**: AgentManager and framework-agnostic agent interfaces  
- **Tool Service Layer**: Unified tool execution service supporting multiple tool types
- **Infrastructure Layer**: Session, storage, logging, monitoring, and framework-specific adapters
- **Data Contracts Layer**: Well-defined inter-layer communication structures

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md) and [docs/framework_abstraction.md](docs/framework_abstraction.md).

## Quick Start

### Prerequisites

- Python 3.9+
- pip-tools for dependency management
- ADK (Agent Development Kit) dependencies

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd aether-frame
```

2. Set up virtual environment and install dependencies:
```bash
# Create virtual environment and get activation command
python dev.py venv-init

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# Or on Unix/Linux/macOS
source .venv/bin/activate

# Auto-activate on Windows (alternative)
python dev.py venv-auto-activate

# Install development dependencies
python dev.py dev-install
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your ADK configuration (project, location, API keys)
```

### Basic Usage

#### Single Task Execution
```python
from aether_frame import AIAssistant, TaskRequest
from aether_frame.contracts import AgentConfig, UniversalMessage

# Initialize AI Assistant (auto-initializes all components)
assistant = await AIAssistant.create()

# Create a new agent and session
task = TaskRequest(
    task_id="chat_001",
    task_type="chat", 
    description="Help analyze customer feedback",
    messages=[UniversalMessage(role="user", content="Hello, can you help me?")],
    agent_config=AgentConfig(
        agent_id="general_agent",
        agent_type="adk_domain_agent",
        model="gemini-1.5-flash"
    )
)

# Execute task - creates new agent and session
result = await assistant.process_request(task)
print(f"Agent ID: {result.agent_id}")
print(f"Session ID: {result.session_id}")
print(f"Response: {result.messages[0].content}")
```

#### Multi-turn Conversation
```python
# Continue conversation using agent_id and session_id from previous result
follow_up_task = TaskRequest(
    task_id="chat_002", 
    task_type="chat",
    description="Continue conversation",
    messages=[UniversalMessage(role="user", content="Can you elaborate on that?")],
    agent_id=result.agent_id,        # Use existing agent
    session_id=result.session_id     # Continue existing session
)

# Execute follow-up - reuses existing agent and session
follow_up_result = await assistant.process_request(follow_up_task)
```

#### New Session with Existing Agent
```python
# Create new session for same agent (fresh conversation)
new_session_task = TaskRequest(
    task_id="chat_003",
    task_type="chat", 
    description="Start new conversation topic",
    messages=[UniversalMessage(role="user", content="Let's discuss a different topic")],
    agent_id=result.agent_id         # Use existing agent, no session_id
)

# Execute - creates new session for existing agent
new_session_result = await assistant.process_request(new_session_task)
```

## Development

### Project Structure

See [docs/layout.md](docs/layout.md) for detailed project structure documentation.

### Development Commands

```bash
# Virtual environment management
python dev.py venv-init          # Create venv and show activation
python dev.py venv-status        # Check venv status
python dev.py venv-auto-activate # Auto-activate (Windows)

# Dependency management
python dev.py compile-deps       # Compile requirements
python dev.py dev-install        # Install dev dependencies

# Code quality
python dev.py lint              # Run linting checks
python dev.py format            # Format code
python dev.py type-check        # Type checking

# Testing
python dev.py test              # Run all tests
python dev.py test-unit         # Unit tests only
python dev.py test-coverage     # Tests with coverage

# Utilities
python dev.py clean             # Clean cache files
python dev.py version           # Show version
```

### Adding Framework Support

To add support for a new agent framework:

1. Create a new adapter in `src/aether_frame/framework/new_framework/`
2. Implement the `FrameworkAdapter` abstract interface
3. Create framework-specific agent implementations in `src/aether_frame/agents/new_framework/`
4. Register the framework adapter with the `FrameworkRegistry`

Example structure:
```
# Framework abstraction layer
src/aether_frame/framework/new_framework/
├── __init__.py
└── adapter.py          # NewFrameworkAdapter

# Agent implementations
src/aether_frame/agents/new_framework/
├── __init__.py
├── domain_agent.py     # NewDomainAgent
└── agent_hooks.py      # NewAgentHooks
```

## Configuration

Aether Frame uses environment variables and configuration files:

- `.env`: Environment-specific settings
- `src/aether_frame/config/settings.py`: Application configuration
- Framework-specific configurations in `src/aether_frame/framework/*/`

## Testing

```bash
# Run all tests
python dev.py test

# Run specific test categories
python dev.py test-unit
python dev.py test-integration
python dev.py test-e2e

# Run complete E2E test with execution chain logging
python tests/manual/test_complete_e2e.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request