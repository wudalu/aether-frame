# -*- coding: utf-8 -*-
"""
DeepSeek Streaming LLM wrapper for ADK integration.

This wrapper implements the connect() method required for ADK live streaming,
providing native DeepSeek streaming support that bypasses LiteLLM limitations.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

import aiohttp
import sseclient


class DeepSeekStreamingLLM:
    """
    DeepSeek LLM wrapper with native streaming support for ADK.
    
    This class implements the connect() method required for ADK live streaming,
    enabling real-time bidirectional communication with DeepSeek API.
    """
    
    def __init__(
        self,
        model: str = "deepseek-chat",
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com/v1",
        **kwargs
    ):
        """
        Initialize DeepSeek streaming LLM wrapper.
        
        Args:
            model: DeepSeek model name
            api_key: DeepSeek API key
            base_url: DeepSeek API base URL
            **kwargs: Additional configuration
        """
        self.model = model
        self.api_key = api_key or self._get_api_key_from_env()
        self.base_url = base_url
        self.config = kwargs
        
        if not self.api_key:
            raise ValueError("DeepSeek API key is required")
    
    def _get_api_key_from_env(self) -> Optional[str]:
        """Get API key from environment variables."""
        import os
        return os.getenv("DEEPSEEK_API_KEY")
    
    @asynccontextmanager
    async def connect(self, llm_request):
        """
        Create live connection for streaming.
        
        This method implements the ADK BaseLlm.connect() interface
        required for live streaming support.
        
        Args:
            llm_request: ADK LlmRequest object
            
        Yields:
            DeepSeekLiveConnection: Live connection instance
        """
        connection = DeepSeekLiveConnection(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            llm_request=llm_request
        )
        
        try:
            await connection.initialize()
            yield connection
        finally:
            await connection.close()
    
    async def generate_content_async(self, llm_request, stream: bool = False):
        """
        Generate content asynchronously.
        
        Args:
            llm_request: ADK LlmRequest object
            stream: Whether to stream response
            
        Yields:
            LlmResponse: Response chunks
        """
        if stream:
            async with self.connect(llm_request) as connection:
                async for chunk in connection.stream_response():
                    yield chunk
        else:
            # Single response implementation
            async with self.connect(llm_request) as connection:
                response = await connection.get_single_response()
                yield response
    
    def __str__(self) -> str:
        return f"DeepSeekStreamingLLM({self.model})"
    
    def __repr__(self) -> str:
        return f"DeepSeekStreamingLLM(model='{self.model}', base_url='{self.base_url}')"


class DeepSeekLiveConnection:
    """
    Live connection implementation for DeepSeek streaming.
    
    This class handles the actual HTTP streaming connection to DeepSeek API
    and provides the interface expected by ADK live flows.
    """
    
    def __init__(self, model: str, api_key: str, base_url: str, llm_request):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.llm_request = llm_request
        self.session = None
        self._closed = False
    
    async def initialize(self):
        """Initialize the connection."""
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close the connection."""
        if self.session and not self._closed:
            await self.session.close()
            self._closed = True
    
    async def stream_response(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream response from DeepSeek API.
        
        Yields:
            Dict: Response chunks in ADK-compatible format
        """
        if not self.session:
            raise RuntimeError("Connection not initialized")
        
        # Convert ADK request to DeepSeek format
        messages = self._convert_adk_request_to_deepseek(self.llm_request)
        
        # Prepare request
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }
        
        try:
            async with self.session.post(url, json=data, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"DeepSeek API error {response.status}: {error_text}")
                
                # Process streaming response
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if line.startswith('data: '):
                        data_str = line[6:]  # Remove 'data: ' prefix
                        
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            chunk_data = json.loads(data_str)
                            content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            
                            if content:
                                # Convert to ADK-compatible format
                                adk_chunk = self._convert_deepseek_chunk_to_adk(chunk_data, content)
                                yield adk_chunk
                                
                        except json.JSONDecodeError:
                            logging.warning(f"Failed to parse DeepSeek chunk: {data_str}")
                            continue
                        except Exception as e:
                            logging.error(f"Error processing DeepSeek chunk: {e}")
                            continue
                            
        except Exception as e:
            logging.error(f"DeepSeek streaming error: {e}")
            raise
    
    async def get_single_response(self) -> Dict[str, Any]:
        """
        Get single (non-streaming) response.
        
        Returns:
            Dict: Complete response in ADK-compatible format
        """
        if not self.session:
            raise RuntimeError("Connection not initialized")
        
        # Convert ADK request to DeepSeek format
        messages = self._convert_adk_request_to_deepseek(self.llm_request)
        
        # Prepare request
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        
        async with self.session.post(url, json=data, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"DeepSeek API error {response.status}: {error_text}")
            
            response_data = await response.json()
            content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Convert to ADK-compatible format
            return self._convert_deepseek_response_to_adk(response_data, content)
    
    def _convert_adk_request_to_deepseek(self, llm_request) -> list:
        """
        Convert ADK LlmRequest to DeepSeek API format.
        
        Args:
            llm_request: ADK LlmRequest object
            
        Returns:
            list: Messages in DeepSeek format
        """
        messages = []
        
        # Add system message if present
        if hasattr(llm_request, 'system_instruction') and llm_request.system_instruction:
            messages.append({
                "role": "system",
                "content": llm_request.system_instruction
            })
        
        # Add conversation messages
        if hasattr(llm_request, 'messages') and llm_request.messages:
            for msg in llm_request.messages:
                if hasattr(msg, 'role') and hasattr(msg, 'parts'):
                    # Extract text content from parts
                    content = ""
                    for part in msg.parts:
                        if hasattr(part, 'text'):
                            content += part.text
                    
                    if content:
                        messages.append({
                            "role": msg.role,
                            "content": content
                        })
        
        return messages
    
    def _convert_deepseek_chunk_to_adk(self, chunk_data: dict, content: str) -> dict:
        """
        Convert DeepSeek streaming chunk to ADK format.
        
        Args:
            chunk_data: Raw DeepSeek chunk
            content: Content string
            
        Returns:
            dict: ADK-compatible chunk
        """
        return {
            "text": content,
            "is_finished": False,
            "finish_reason": chunk_data.get("choices", [{}])[0].get("finish_reason"),
            "model": self.model,
            "usage": chunk_data.get("usage"),
            "chunk_type": "content"
        }
    
    def _convert_deepseek_response_to_adk(self, response_data: dict, content: str) -> dict:
        """
        Convert DeepSeek complete response to ADK format.
        
        Args:
            response_data: Raw DeepSeek response
            content: Content string
            
        Returns:
            dict: ADK-compatible response
        """
        return {
            "text": content,
            "is_finished": True,
            "finish_reason": response_data.get("choices", [{}])[0].get("finish_reason"),
            "model": self.model,
            "usage": response_data.get("usage"),
            "response_type": "complete"
        }