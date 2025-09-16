# Aether Frame

A multi-agent framework abstraction layer supporting ADK, AutoGen, and LangGraph with unified interfaces and dynamic execution modes.

## Overview

Aether Frame provides a unified abstraction layer for building multi-agent applications that can seamlessly switch between different agent frameworks. It supports flexible execution patterns through a strategy-based approach with intelligent framework routing.

## Key Features

- **Multi-Framework Support**: Unified interface for ADK, AutoGen, and LangGraph
- **Framework Abstraction**: Clean separation between business logic and framework specifics
- **Intelligent Routing**: AI Assistant automatically selects optimal framework and execution strategy
- **Unified Data Contracts**: Consistent data structures across all framework integrations
- **Tool Integration**: Extensible tool registry with MCP, ADK native, external API, and builtin tools
- **Infrastructure Services**: Built-in session management, logging, monitoring, and storage

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
# Edit .env with your configuration
```

### Basic Usage

```python
from aether_frame import AIAssistant, TaskRequest
from aether_frame.config.settings import Settings

# Initialize the framework
settings = Settings()
assistant = AIAssistant(settings)

# Create a task request using data contracts
task = TaskRequest(
    task_id="example_001",
    task_type="chat",
    description="Analyze customer feedback and generate insights",
    user_context={"user_id": "user_123"},
    session_context={"session_id": "session_456"},
    messages=[],
    available_tools=[],
    available_knowledge=[],
    execution_config={}
)

# Execute the task (AI Assistant will choose optimal framework and strategy)
result = await assistant.process_request(task)
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