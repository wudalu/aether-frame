"""
Health check endpoints for the Aether Frame Controller API.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..api_server import get_controller_service
from ..request_processor import ControllerService


router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str
    timestamp: str
    initialized: bool = None
    error: str = None


@router.get("/health", response_model=HealthResponse)
async def health_check(
    controller: ControllerService = Depends(get_controller_service)
) -> HealthResponse:
    """
    Perform a health check of the controller service.
    
    Returns:
        HealthResponse: Current health status
    """
    health_data = await controller.health_check()
    
    # Map the health data to match HealthResponse model
    response_data = {
        "status": health_data.get("overall_status", health_data.get("status", "unknown")),
        "service": health_data.get("service", "ControllerService"),
        "timestamp": health_data.get("timestamp", "")
    }
    
    # Add optional fields only if they exist
    if "initialized" in health_data:
        response_data["initialized"] = health_data["initialized"]
    if "error" in health_data:
        response_data["error"] = health_data["error"]
    
    return HealthResponse(**response_data)


@router.get("/health/detailed")
async def detailed_health_check(
    controller: ControllerService = Depends(get_controller_service)
) -> Dict[str, Any]:
    """
    Perform a detailed health check with additional system information.
    
    Returns:
        Dict: Detailed health and system information
    """
    health_data = await controller.health_check()
    
    # Add additional system information
    health_data.update({
        "endpoints": {
            "health": "/api/v1/health",
            "chat": "/api/v1/chat",
            "process": "/api/v1/process"
        },
        "version": "1.0.0",
        "api_docs": "/docs"
    })
    
    return health_data