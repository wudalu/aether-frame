"""Custom exceptions for Aether Frame."""


class AetherFrameError(Exception):
    """Base exception class for Aether Frame."""

    pass


class ConfigurationError(AetherFrameError):
    """Raised when configuration is invalid."""

    pass


class FrameworkError(AetherFrameError):
    """Raised when framework operation fails."""

    pass


class AgentError(AetherFrameError):
    """Raised when agent operation fails."""

    pass


class ToolError(AetherFrameError):
    """Raised when tool operation fails."""

    pass


class MemoryError(AetherFrameError):
    """Raised when memory operation fails."""

    pass


class ExecutionError(AetherFrameError):
    """Raised when task execution fails."""

    pass


class TimeoutError(AetherFrameError):
    """Raised when operation times out."""

    pass


class ValidationError(AetherFrameError):
    """Raised when data validation fails."""

    pass
