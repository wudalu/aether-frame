# Aether Frame

A multi-agent framework abstraction layer supporting ADK, AutoGen, and LangGraph with unified interfaces and dynamic execution modes.

## Overview

Aether Frame provides a unified abstraction layer for building multi-agent applications that can seamlessly switch between different agent frameworks. It supports both static workflow execution and dynamic agent coordination patterns.

## Key Features

- **Multi-Framework Support**: Unified interface for ADK, AutoGen, and LangGraph
- **Dual Execution Modes**: Static workflows and dynamic agent coordination
- **Intelligent Routing**: AI Assistant automatically selects optimal execution pattern
- **Memory Management**: Built-in session and context management with pluggable storage
- **Tool Integration**: Extensible tool registry with LLM, search, and external API tools
- **Observability**: Comprehensive monitoring, logging, and tracing capabilities

## Architecture

Aether Frame follows a layered architecture:

- **Execution Layer**: AI Assistant, Workflow Engine, and Coordinator Agent
- **Framework Abstraction Layer**: Unified APIs for multiple agent frameworks
- **Core Agent Layer**: Domain-specific agents and tool services
- **Infrastructure Layer**: Runtime integrations and external services
- **Memory Layer**: Session management and context persistence

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

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

2. Install dependencies:
```bash
make dev-install
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### Basic Usage

```python
from aether_frame.execution.ai_assistant import AIAssistant
from aether_frame.config.settings import Settings

# Initialize the framework
settings = Settings()
assistant = AIAssistant(settings)

# Execute a task (AI Assistant will choose optimal execution mode)
result = await assistant.execute_task({
    "description": "Analyze customer feedback and generate insights",
    "context": {"domain": "customer_service"}
})
```

## Development

### Project Structure

See [docs/layout.md](docs/layout.md) for detailed project structure documentation.

### Development Commands

```bash
# Compile dependencies
make compile-deps

# Install development dependencies
make dev-install

# Run tests
make test

# Clean cache
make clean
```

### Adding Framework Support

To add support for a new agent framework:

1. Create a new adapter in `src/aether_frame/framework/new_framework/`
2. Implement the unified agent interface
3. Register the framework in the configuration

## Configuration

Aether Frame uses environment variables and configuration files:

- `.env`: Environment-specific settings
- `src/aether_frame/config/settings.py`: Application configuration
- Framework-specific configurations in `src/aether_frame/framework/*/`

## Testing

```bash
# Run all tests
make test

# Run specific test categories
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/e2e/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request