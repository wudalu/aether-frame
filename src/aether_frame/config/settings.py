"""Application settings using Pydantic."""

from typing import List, Optional

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

    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-3-sonnet-20240229", env="ANTHROPIC_MODEL"
    )
    anthropic_max_tokens: int = Field(default=4096, env="ANTHROPIC_MAX_TOKENS")

    # DeepSeek configuration
    deepseek_api_key: Optional[str] = Field(default=None, env="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", env="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1", env="DEEPSEEK_BASE_URL")
    deepseek_max_tokens: int = Field(default=4096, env="DEEPSEEK_MAX_TOKENS")
    deepseek_temperature: float = Field(default=0.7, env="DEEPSEEK_TEMPERATURE")

    # Qwen / DashScope configuration
    qwen_api_key: Optional[str] = Field(default=None, env="QWEN_API_KEY")
    qwen_base_url: Optional[str] = Field(default=None, env="QWEN_BASE_URL")
    qwen_model: str = Field(default="qwen-vl-plus", env="QWEN_MODEL")

    # Azure OpenAI configuration - Using LiteLLM standard environment variable names
    azure_api_key: Optional[str] = Field(default=None, env="AZURE_API_KEY")
    azure_api_base: str = Field(default="", env="AZURE_API_BASE")
    azure_api_version: str = Field(default="2023-07-01-preview", env="AZURE_API_VERSION")

    # LiteLLM configuration
    litellm_log: str = Field(default="ERROR", env="LITELLM_LOG")
    deepseek_api_base: str = Field(default="https://api.deepseek.com/v1", env="DEEPSEEK_API_BASE")

    # Google AI/Vertex AI configuration
    google_ai_api_key: Optional[str] = Field(default=None, env="GOOGLE_AI_API_KEY")
    vertex_ai_project_id: Optional[str] = Field(default=None, env="VERTEX_AI_PROJECT_ID")
    vertex_ai_location: str = Field(default="us-central1", env="VERTEX_AI_LOCATION")
    vertex_ai_model: str = Field(default="gemini-pro", env="VERTEX_AI_MODEL")

    # ADK configuration
    adk_project_id: Optional[str] = Field(default=None, env="ADK_PROJECT_ID")
    adk_location: str = Field(default="us-central1", env="ADK_LOCATION")
    adk_credentials_path: Optional[str] = Field(default=None, env="ADK_CREDENTIALS_PATH")

    # AutoGen configuration
    autogen_model_name: str = Field(default="gpt-4", env="AUTOGEN_MODEL_NAME")
    autogen_max_tokens: int = Field(default=4096, env="AUTOGEN_MAX_TOKENS")

    # LangGraph configuration
    langgraph_memory_type: str = Field(default="postgres", env="LANGGRAPH_MEMORY_TYPE")
    langgraph_checkpoint_backend: str = Field(default="postgres", env="LANGGRAPH_CHECKPOINT_BACKEND")

    # PostgreSQL configuration
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_user: str = Field(default="postgres", env="POSTGRES_USER")
    postgres_password: Optional[str] = Field(default=None, env="POSTGRES_PASSWORD")
    postgres_database: str = Field(default="aether_frame", env="POSTGRES_DATABASE")

    # Search engine configuration
    search_engine: str = Field(default="google", env="SEARCH_ENGINE")
    google_search_api_key: Optional[str] = Field(default=None, env="GOOGLE_SEARCH_API_KEY")
    google_search_cx: Optional[str] = Field(default=None, env="GOOGLE_SEARCH_CX")

    # Observability and monitoring
    jaeger_endpoint: str = Field(default="http://localhost:14268/api/traces", env="JAEGER_ENDPOINT")

    # Security configuration
    secret_key: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    api_key_header: str = Field(default="X-API-Key", env="API_KEY_HEADER")

    # CORS configuration
    cors_origins: str = Field(default='["http://localhost:3000"]', env="CORS_ORIGINS")

    # Development settings
    reload_on_change: bool = Field(default=True, env="RELOAD_ON_CHANGE")
    profiling_enabled: bool = Field(default=False, env="PROFILING_ENABLED")

    # Default model configuration
    default_model_provider: str = Field(default="deepseek", env="DEFAULT_MODEL_PROVIDER")
    default_model: str = Field(default="deepseek-chat", env="DEFAULT_MODEL")

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

    # Bootstrap configuration
    enable_tool_service: bool = Field(default=True, env="ENABLE_TOOL_SERVICE")
    enable_mcp_tools: bool = Field(default=False, env="ENABLE_MCP_TOOLS")
    enable_adk_native_tools: bool = Field(default=False, env="ENABLE_ADK_NATIVE_TOOLS")

    # Framework preferences
    preferred_frameworks: List[str] = Field(default=["adk"], env="PREFERRED_FRAMEWORKS")
    framework_timeout: int = Field(default=30, env="FRAMEWORK_TIMEOUT")

    # Runtime ID configuration
    default_user_id: str = Field(default="anonymous", env="DEFAULT_USER_ID")
    default_app_name: str = Field(default="aether_frame", env="DEFAULT_APP_NAME")
    default_agent_type: str = Field(default="adk_domain_agent", env="DEFAULT_AGENT_TYPE")
    
    # ID generation configuration
    runner_id_prefix: str = Field(default="runner", env="RUNNER_ID_PREFIX")
    session_id_prefix: str = Field(default="session", env="SESSION_ID_PREFIX")
    agent_id_prefix: str = Field(default="agent", env="AGENT_ID_PREFIX")
    domain_agent_id_prefix: str = Field(default="domain_agent", env="DOMAIN_AGENT_ID_PREFIX")
    
    # Default model fallbacks
    default_adk_model: str = Field(default="gemini-1.5-flash", env="DEFAULT_ADK_MODEL")
    default_autogen_model: str = Field(default="gpt-4", env="DEFAULT_AUTOGEN_MODEL")
    default_langgraph_model: str = Field(default="gpt-4", env="DEFAULT_LANGGRAPH_MODEL")

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
