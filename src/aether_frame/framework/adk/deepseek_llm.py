# -*- coding: utf-8 -*-
"""DeepSeek LLM wrapper for ADK integration."""

from typing import Any, Dict, Optional


class DeepSeekLLM:
    """
    DeepSeek LLM wrapper class for ADK integration.
    
    This class provides a simple wrapper to use DeepSeek models
    within the ADK framework without modifying core logic.
    """
    
    def __init__(
        self,
        model: str = "deepseek-chat",
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com/v1",
        **kwargs
    ):
        """
        Initialize DeepSeek LLM wrapper.
        
        Args:
            model: DeepSeek model name (e.g., "deepseek-chat")
            api_key: DeepSeek API key (if None, will look for DEEPSEEK_API_KEY env var)
            base_url: DeepSeek API base URL
            **kwargs: Additional configuration parameters
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.config = kwargs
        
        # If no API key provided, try to get from environment
        if not self.api_key:
            import os
            self.api_key = os.getenv("DEEPSEEK_API_KEY")
        
        if not self.api_key:
            raise ValueError("DeepSeek API key is required. Set DEEPSEEK_API_KEY environment variable or pass api_key parameter.")
    
    def __str__(self) -> str:
        """String representation of the model."""
        return f"DeepSeek({self.model})"
    
    def __repr__(self) -> str:
        """Detailed representation of the model."""
        return f"DeepSeekLLM(model='{self.model}', base_url='{self.base_url}')"
    
    def to_litellm_format(self) -> str:
        """
        Convert to LiteLLM format for actual API calls.
        
        Returns:
            LiteLLM compatible model string
        """
        # DeepSeek can be accessed via LiteLLM with proper configuration
        return f"deepseek/{self.model}"
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get configuration for the model.
        
        Returns:
            Configuration dictionary
        """
        return {
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            **self.config
        }
    
    @classmethod
    def from_settings(cls, settings) -> "DeepSeekLLM":
        """
        Create DeepSeek LLM from application settings.
        
        Args:
            settings: Application settings object
            
        Returns:
            Configured DeepSeekLLM instance
        """
        return cls(
            model=getattr(settings, "deepseek_model", "deepseek-chat"),
            api_key=getattr(settings, "deepseek_api_key", None),
            base_url=getattr(settings, "deepseek_base_url", "https://api.deepseek.com/v1"),
            max_tokens=getattr(settings, "deepseek_max_tokens", 4096),
            temperature=getattr(settings, "deepseek_temperature", 0.7),
        )