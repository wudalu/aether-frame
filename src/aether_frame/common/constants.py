"""Constants used throughout Aether Frame."""

from aether_frame.common.types import FrameworkType

# Supported frameworks
SUPPORTED_FRAMEWORKS = [
    FrameworkType.ADK.value,
    FrameworkType.AUTOGEN.value,
    FrameworkType.LANGGRAPH.value,
]

# Default configuration values
DEFAULT_TIMEOUT = 300  # 5 minutes
MAX_RETRIES = 3
DEFAULT_BATCH_SIZE = 10
DEFAULT_MEMORY_TTL = 3600  # 1 hour

# Framework-specific constants
ADK_DEFAULT_MODEL = "gemini-pro"
AUTOGEN_DEFAULT_MODEL = "gpt-4"
LANGGRAPH_DEFAULT_MODEL = "claude-3-sonnet-20240229"

# Memory backends
REDIS_BACKEND = "redis"
POSTGRES_BACKEND = "postgres"
MEMORY_BACKEND = "memory"

# Observability
DEFAULT_METRICS_PORT = 9090
DEFAULT_TRACING_ENDPOINT = "http://localhost:14268/api/traces"

# API settings
API_VERSION = "v1"
DEFAULT_API_PORT = 8000

# Logging
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LOG_FORMATS = ["json", "text"]

# Task execution
MAX_TASK_HISTORY = 1000
TASK_CLEANUP_INTERVAL = 3600  # 1 hour
