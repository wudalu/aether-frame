# -*- coding: utf-8 -*-
"""Framework Adapter Abstract Base Class."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from ...contracts import AgentRequest, TaskResult, FrameworkType


class FrameworkAdapter(ABC):
    """
    Abstract base class for framework adapters.
    
    Each framework implementation must provide an adapter that implements
    this interface to enable unified task execution through the framework
    abstraction layer.
    """
    
    @property
    @abstractmethod
    def framework_type(self) -> FrameworkType:
        """Return the framework type this adapter supports."""
        pass
    
    @abstractmethod
    async def initialize(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the framework adapter with configuration.
        
        Args:
            config: Framework-specific configuration
        """
        pass
    
    @abstractmethod
    async def execute_task(self, agent_request: AgentRequest) -> TaskResult:
        """
        Execute a task through this framework.
        
        Args:
            agent_request: The agent request containing task details
            
        Returns:
            TaskResult: The result of task execution
        """
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if the framework is available and ready to process tasks.
        
        Returns:
            bool: True if framework is available, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_capabilities(self) -> List[str]:
        """
        Get list of capabilities supported by this framework.
        
        Returns:
            List[str]: List of capability names
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of the framework.
        
        Returns:
            Dict[str, Any]: Health status information
        """
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Shutdown the framework adapter and cleanup resources."""
        pass
    
    async def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate framework-specific configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            bool: True if configuration is valid
        """
        # Default implementation - can be overridden
        return True
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get framework performance metrics.
        
        Returns:
            Dict[str, Any]: Performance metrics
        """
        # Default implementation - can be overridden
        return {}