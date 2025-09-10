# -*- coding: utf-8 -*-
"""Task Router - Strategy selection for task execution."""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from ..contracts import TaskRequest, FrameworkType, TaskComplexity, ExecutionMode
from ..config.settings import Settings
from ..config.routing_config import RoutingConfig


@dataclass
class ExecutionStrategy:
    """Execution strategy determined by task routing - framework-focused only."""
    framework_type: FrameworkType
    task_complexity: TaskComplexity
    execution_config: Dict[str, Any]
    runtime_options: Dict[str, Any]
    framework_score: float = 0.0
    fallback_frameworks: List[FrameworkType] = None


class TaskRouter:
    """
    TaskRouter selects the optimal framework for task execution.
    
    Current Implementation: ADK-First Approach
    ------------------------------------------
    Based on framework_abstraction.md design, this implementation uses ADK as the 
    primary framework with fallback strategy. This aligns with the ADK-First 
    Compatibility approach for initial development phase.
    
    Future Extension: Multi-Framework Support
    -----------------------------------------
    The interface is designed to support multiple frameworks through static 
    configuration management. Complex routing logic can be added later when 
    multiple frameworks are integrated.
    
    Interface preserved for future extension while keeping current logic simple.
    """
    
    def __init__(self, settings: Optional[Settings] = None, routing_config: Optional[RoutingConfig] = None):
        """
        Initialize task router.
        
        Args:
            settings: Application settings
            routing_config: Routing configuration (preserved for future use)
        """
        self.settings = settings or Settings()
        self.routing_config = routing_config or RoutingConfig()
    
    async def route_task(self, task_request: TaskRequest) -> ExecutionStrategy:
        """
        Route task to optimal framework - currently ADK fallback.
        
        Current Implementation: Always routes to ADK
        Future: Will use static configuration for multi-framework routing
        
        Args:
            task_request: The task to be routed
            
        Returns:
            ExecutionStrategy: Framework execution strategy (currently ADK-based)
        """
        # Current phase: ADK-First approach - direct ADK routing
        # Interface preserved for future multi-framework extension
        
        complexity = self._analyze_task_complexity(task_request)
        execution_config = self._build_execution_config(task_request)
        runtime_options = self._build_runtime_options(task_request, complexity)
        
        return ExecutionStrategy(
            framework_type=FrameworkType.ADK,  # ADK fallback for current phase
            task_complexity=complexity,
            execution_config=execution_config,
            runtime_options=runtime_options,
            framework_score=1.0,  # ADK gets full score as primary framework
            fallback_frameworks=[]  # No fallbacks needed in ADK-first approach
        )
    
    def _analyze_task_complexity(self, task_request: TaskRequest) -> TaskComplexity:
        """
        Simple task complexity analysis for ADK routing.
        
        Current Implementation: Basic heuristics
        Future: Can be enhanced with sophisticated analysis when needed
        """
        # Simple complexity analysis - interface preserved for future extension
        message_count = len(task_request.messages)
        tool_count = len(task_request.available_tools)
        
        # Basic complexity classification
        if message_count > 10 or tool_count > 5:
            return TaskComplexity.COMPLEX
        elif message_count > 3 or tool_count > 2:
            return TaskComplexity.MODERATE
        else:
            return TaskComplexity.SIMPLE
    
    def _build_execution_config(self, task_request: TaskRequest) -> Dict[str, Any]:
        """
        Build basic execution configuration for ADK.
        
        Current Implementation: ADK-optimized configuration
        Future: Framework-specific configuration logic
        """
        # Basic configuration for ADK execution
        config = {
            "framework_type": FrameworkType.ADK.value,
            "available_tools": [tool.name for tool in task_request.available_tools],
            "timeout": 300,  # Default 5 minutes for ADK
            "max_iterations": 20,  # ADK default
            "required_capabilities": []  # ADK handles all capabilities
        }
        
        # Merge with request execution config if present
        if task_request.execution_config:
            config.update({
                "execution_mode": task_request.execution_config.execution_mode.value,
                "max_retries": task_request.execution_config.max_retries,
                "enable_logging": task_request.execution_config.enable_logging,
                "enable_monitoring": task_request.execution_config.enable_monitoring
            })
        
        return config
    
    def _build_runtime_options(self, task_request: TaskRequest, complexity: TaskComplexity) -> Dict[str, Any]:
        """
        Build runtime options for ADK execution.
        
        Current Implementation: ADK-specific options
        Future: Framework-specific runtime configuration
        """
        # Basic runtime options for ADK
        return {
            "execution_mode": ExecutionMode.ASYNC.value,  # ADK supports async
            "enable_logging": True,
            "enable_monitoring": True,
            "max_retries": 3,  # ADK default retry count
            "task_type": task_request.task_type,  # Pass to framework layer
            "complexity_level": complexity.value
        }
    
    def update_routing_config(self, config: RoutingConfig):
        """
        Update routing configuration.
        
        Current Implementation: Configuration preserved but not actively used
        Future: Will drive multi-framework routing decisions
        """
        # Interface preserved for future multi-framework support
        self.routing_config = config