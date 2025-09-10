# -*- coding: utf-8 -*-
"""Framework Adapter Abstract Base Class."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from ...contracts import AgentRequest, TaskResult, FrameworkType, TaskRequest
from ...execution.task_router import ExecutionStrategy


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
    
    async def execute_task_with_strategy(self, task_request: TaskRequest, strategy: ExecutionStrategy) -> TaskResult:
        """
        Execute a task with routing strategy - bridge method for layer separation.
        
        This method handles the conversion from TaskRequest + Strategy to AgentRequest,
        keeping agent-specific logic in the Framework Abstraction Layer.
        
        Args:
            task_request: The universal task request
            strategy: The execution strategy from task router (framework-focused)
            
        Returns:
            TaskResult: The result of task execution
        """
        # Map task type to agent type - this logic belongs in Framework Layer
        agent_type = self._map_task_type_to_agent(
            task_request.task_type, 
            strategy.runtime_options.get("complexity_level", "simple")
        )
        
        # Build agent request from strategy - this is framework layer responsibility
        from ...contracts import AgentRequest, AgentConfig
        
        # Get execution config from strategy
        execution_config_dict = strategy.execution_config.copy()
        
        # Valid fields for AgentConfig
        valid_agent_config_fields = {
            'agent_type', 'framework_type', 'capabilities', 'max_iterations', 
            'timeout', 'model_config', 'system_prompt', 'behavior_settings', 
            'memory_config', 'tool_permissions'
        }
        
        # Filter and prepare agent config
        filtered_config = {
            k: v for k, v in execution_config_dict.items() 
            if k in valid_agent_config_fields and k not in ['agent_type', 'framework_type']
        }
        
        # Map framework execution config to agent config
        if 'available_tools' in execution_config_dict:
            filtered_config['capabilities'] = execution_config_dict['available_tools']
        if 'required_capabilities' in execution_config_dict:
            filtered_config['tool_permissions'] = execution_config_dict['required_capabilities']
        
        # Create agent config
        agent_config = AgentConfig(
            agent_type=agent_type,
            framework_type=strategy.framework_type,
            **filtered_config
        )
        
        # Create agent request
        agent_request = AgentRequest(
            agent_type=agent_type,
            framework_type=strategy.framework_type,
            task_request=task_request,
            agent_config=agent_config,
            runtime_options=strategy.runtime_options
        )
        
        # Execute through concrete framework implementation
        return await self.execute_task(agent_request)
    
    def _map_task_type_to_agent(self, task_type: str, complexity_level: str = "simple") -> str:
        """
        Map task type to agent type - Framework Layer responsibility.
        
        This logic was moved from TaskRouter to maintain proper layer separation.
        """
        # Default task type to agent type mapping
        task_to_agent_mapping = {
            "chat": "conversational_agent",
            "analysis": "analytical_agent", 
            "code": "coding_agent",
            "research": "research_agent",
            "planning": "planning_agent",
            "orchestration": "orchestration_agent"
        }
        
        return task_to_agent_mapping.get(task_type, "general_agent")
    
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