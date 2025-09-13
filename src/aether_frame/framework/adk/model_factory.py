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
        return "deepseek" in model_lower
    
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
        # Gemini supports streaming natively through ADK
        if "gemini" in model_lower:
            return True
        return False