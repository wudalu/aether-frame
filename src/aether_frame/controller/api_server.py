"""
FastAPI application for the Aether Frame Controller layer.

This module creates and configures the FastAPI application that provides
HTTP API endpoints for the Aether Frame system.
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config.settings import Settings
from .request_processor import ControllerService


# Global controller service instance
controller_service: ControllerService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.
    """
    global controller_service
    
    # Startup
    logger = logging.getLogger(__name__)
    logger.info("Starting Aether Frame Controller API...")
    
    # Initialize API Key Manager
    api_key_manager = None
    try:
        settings = Settings()
        
        # Configure LiteLLM debug mode for development
        if settings.is_debug_mode():
            try:
                import litellm
                import os
                
                # Set LiteLLM debug mode using the recommended methods from documentation
                os.environ["LITELLM_LOG"] = "DEBUG"
                
                # Enable verbose debugging using the official method
                litellm._turn_on_debug()
                
                logger.info("LiteLLM debug mode enabled for development")
                logger.info("LiteLLM will now show detailed logs including API calls and responses")
            except ImportError:
                logger.warning("LiteLLM not available for debug configuration")
            except Exception as e:
                logger.warning(f"Failed to enable LiteLLM debug mode: {e}")
        
        # Initialize and start API key manager
        from ..services import initialize_api_key_manager
        api_key_manager = initialize_api_key_manager(settings)
        await api_key_manager.start()
        logger.info("API key manager started successfully")
        
        controller_service = ControllerService(settings)
        # Don't initialize here to avoid blocking startup
        # await controller_service.initialize()
        logger.info("Controller service created successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to create controller service: {str(e)}")
        # Don't raise to allow server to start
        controller_service = None
        yield
    finally:
        # Shutdown
        if api_key_manager:
            try:
                await api_key_manager.stop()
                logger.info("API key manager stopped")
            except Exception as e:
                logger.error(f"Error stopping API key manager: {str(e)}")
                
        if controller_service:
            try:
                await controller_service.shutdown()
            except Exception as e:
                logger.error(f"Error during shutdown: {str(e)}")
        logger.info("Aether Frame Controller API shutdown complete")


def create_app_factory() -> FastAPI:
    """
    Factory function for uvicorn reload mode.
    
    Returns:
        FastAPI: Configured FastAPI application
    """
    return create_app()


def create_app(settings: Settings = None) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        settings: Configuration settings. If None, will create default settings.
        
    Returns:
        FastAPI: Configured FastAPI application
    """
    if settings is None:
        settings = Settings()
    
    app = FastAPI(
        title="Aether Frame Controller API - UPDATED VERSION",
        description="HTTP API for the Aether Frame AI Assistant system",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Setup exception handlers
    setup_exception_handlers(app)
    
    # Include API routes
    try:
        from .endpoints import health, chat
        
        app.include_router(health.router, prefix="/api/v1", tags=["health"])
        app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    except ImportError as e:
        # Handle import errors gracefully during development
        print(f"Warning: Could not import endpoints: {e}")
        
        # Add a basic health endpoint as fallback
        @app.get("/api/v1/health")
        async def basic_health():
            return {"status": "healthy", "service": "ControllerService", "message": "Basic health check"}
    
    return app


async def get_controller_service() -> ControllerService:
    """
    Dependency to get the controller service instance.
    
    Returns:
        ControllerService: The global controller service instance
        
    Raises:
        HTTPException: If the service is not initialized
    """
    global controller_service
    
    # Create service if it doesn't exist (for TestClient scenarios)
    if controller_service is None:
        try:
            settings = Settings()
            controller_service = ControllerService(settings)
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to create controller service: {str(e)}"
            )
    
    # Initialize the service if not already done
    if not controller_service._initialized:
        try:
            await controller_service.initialize()
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to initialize controller service: {str(e)}"
            )
    
    return controller_service


def setup_exception_handlers(app: FastAPI):
    """Setup global exception handlers for the FastAPI app."""
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger = logging.getLogger(__name__)
        logger.error(f"Unhandled exception: {str(exc)}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "type": "internal_error"
            }
        )