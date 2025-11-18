# -*- coding: utf-8 -*-
"""ADK Model Factory for custom model handling."""

import os
from typing import Any, Dict, Optional, Union


class AdkModelFactory:
    """
    Factory for creating ADK-compatible model instances.
    
    This factory handles custom model creation without modifying
    core ADK domain agent logic.
    """
    
    @staticmethod
    def create_model(
        model_identifier: str,
        settings=None,
        enable_streaming: bool = False,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> Union[str, Any]:
        """
        Create appropriate model instance based on identifier.
        
        Args:
            model_identifier: Model identifier string
            settings: Application settings (optional)
            enable_streaming: Whether to enable streaming support
            model_config: Optional per-model configuration overrides
            
        Returns:
            Either the original string for native ADK models,
            or a custom wrapper for external models
        """
        model_lower = model_identifier.lower()
        model_kwargs: Dict[str, Any] = {}
        if model_config:
            model_kwargs = {
                key: value
                for key, value in model_config.items()
                if key != "model" and value is not None
            }
        
        # Handle DeepSeek models
        if "deepseek" in model_lower:
            api_key = getattr(settings, "deepseek_api_key", None) if settings else None
            base_url = getattr(settings, "deepseek_base_url", None) if settings else None
            if api_key:
                os.environ.setdefault("DEEPSEEK_API_KEY", api_key)
            if base_url:
                os.environ.setdefault("DEEPSEEK_API_BASE", base_url)

            model_name = model_identifier if model_identifier.startswith("deepseek/") else f"deepseek/{model_identifier}"

            try:
                if enable_streaming:
                    from .deepseek_streaming_llm import DeepSeekStreamingLLM

                    stream_kwargs = dict(model_kwargs)
                    if api_key:
                        stream_kwargs.setdefault("api_key", api_key)
                    if base_url:
                        stream_kwargs.setdefault("api_base", base_url)
                    return DeepSeekStreamingLLM(
                        model=model_name,
                        **stream_kwargs,
                    )

                from google.adk.models.lite_llm import LiteLlm

                extra_kwargs = {}
                if api_key:
                    extra_kwargs["api_key"] = api_key
                if base_url:
                    extra_kwargs["api_base"] = base_url
                if model_kwargs:
                    extra_kwargs.update(model_kwargs)
                return LiteLlm(model=model_name, **extra_kwargs)
            except ImportError as exc:
                if enable_streaming:
                    raise RuntimeError(
                        "DeepSeek streaming requested but google-adk lite_llm dependencies are not available."
                    ) from exc
                return model_identifier
        
        # Handle Azure OpenAI models
        if model_lower.startswith("azure/") or "azure-" in model_lower:
            try:
                from google.adk.models.lite_llm import LiteLlm
                AzureStreamingLLM = None
                if enable_streaming:
                    try:
                        from .azure_streaming_llm import AzureStreamingLLM
                    except ImportError as exc:
                        raise RuntimeError(
                            "Azure OpenAI streaming requested but dependencies are unavailable."
                        ) from exc

                # Set Azure environment variables if settings provided
                if settings:
                    if hasattr(settings, 'azure_api_key') and settings.azure_api_key:
                        os.environ["AZURE_API_KEY"] = settings.azure_api_key
                    if hasattr(settings, 'azure_api_base') and settings.azure_api_base:
                        os.environ["AZURE_API_BASE"] = settings.azure_api_base
                    if hasattr(settings, 'azure_api_version') and settings.azure_api_version:
                        os.environ["AZURE_API_VERSION"] = settings.azure_api_version
                
                # Convert azure-gpt-4 to azure/gpt-4 format if needed
                if "azure-" in model_lower and not model_lower.startswith("azure/"):
                    azure_model = model_identifier.replace("azure-", "azure/")
                else:
                    azure_model = model_identifier
                extra_args = {}
                if settings:
                    if getattr(settings, 'azure_api_key', None):
                        extra_args.setdefault("api_key", settings.azure_api_key)
                    if getattr(settings, 'azure_api_base', None):
                        extra_args.setdefault("api_base", settings.azure_api_base)
                    if getattr(settings, 'azure_api_version', None):
                        extra_args.setdefault("api_version", settings.azure_api_version)
                if model_kwargs:
                    extra_args.update({k: v for k, v in model_kwargs.items() if v is not None})

                if enable_streaming and AzureStreamingLLM:
                    return AzureStreamingLLM(model=azure_model, **extra_args)

                extra_args.setdefault("stream", enable_streaming)
                return LiteLlm(model=azure_model, **{k: v for k, v in extra_args.items() if v is not None})
            except ImportError:
                # LiteLLM not available, fallback to string
                return model_identifier

        # Handle OpenAI models
        if any(model in model_lower for model in [
            "gpt-4o", "gpt-4.1", "gpt-4", "gpt-3.5", "o1-preview", "o1-mini"
        ]):
            try:
                from google.adk.models.lite_llm import LiteLlm
                extra_kwargs = {"stream": enable_streaming}
                if model_kwargs:
                    extra_kwargs.update(model_kwargs)
                return LiteLlm(model=model_identifier, **{k: v for k, v in extra_kwargs.items() if v is not None})
            except ImportError:
                # LiteLLM not available, fallback to string
                return model_identifier
        
        # Handle Qwen / DashScope models
        if "qwen" in model_lower or "dashscope" in model_lower:
            try:
                from google.adk.models.lite_llm import LiteLlm

                api_key = None
                base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
                if settings:
                    api_key = getattr(settings, "qwen_api_key", None)
                    base_url = getattr(settings, "qwen_base_url", None) or base_url

                # Fall back to environment variables commonly used with DashScope
                if not api_key:
                    api_key = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
                if os.getenv("QWEN_BASE_URL"):
                    base_url = os.getenv("QWEN_BASE_URL")
                elif os.getenv("DASHSCOPE_BASE_URL"):
                    base_url = os.getenv("DASHSCOPE_BASE_URL")

                if api_key:
                    os.environ.setdefault("DASHSCOPE_API_KEY", api_key)

                if model_lower.startswith("dashscope/"):
                    qwen_model = model_identifier
                else:
                    qwen_model = f"dashscope/{model_identifier}"

                extra_args = {}
                if api_key:
                    extra_args["api_key"] = api_key
                if base_url:
                    extra_args["api_base"] = base_url
                if enable_streaming:
                    extra_args["stream"] = True
                if model_kwargs:
                    extra_args.update(model_kwargs)

                return LiteLlm(model=qwen_model, **extra_args)
            except ImportError:
                if enable_streaming:
                    raise RuntimeError(
                        "Qwen streaming requested but google-adk lite_llm dependencies are not available."
                    )
                return model_identifier

        # For Gemini and other ADK-native models, return as-is
        if any(prefix in model_lower for prefix in ["gemini", "projects/", "model-optimizer"]):
            return model_identifier
        
        # Default: return as string for ADK to handle
        return model_identifier
    
    @staticmethod
    def is_custom_model(model_identifier: str) -> bool:
        """
        Check if model requires custom handling.
        
        Args:
            model_identifier: Model identifier string
            
        Returns:
            True if model needs custom wrapper
        """
        model_lower = model_identifier.lower()
        return (
            "deepseek" in model_lower or 
            any(model in model_lower for model in [
                "gpt-4o", "gpt-4.1", "gpt-4", "gpt-3.5", "o1-preview", "o1-mini"
            ]) or
            model_lower.startswith("azure/") or "azure-" in model_lower or
            "qwen" in model_lower or "dashscope" in model_lower
        )
    
    @staticmethod
    def supports_streaming(model_identifier: str) -> bool:
        """
        Check if model supports streaming through our custom wrapper.
        
        Args:
            model_identifier: Model identifier string
            
        Returns:
            True if model supports streaming
        """
        model_lower = model_identifier.lower()
        # DeepSeek supports streaming through our custom wrapper
        if "deepseek" in model_lower:
            return True
        # OpenAI supports streaming natively through LiteLLM
        if any(model in model_lower for model in [
            "gpt-4o", "gpt-4.1", "gpt-4", "gpt-3.5", "o1-preview", "o1-mini"
        ]):
            return True
        # Azure OpenAI supports streaming through LiteLLM
        if model_lower.startswith("azure/") or "azure-" in model_lower:
            return True
        # Gemini supports streaming natively through ADK
        if "gemini" in model_lower:
            return True
        # DashScope/Qwen models support streaming via LiteLLM
        if "qwen" in model_lower or "dashscope" in model_lower:
            return True
        return False
