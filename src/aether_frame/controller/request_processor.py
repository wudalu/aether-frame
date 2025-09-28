"""
Request processor that replaces AI Assistant functionality.

This module contains the ControllerService class which implements the same
process_request() interface as the original AI Assistant, but is designed
to work within the controller layer architecture.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..config.settings import Settings
from ..contracts import TaskRequest, TaskResult, TaskStatus, AgentConfig
from ..bootstrap import create_system_components, SystemComponents


class ControllerService:
    """
    Controller service that replaces AI Assistant functionality.
    
    This service provides the same process_request() interface but is designed
    to be used within the controller layer for both direct calls and HTTP API endpoints.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize the controller service.
        
        Args:
            settings: Configuration settings. If None, will create default settings.
        """
        self.settings = settings or Settings()
        self.logger = logging.getLogger(__name__)
        self._components: Optional[SystemComponents] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the controller service components."""
        if self._initialized:
            return
            
        try:
            self.logger.info("Initializing ControllerService components...")
            self._components = await create_system_components(self.settings)
            self._initialized = True
            self.logger.info("ControllerService initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize ControllerService: {str(e)}")
            raise
    
    async def process_request(self, task_request: TaskRequest) -> TaskResult:
        """
        Process a task request and return the result.
        
        This method provides the same interface as the original AI Assistant
        but is implemented within the controller layer.
        
        Args:
            task_request: The task request to process
            
        Returns:
            TaskResult: The processing result
        """
        # Ensure service is initialized
        if not self._initialized:
            await self.initialize()
        
        start_time = datetime.now()
        
        self.logger.info(f"ControllerService processing request - task_id: {task_request.task_id}, task_type: {task_request.task_type}")
        
        try:
            # Validate the request (same logic as AI Assistant)
            if not self._validate_request(task_request):
                error_msg = "Invalid task request"
                validation_errors = self._get_validation_errors(task_request)
                self.logger.error(f"Request validation failed - task_id: {task_request.task_id}, errors: {validation_errors}")
                return TaskResult(
                    task_id=task_request.task_id,
                    status=TaskStatus.ERROR,
                    error_message=error_msg,
                    metadata={
                        "processed_by": "ControllerService",
                        "processing_time": (datetime.now() - start_time).total_seconds(),
                        "timestamp": datetime.now().isoformat(),
                        "validation_errors": validation_errors
                    }
                )
            
            self.logger.info(f"Request validation passed - task_id: {task_request.task_id}")

            # Process through execution engine (same as AI Assistant)
            result = await self._components.execution_engine.execute_task(task_request)
            
            # Add controller metadata to the result
            if result.metadata is None:
                result.metadata = {}
            result.metadata.update({
                "processed_by": "ControllerService",
                "processing_time": (datetime.now() - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat()
            })
            
            self.logger.info(f"Processing completed - task_id: {result.task_id}, status: {result.status.value if result.status else 'unknown'}, has_response: {bool(result.messages)}")
            return result

        except Exception as e:
            self.logger.error(f"ControllerService processing failed - task_id: {task_request.task_id}, error: {str(e)}")
            return TaskResult(
                task_id=task_request.task_id,
                status=TaskStatus.ERROR,
                error_message=f"Processing failed: {str(e)}",
                metadata={
                    "processed_by": "ControllerService",
                    "processing_time": (datetime.now() - start_time).total_seconds(),
                    "timestamp": datetime.now().isoformat(),
                    "error": True
                }
            )
    
    def _validate_request(self, task_request: TaskRequest) -> bool:
        """Validate the incoming task request (same logic as AI Assistant)."""
        if not task_request.task_id:
            return False
        if not task_request.task_type:
            return False
        if not task_request.description:
            return False
        return True
    
    def _get_validation_errors(self, task_request: TaskRequest) -> list:
        """Get detailed validation errors for logging (same logic as AI Assistant)."""
        errors = []
        if not task_request.task_id:
            errors.append("missing_task_id")
        if not task_request.task_type:
            errors.append("missing_task_type")
        if not task_request.description:
            errors.append("missing_description")
        return errors

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the controller service.
        
        Returns:
            Dict containing health status information
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            # Perform comprehensive health check using bootstrap function
            from ..bootstrap import health_check_system
            health_status = await health_check_system(self._components)
            
            # Add controller-specific information
            health_status.update({
                "service": "ControllerService",
                "initialized": self._initialized,
                "timestamp": datetime.now().isoformat()
            })
            
            return health_status
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "ControllerService", 
                "error": str(e),
                "initialized": self._initialized,
                "timestamp": datetime.now().isoformat()
            }
    
    async def create_runtime_context(
        self, 
        agent_config: "AgentConfig", 
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create RuntimeContext by pre-creating agent, runner, and session.
        
        This method creates a complete RuntimeContext that can be used for subsequent
        task processing, allowing for faster response times by pre-initializing
        all necessary components.
        
        Args:
            agent_config: Agent configuration for creating the domain agent
            user_id: Optional user ID for tracking
            metadata: Optional additional metadata
            
        Returns:
            Dict containing context information including agent_id, session_id, etc.
        """
        # Ensure service is initialized
        if not self._initialized:
            await self.initialize()
        
        start_time = datetime.now()
        
        self.logger.info(f"Creating RuntimeContext - agent_type: {agent_config.agent_type}")
        
        try:
            from ..contracts import TaskRequest, FrameworkType
            from uuid import uuid4
            
            # Create a dummy TaskRequest for context creation
            dummy_task_id = f"context_create_{int(start_time.timestamp() * 1000)}"
            dummy_task_request = TaskRequest(
                task_id=dummy_task_id,
                task_type="context_creation",
                description="Creating RuntimeContext for pre-initialization",
                messages=[],  # Empty messages for context creation
                agent_config=agent_config,
                metadata={
                    "context_creation": True,
                    "user_id": user_id,
                    "timestamp": start_time.isoformat(),
                    **(metadata or {})
                }
            )
            
            # Get ADK framework adapter directly
            adk_adapter = await self._components.framework_registry.get_adapter(FrameworkType.ADK)
            if not adk_adapter:
                raise RuntimeError("ADK framework adapter not available")
            
            # Use the ADK adapter's _create_runtime_context_for_new_agent method
            # This creates domain_agent, registers it, creates runner and session
            runtime_context = await adk_adapter._create_runtime_context_for_new_agent(dummy_task_request)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Extract information from RuntimeContext
            context_info = {
                "agent_id": runtime_context.agent_id,
                "session_id": runtime_context.session_id,
                "runner_id": runtime_context.runner_id,
                "framework_type": runtime_context.framework_type.value,
                "agent_type": agent_config.agent_type,
                "model": agent_config.model_config.get("model", "deepseek-chat"),
                "created_at": runtime_context.created_at.isoformat() if runtime_context.created_at else start_time.isoformat(),
                "processing_time": processing_time,
                "metadata": {
                    "user_id": user_id,
                    "execution_id": runtime_context.execution_id,
                    "pattern": runtime_context.metadata.get("pattern"),
                    "created_by": "ControllerService",
                    **(metadata or {})
                }
            }
            
            self.logger.info(f"RuntimeContext created successfully - agent_id: {context_info['agent_id']}, session_id: {context_info['session_id']}, processing_time: {processing_time:.3f}s")
            return context_info
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"RuntimeContext creation failed - error: {str(e)}, processing_time: {processing_time:.3f}s")
            raise RuntimeError(f"Failed to create RuntimeContext: {str(e)}")

    async def shutdown(self) -> None:
        """Shutdown the controller service and cleanup resources."""
        try:
            self.logger.info("Shutting down ControllerService...")
            
            if self._components:
                from ..bootstrap import shutdown_system
                await shutdown_system(self._components)
                self._components = None
            
            self._initialized = False
            self.logger.info("ControllerService shutdown complete")
        except Exception as e:
            self.logger.error(f"Error during ControllerService shutdown: {str(e)}")