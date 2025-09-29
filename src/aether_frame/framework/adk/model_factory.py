# -*- coding: utf-8 -*-
"""ADK Model Factory for custom model handling."""

from typing import Any, Union


class AdkModelFactory:
    """
    Factory for creating ADK-compatible model instances.
    
    This factory handles custom model creation without modifying
    core ADK domain agent logic.
    """
    
    @staticmethod
    def create_model(model_identifier: str, settings=None, enable_streaming: bool = False) -> Union[str, Any]:
        """
        Create appropriate model instance based on identifier.
        
        Args:
            model_identifier: Model identifier string
            settings: Application settings (optional)
            enable_streaming: Whether to enable streaming support
            
        Returns:
            Either the original string for native ADK models,
            or a custom wrapper for external models
        """
        model_lower = model_identifier.lower()
        
        # Handle DeepSeek models
        if "deepseek" in model_lower:
            if enable_streaming:
                # Use custom streaming wrapper
                try:
                    from .deepseek_streaming_llm import DeepSeekStreamingLLM
                    if settings:
                        # DeepSeek still uses direct env variable access for now
                        api_key = getattr(settings, "deepseek_api_key", None)
                        base_url = getattr(settings, "deepseek_base_url", "https://api.deepseek.com/v1")
                        return DeepSeekStreamingLLM(
                            model=model_identifier,
                            api_key=api_key,
                            base_url=base_url
                        )
                    else:
                        return DeepSeekStreamingLLM(model=model_identifier)
                except ImportError:
                    # Fall back to LiteLLM if streaming wrapper unavailable
                    pass
            
            # Use LiteLLM for non-streaming or fallback
            try:
                from google.adk.models.lite_llm import LiteLlm
                return LiteLlm(model=f"deepseek/{model_identifier}")
            except ImportError:
                # LiteLLM not available, fallback to string
                return model_identifier
        
        # Handle OpenAI models
        if any(model in model_lower for model in [
            "gpt-4o", "gpt-4.1", "gpt-4", "gpt-3.5", "o1-preview", "o1-mini"
        ]):
            try:
                from google.adk.models.lite_llm import LiteLlm
                import os
                import logging
                
                logger = logging.getLogger(__name__)
                
                # Set OpenAI API key from settings if available
                if settings:
                    openai_key = settings.get_openai_api_key()
                    if openai_key:
                        os.environ["OPENAI_API_KEY"] = openai_key
                        if settings.is_debug_mode():
                            logger.debug(f"Set OpenAI API key for model {model_identifier}")
                    elif settings.is_debug_mode():
                        logger.warning(f"No OpenAI API key available for model {model_identifier}")
                
                if settings and settings.is_debug_mode():
                    logger.debug(f"Creating LiteLLM model: {model_identifier}")
                
                return LiteLlm(model=model_identifier)
            except ImportError:
                # LiteLLM not available, fallback to string
                return model_identifier
        
        # Handle Azure OpenAI models
        if model_lower.startswith("azure/") or "azure-" in model_lower:
            try:
                from google.adk.models.lite_llm import LiteLlm
                import os
                import logging
                
                logger = logging.getLogger(__name__)
                
                # Prepare Azure configuration
                azure_config = {}
                
                if settings:
                    # Use new API key management system for Azure API key
                    azure_key = settings.get_azure_api_key()
                    if azure_key:
                        # Set environment variable for LiteLLM to use
                        os.environ["AZURE_API_KEY"] = azure_key
                        azure_config["api_key"] = azure_key
                        if settings.is_debug_mode():
                            logger.debug(f"Set Azure API key for model {model_identifier}")
                    elif settings.is_debug_mode():
                        logger.warning(f"No Azure API key available for model {model_identifier}")
                    
                    # Set other Azure configuration from settings
                    if hasattr(settings, 'azure_api_base') and settings.azure_api_base:
                        os.environ["AZURE_API_BASE"] = settings.azure_api_base
                        azure_config["api_base"] = settings.azure_api_base
                        if settings.is_debug_mode():
                            logger.debug(f"Set Azure API base: {settings.azure_api_base}")
                    
                    if hasattr(settings, 'azure_api_version') and settings.azure_api_version:
                        os.environ["AZURE_API_VERSION"] = settings.azure_api_version
                        azure_config["api_version"] = settings.azure_api_version
                        if settings.is_debug_mode():
                            logger.debug(f"Set Azure API version: {settings.azure_api_version}")
                
                # Convert azure-gpt-4 to azure/gpt-4 format if needed
                if "azure-" in model_lower and not model_lower.startswith("azure/"):
                    azure_model = model_identifier.replace("azure-", "azure/")
                else:
                    azure_model = model_identifier
                
                if settings and settings.is_debug_mode():
                    logger.debug(f"Creating LiteLLM model: {azure_model}")
                    logger.debug(f"Azure config: {azure_config}")
                
                # Create LiteLlm instance - ADK's LiteLlm should use environment variables
                # but we also set them explicitly to ensure they're available
                return LiteLlm(model=azure_model)
            except ImportError:
                # LiteLLM not available, fallback to string
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
            model_lower.startswith("azure/") or "azure-" in model_lower
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
        return False