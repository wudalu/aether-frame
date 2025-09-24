"""
Chat endpoints for the Aether Frame Controller API.

This module provides HTTP endpoints that accept external requests and convert them
into TaskRequest objects for processing by the controller service.
"""

import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ...contracts import TaskRequest, UniversalMessage, AgentConfig, TaskResult
from ..api_server import get_controller_service
from ..request_processor import ControllerService


router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message model for API requests."""
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional message metadata")


class ChatRequest(BaseModel):
    """Chat request model for API endpoints."""
    message: str = Field(..., description="User message content")
    model: Optional[str] = Field("deepseek-chat", description="AI model to use")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: Optional[int] = Field(1500, gt=0, description="Maximum tokens in response")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_id: Optional[str] = Field(None, description="User ID for tracking")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional request metadata")


class ProcessRequest(BaseModel):
    """Direct TaskRequest processing model for advanced usage."""
    task_type: str = Field(..., description="Type of task to process")
    description: Optional[str] = Field(None, description="Task description")
    messages: List[ChatMessage] = Field(..., description="List of messages")
    model: Optional[str] = Field("deepseek-chat", description="AI model to use")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: Optional[int] = Field(1500, gt=0, description="Maximum tokens in response")
    agent_type: Optional[str] = Field("conversational_assistant", description="Type of agent")
    system_prompt: Optional[str] = Field(None, description="System prompt for the agent")
    available_tools: Optional[List[str]] = Field(None, description="Available tools for the agent")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional task metadata")


class ChatResponse(BaseModel):
    """Chat response model."""
    task_id: str
    status: str
    message: str
    model: str
    processing_time: float
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ProcessResponse(BaseModel):
    """Process response model."""
    task_id: str
    status: str
    messages: List[ChatMessage]
    processing_time: float
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    controller: ControllerService = Depends(get_controller_service)
) -> ChatResponse:
    """
    Simple chat endpoint that accepts a message and returns an AI response.
    
    This endpoint converts the simple chat request into a TaskRequest and processes it.
    
    Args:
        request: Chat request with message and optional parameters
        controller: Controller service dependency
        
    Returns:
        ChatResponse: AI response with metadata
    """
    start_time = time.time()
    
    try:
        # Generate task ID
        task_id = f"chat_{int(start_time * 1000)}"
        
        # Build TaskRequest from chat request
        task_request = TaskRequest(
            task_id=task_id,
            task_type="chat",
            description=f"Chat request from API: {request.message[:50]}...",
            messages=[
                UniversalMessage(
                    role="user",
                    content=request.message,
                    metadata={
                        "api_request": True,
                        "user_id": request.user_id,
                        "session_id": request.session_id
                    }
                )
            ],
            agent_config=AgentConfig(
                agent_type="conversational_assistant",
                system_prompt=request.system_prompt or "You are a helpful AI assistant.",
                model_config={
                    "model": request.model,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens
                },
                framework_config={
                    "provider": "deepseek" if "deepseek" in request.model else "openai"
                }
            ),
            metadata={
                "api_endpoint": "chat",
                "user_id": request.user_id,
                "session_id": request.session_id,
                "timestamp": time.time(),
                **(request.metadata or {})
            }
        )
        
        # Process the request
        result = await controller.process_request(task_request)
        
        processing_time = time.time() - start_time
        
        # Extract response message
        response_message = ""
        if result.messages and len(result.messages) > 0:
            response_message = result.messages[0].content
        
        return ChatResponse(
            task_id=result.task_id,
            status=result.status.value,
            message=response_message,
            model=request.model,
            processing_time=processing_time,
            session_id=request.session_id,
            metadata=result.metadata
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Chat processing failed",
                "message": str(e),
                "processing_time": processing_time
            }
        )


@router.post("/process", response_model=ProcessResponse)
async def process_endpoint(
    request: ProcessRequest,
    controller: ControllerService = Depends(get_controller_service)
) -> ProcessResponse:
    """
    Advanced processing endpoint that accepts a full TaskRequest-like structure.
    
    This endpoint provides more control over the task processing parameters.
    
    Args:
        request: Process request with detailed task parameters
        controller: Controller service dependency
        
    Returns:
        ProcessResponse: Processing result with full message history
    """
    start_time = time.time()
    
    try:
        # Generate task ID
        task_id = f"process_{int(start_time * 1000)}"
        
        # Convert API messages to UniversalMessage objects
        universal_messages = [
            UniversalMessage(
                role=msg.role,
                content=msg.content,
                metadata=msg.metadata or {}
            )
            for msg in request.messages
        ]
        
        # Build TaskRequest
        task_request = TaskRequest(
            task_id=task_id,
            task_type=request.task_type,
            description=request.description or f"API process request: {request.task_type}",
            messages=universal_messages,
            agent_config=AgentConfig(
                agent_type=request.agent_type,
                system_prompt=request.system_prompt or "You are a helpful AI assistant.",
                model_config={
                    "model": request.model,
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens
                },
                available_tools=request.available_tools,
                framework_config={
                    "provider": "deepseek" if "deepseek" in request.model else "openai"
                }
            ),
            metadata={
                "api_endpoint": "process",
                "timestamp": time.time(),
                **(request.metadata or {})
            }
        )
        
        # Process the request
        result = await controller.process_request(task_request)
        
        processing_time = time.time() - start_time
        
        # Convert result messages back to API format
        response_messages = [
            ChatMessage(
                role=msg.role,
                content=msg.content,
                metadata=msg.metadata
            )
            for msg in (result.messages or [])
        ]
        
        return ProcessResponse(
            task_id=result.task_id,
            status=result.status.value,
            messages=response_messages,
            processing_time=processing_time,
            error_message=result.error_message,
            metadata=result.metadata
        )
        
    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Process request failed",
                "message": str(e),
                "processing_time": processing_time
            }
        )