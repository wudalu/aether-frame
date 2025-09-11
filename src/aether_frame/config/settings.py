"""Application settings using Pydantic."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Application settings
    app_name: str = Field(default="aether-frame", env="APP_NAME")
    app_version: str = Field(default="0.1.0", env="APP_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")

    # Logging configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_file_path: Optional[str] = Field(default=None, env="LOG_FILE_PATH")

    # Framework settings
    default_framework: str = Field(default="adk", env="DEFAULT_FRAMEWORK")
    enable_framework_switching: bool = Field(
        default=True, env="ENABLE_FRAMEWORK_SWITCHING"
    )

    # LLM Provider settings
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=4096, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.7, env="OPENAI_TEMPERATURE")

    anthropic_api_key: Optional[str] = Field(
        default=None, env="ANTHROPIC_API_KEY"
    )
    anthropic_model: str = Field(
        default="claude-3-sonnet-20240229", env="ANTHROPIC_MODEL"
    )
    anthropic_max_tokens: int = Field(default=4096, env="ANTHROPIC_MAX_TOKENS")

    # Memory & Storage configuration
    memory_backend: str = Field(default="redis", env="MEMORY_BACKEND")
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    # Session management
    session_timeout: int = Field(default=3600, env="SESSION_TIMEOUT")
    session_storage: str = Field(default="redis", env="SESSION_STORAGE")

    # Observability settings
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    enable_tracing: bool = Field(default=True, env="ENABLE_TRACING")
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT")

    # Performance settings
    max_concurrent_tasks: int = Field(default=10, env="MAX_CONCURRENT_TASKS")
    task_timeout: int = Field(default=300, env="TASK_TIMEOUT")
    memory_limit_mb: int = Field(default=1024, env="MEMORY_LIMIT_MB")

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
