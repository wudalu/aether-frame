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
    role: str = Field(...,
                      description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional message metadata")


class ChatRequest(BaseModel):
    """Chat request model for API endpoints."""
    message: str = Field(..., description="User message content")
    agent_id: str = Field(..., description="Agent ID from create-context")
    session_id: Optional[str] = Field(None, description="Session ID from create-context. If not provided, creates new session for the agent")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional request metadata")


class ProcessRequest(BaseModel):
    """Direct TaskRequest processing model for one-time task processing."""
    task_type: str = Field(..., description="Type of task to process")
    description: Optional[str] = Field(None, description="Task description")
    messages: List[ChatMessage] = Field(..., description="List of messages")
    # Agent creation parameters (always create new agent and session)
    model: Optional[str] = Field(
        "deepseek-chat", description="AI model to use")
    temperature: Optional[float] = Field(
        0.7, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: Optional[int] = Field(
        1500, gt=0, description="Maximum tokens in response")
    agent_type: Optional[str] = Field(
        "conversational_assistant", description="Type of agent")
    system_prompt: Optional[str] = Field(
        None, description="System prompt for the agent")
    available_tools: Optional[List[str]] = Field(
        None, description="Available tools for the agent")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional task metadata")


class ChatResponse(BaseModel):
    """Chat response model."""
    task_id: str
    status: str
    message: str
    processing_time: float
    agent_id: str
    session_id: str
    metadata: Optional[Dict[str, Any]] = None


class ProcessResponse(BaseModel):
    """Process response model."""
    task_id: str
    status: str
    messages: List[ChatMessage]
    processing_time: float
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CreateContextRequest(BaseModel):
    """Request model for creating RuntimeContext."""
    agent_type: str = Field(..., description="Type of agent to create")
    system_prompt: str = Field(..., description="System prompt for the agent")
    model: Optional[str] = Field(
        "deepseek-chat", description="AI model to use")
    temperature: Optional[float] = Field(
        0.7, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: Optional[int] = Field(
        1500, gt=0, description="Maximum tokens in response")
    available_tools: Optional[List[str]] = Field(
        None, description="Available tools for the agent")
    user_id: Optional[str] = Field(None, description="User ID for tracking")
    framework_config: Optional[Dict[str, Any]] = Field(
        None, description="Framework-specific configuration")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata")


class CreateContextResponse(BaseModel):
    """Response model for created RuntimeContext."""
    agent_id: str = Field(..., description="Created agent ID")
    session_id: str = Field(..., description="Created session ID")
    runner_id: str = Field(..., description="Created runner ID")
    framework_type: str = Field(..., description="Framework type used")
    agent_type: str = Field(..., description="Agent type")
    model: str = Field(..., description="Model used")
    created_at: str = Field(..., description="Creation timestamp")
    processing_time: float = Field(..., description="Context creation time")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional context metadata")


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    controller: ControllerService = Depends(get_controller_service)
) -> ChatResponse:
    """
    Chat endpoint for conversations with existing agents.

    This endpoint supports two modes:
    1. Continue existing session: Provide both agent_id and session_id
    2. Create new session: Provide only agent_id (session_id will be auto-created)

    Args:
        request: Chat request with message, agent_id, and optional session_id
        controller: Controller service dependency

    Returns:
        ChatResponse: AI response with metadata including session_id
    """
    start_time = time.time()

    try:
        # Generate task ID
        task_id = f"chat_{int(start_time * 1000)}"

        # Build TaskRequest - supports both existing session and new session creation
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
                        "agent_id": request.agent_id,
                        "session_id": request.session_id
                    }
                )
            ],
            agent_id=request.agent_id,
            session_id=request.session_id,  # Can be None for new session creation
            metadata={
                "api_endpoint": "chat",
                "context_reuse": request.session_id is not None,
                "new_session": request.session_id is None,
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
            processing_time=processing_time,
            agent_id=result.agent_id or request.agent_id,
            session_id=result.session_id or request.session_id,  # Use result session_id for new sessions
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
    One-time task processing endpoint that creates a new agent and session for each request.

    This endpoint is designed for independent task processing without context persistence.
    Each request creates a fresh agent and session based on the provided agent configuration.

    Args:
        request: Process request with task parameters and agent configuration
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

        # Build TaskRequest - always create new agent and session for one-time processing
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
                "one_time_processing": True,
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


@router.post("/create-context", response_model=CreateContextResponse)
async def create_context_endpoint(
    request: CreateContextRequest,
    controller: ControllerService = Depends(get_controller_service)
) -> CreateContextResponse:
    """
    Create RuntimeContext endpoint that pre-creates agent, runner, and session.

    This endpoint allows clients to pre-create a RuntimeContext with agent and session,
    which can then be used in subsequent process requests for faster response times.

    Args:
        request: Context creation request with agent configuration
        controller: Controller service dependency

    Returns:
        CreateContextResponse: Created context information including agent_id and session_id
    """
    start_time = time.time()

    try:
        # Build AgentConfig from request
        agent_config = AgentConfig(
            agent_type=request.agent_type,
            system_prompt=request.system_prompt,
            model_config={
                "model": request.model,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            },
            available_tools=request.available_tools or [],
            framework_config=request.framework_config or {}
        )

        # Create RuntimeContext through controller service
        context_info = await controller.create_runtime_context(
            agent_config=agent_config,
            user_id=request.user_id,
            metadata=request.metadata
        )

        processing_time = time.time() - start_time

        return CreateContextResponse(
            agent_id=context_info["agent_id"],
            session_id=context_info["session_id"],
            runner_id=context_info["runner_id"],
            framework_type=context_info["framework_type"],
            agent_type=context_info["agent_type"],
            model=context_info["model"],
            created_at=context_info["created_at"],
            processing_time=processing_time,
            metadata=context_info.get("metadata")
        )

    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Context creation failed",
                "message": str(e),
                "processing_time": processing_time
            }
        )
