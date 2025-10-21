"""Application settings using Pydantic V2 style configuration."""

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application settings
    app_name: str = "aether-frame"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "json"
    log_file_path: Optional[str] = None

    # Framework settings
    default_framework: str = "adk"
    enable_framework_switching: bool = True

    # LLM Provider settings
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.7

    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-sonnet-20240229"
    anthropic_max_tokens: int = 4096

    # DeepSeek configuration
    deepseek_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_max_tokens: int = 4096
    deepseek_temperature: float = 0.7

    # Qwen / DashScope configuration
    qwen_api_key: Optional[str] = None
    qwen_base_url: Optional[str] = None
    qwen_model: str = "qwen-vl-plus"

    # Azure OpenAI configuration - Using LiteLLM standard environment variable names
    azure_api_key: Optional[str] = None
    azure_api_base: str = ""
    azure_api_version: str = "2023-07-01-preview"

    # LiteLLM configuration
    litellm_log: str = "ERROR"
    deepseek_api_base: str = "https://api.deepseek.com/v1"

    # Google AI/Vertex AI configuration
    google_ai_api_key: Optional[str] = None
    vertex_ai_project_id: Optional[str] = None
    vertex_ai_location: str = "us-central1"
    vertex_ai_model: str = "gemini-pro"

    # ADK configuration
    adk_project_id: Optional[str] = None
    adk_location: str = "us-central1"
    adk_credentials_path: Optional[str] = None

    # AutoGen configuration
    autogen_model_name: str = "gpt-4"
    autogen_max_tokens: int = 4096

    # LangGraph configuration
    langgraph_memory_type: str = "postgres"
    langgraph_checkpoint_backend: str = "postgres"

    # PostgreSQL configuration
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: Optional[str] = None
    postgres_database: str = "aether_frame"

    # Search engine configuration
    search_engine: str = "google"
    google_search_api_key: Optional[str] = None
    google_search_cx: Optional[str] = None

    # Observability and monitoring
    jaeger_endpoint: str = "http://localhost:14268/api/traces"

    # Security configuration
    secret_key: str = "your-secret-key-here"
    api_key_header: str = "X-API-Key"

    # CORS configuration
    cors_origins: str = '["http://localhost:3000"]'

    # Development settings
    reload_on_change: bool = True
    profiling_enabled: bool = False

    # Default model configuration
    default_model_provider: str = "deepseek"
    default_model: str = "deepseek-chat"

    # Memory & Storage configuration
    memory_backend: str = "redis"
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    redis_password: Optional[str] = None

    # Session management
    session_timeout: int = 3600
    session_storage: str = "redis"
    session_idle_timeout_seconds: int = 0  # Disabled by default
    session_idle_check_interval_seconds: int = 300
    runner_idle_timeout_seconds: int = 43200  # 12 hours by default
    agent_idle_timeout_seconds: int = 43200  # 12 hours by default

    # Observability settings
    enable_metrics: bool = True
    enable_tracing: bool = True
    prometheus_port: int = 9090

    # Performance settings
    max_concurrent_tasks: int = 10
    task_timeout: int = 300
    memory_limit_mb: int = 1024

    # Bootstrap configuration
    enable_tool_service: bool = True
    enable_mcp_tools: bool = False
    enable_adk_native_tools: bool = False

    # Framework preferences
    preferred_frameworks: List[str] = Field(default_factory=lambda: ["adk"])
    framework_timeout: int = 30

    # Runtime ID configuration
    default_user_id: str = "anonymous"
    default_app_name: str = "aether_frame"
    default_agent_type: str = "adk_domain_agent"

    # ID generation configuration
    runner_id_prefix: str = "runner"
    session_id_prefix: str = "session"
    agent_id_prefix: str = "agent"
    domain_agent_id_prefix: str = "domain_agent"
    max_sessions_per_agent: int = 100

    # Default model fallbacks
    default_adk_model: str = "gemini-1.5-flash"
    default_autogen_model: str = "gpt-4"
    default_langgraph_model: str = "gpt-4"
