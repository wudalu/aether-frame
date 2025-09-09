# -*- coding: utf-8 -*-
"""Task Router - Strategy selection for task execution."""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from ..contracts import TaskRequest, FrameworkType, TaskComplexity, ExecutionMode
from ..config.settings import Settings


@dataclass
class ExecutionStrategy:
    """Execution strategy determined by task routing."""
    framework_type: FrameworkType
    agent_type: str
    task_complexity: TaskComplexity
    agent_config: Dict[str, Any]
    runtime_options: Dict[str, Any]
    framework_score: float = 0.0
    fallback_frameworks: List[FrameworkType] = None


class TaskRouter:
    """
    TaskRouter analyzes incoming tasks and selects the optimal execution strategy
    based on task characteristics, framework capabilities, and performance requirements.
    
    Integrates comprehensive strategy configuration including framework capabilities,
    performance thresholds, and intelligent routing algorithms.
    """
    
    # Framework capability matrix
    FRAMEWORK_CAPABILITIES = {
        FrameworkType.ADK: {
            "memory_management": True,
            "observability": True,
            "tool_integration": True,
            "session_management": True,
            "state_persistence": True,
            "streaming": True,
            "async_execution": True,
            "scalability": "high",
            "performance": "high"
        },
        FrameworkType.AUTOGEN: {
            "memory_management": False,
            "observability": False,
            "tool_integration": True,
            "session_management": False,
            "state_persistence": False,
            "streaming": False,
            "async_execution": True,
            "scalability": "medium",
            "performance": "medium"
        },
        FrameworkType.LANGGRAPH: {
            "memory_management": True,
            "observability": True,
            "tool_integration": True,
            "session_management": True,
            "state_persistence": True,
            "streaming": True,
            "async_execution": True,
            "scalability": "high",
            "performance": "high"
        }
    }
    
    # Task complexity routing rules
    COMPLEXITY_ROUTING = {
        TaskComplexity.SIMPLE: {
            "preferred_frameworks": [FrameworkType.ADK, FrameworkType.AUTOGEN],
            "execution_mode": ExecutionMode.SYNC,
            "max_iterations": 5,
            "timeout": 30,
            "retry_count": 2
        },
        TaskComplexity.MODERATE: {
            "preferred_frameworks": [FrameworkType.ADK, FrameworkType.LANGGRAPH],
            "execution_mode": ExecutionMode.ASYNC,
            "max_iterations": 10,
            "timeout": 120,
            "retry_count": 3
        },
        TaskComplexity.COMPLEX: {
            "preferred_frameworks": [FrameworkType.ADK, FrameworkType.LANGGRAPH],
            "execution_mode": ExecutionMode.ASYNC,
            "max_iterations": 20,
            "timeout": 300,
            "retry_count": 3
        },
        TaskComplexity.ADVANCED: {
            "preferred_frameworks": [FrameworkType.ADK, FrameworkType.LANGGRAPH],
            "execution_mode": ExecutionMode.STREAMING,
            "max_iterations": 50,
            "timeout": 600,
            "retry_count": 5
        }
    }
    
    # Task type to agent type mapping
    TASK_TYPE_MAPPING = {
        "chat": {
            "agent_type": "conversational_agent",
            "preferred_frameworks": [FrameworkType.ADK],
            "required_capabilities": ["memory_management", "session_management"]
        },
        "analysis": {
            "agent_type": "analytical_agent",
            "preferred_frameworks": [FrameworkType.ADK, FrameworkType.LANGGRAPH],
            "required_capabilities": ["tool_integration", "state_persistence"]
        },
        "code": {
            "agent_type": "coding_agent",
            "preferred_frameworks": [FrameworkType.ADK, FrameworkType.LANGGRAPH],
            "required_capabilities": ["tool_integration", "observability"]
        },
        "research": {
            "agent_type": "research_agent",
            "preferred_frameworks": [FrameworkType.ADK, FrameworkType.LANGGRAPH],
            "required_capabilities": ["tool_integration", "memory_management", "state_persistence"]
        },
        "planning": {
            "agent_type": "planning_agent",
            "preferred_frameworks": [FrameworkType.LANGGRAPH, FrameworkType.ADK],
            "required_capabilities": ["state_persistence", "memory_management", "async_execution"]
        },
        "orchestration": {
            "agent_type": "orchestration_agent",
            "preferred_frameworks": [FrameworkType.LANGGRAPH, FrameworkType.ADK],
            "required_capabilities": ["async_execution", "streaming", "observability"]
        }
    }
    
    # Framework selection criteria weights
    SELECTION_WEIGHTS = {
        "capability_match": 0.4,    # How well framework capabilities match requirements
        "performance": 0.3,         # Framework performance characteristics
        "reliability": 0.2,         # Framework reliability and error rates
        "resource_usage": 0.1       # Framework resource consumption
    }
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize task router with configuration."""
        self.settings = settings or Settings()
        self._load_routing_rules()
    
    async def route_task(self, task_request: TaskRequest) -> ExecutionStrategy:
        """
        Analyze task and determine optimal execution strategy.
        
        Args:
            task_request: The task to be routed
            
        Returns:
            ExecutionStrategy: The selected execution strategy
        """
        # Analyze task complexity
        complexity = self._analyze_task_complexity(task_request)
        
        # Get optimal strategy using integrated logic
        strategy = self._get_optimal_strategy(
            task_request.task_type,
            complexity,
            {"available_tools": task_request.available_tools}
        )
        
        # Build agent configuration
        agent_config = self._build_agent_config(task_request, strategy)
        
        # Build runtime options
        runtime_options = self._build_runtime_options(task_request, complexity, strategy)
        
        return ExecutionStrategy(
            framework_type=strategy["framework_type"],
            agent_type=strategy["agent_type"],
            task_complexity=complexity,
            agent_config=agent_config,
            runtime_options=runtime_options,
            framework_score=strategy["framework_score"],
            fallback_frameworks=strategy["fallback_frameworks"]
        )
    
    def _analyze_task_complexity(self, task_request: TaskRequest) -> TaskComplexity:
        """Enhanced task complexity analysis."""
        complexity_score = 0
        
        # Message count factor
        if len(task_request.messages) > 20:
            complexity_score += 3
        elif len(task_request.messages) > 10:
            complexity_score += 2
        elif len(task_request.messages) > 5:
            complexity_score += 1
        
        # Tool count factor
        if len(task_request.available_tools) > 10:
            complexity_score += 3
        elif len(task_request.available_tools) > 5:
            complexity_score += 2
        elif len(task_request.available_tools) > 2:
            complexity_score += 1
        
        # Task type factor
        complex_task_types = ["research", "planning", "orchestration", "code"]
        if task_request.task_type in complex_task_types:
            complexity_score += 2
        
        # Knowledge factor
        if len(task_request.available_knowledge) > 5:
            complexity_score += 2
        elif len(task_request.available_knowledge) > 2:
            complexity_score += 1
        
        # Map score to complexity level
        if complexity_score >= 8:
            return TaskComplexity.ADVANCED
        elif complexity_score >= 5:
            return TaskComplexity.COMPLEX
        elif complexity_score >= 3:
            return TaskComplexity.MODERATE
        else:
            return TaskComplexity.SIMPLE
    
    def _get_optimal_strategy(self, task_type: str, complexity: TaskComplexity, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Get optimal execution strategy for given task characteristics."""
        # Get base configuration for task type
        task_config = self.TASK_TYPE_MAPPING.get(task_type, {
            "agent_type": "general_agent",
            "preferred_frameworks": [FrameworkType.ADK],
            "required_capabilities": []
        })
        
        # Get complexity-based configuration
        complexity_config = self.COMPLEXITY_ROUTING.get(complexity, self.COMPLEXITY_ROUTING[TaskComplexity.SIMPLE])
        
        # Score frameworks
        framework_scores = {}
        for framework in task_config["preferred_frameworks"]:
            score = self._get_framework_score(framework, {
                "required_capabilities": task_config["required_capabilities"],
                **requirements
            })
            framework_scores[framework] = score
        
        # If no frameworks in preferred list, try all available frameworks
        if not framework_scores:
            for framework in FrameworkType:
                score = self._get_framework_score(framework, {
                    "required_capabilities": task_config["required_capabilities"],
                    **requirements
                })
                framework_scores[framework] = score
        
        # Select best framework
        best_framework = max(framework_scores.items(), key=lambda x: x[1])[0]
        
        return {
            "framework_type": best_framework,
            "agent_type": task_config["agent_type"],
            "execution_mode": complexity_config["execution_mode"],
            "max_iterations": complexity_config["max_iterations"],
            "timeout": complexity_config["timeout"],
            "retry_count": complexity_config["retry_count"],
            "required_capabilities": task_config["required_capabilities"],
            "framework_score": framework_scores[best_framework],
            "fallback_frameworks": [f for f in framework_scores.keys() if f != best_framework]
        }
    
    def _get_framework_score(self, framework_type: FrameworkType, task_requirements: Dict[str, Any]) -> float:
        """Calculate framework score based on task requirements."""
        capabilities = self.FRAMEWORK_CAPABILITIES.get(framework_type, {})
        
        # Calculate capability match score
        required_caps = task_requirements.get("required_capabilities", [])
        capability_score = 0.0
        if required_caps:
            matched_caps = sum(1 for cap in required_caps if capabilities.get(cap, False))
            capability_score = matched_caps / len(required_caps)
        else:
            capability_score = 1.0  # No specific requirements
        
        # Calculate performance score
        performance_level = capabilities.get("performance", "medium")
        performance_score = {
            "high": 1.0,
            "medium": 0.7,
            "low": 0.4
        }.get(performance_level, 0.5)
        
        # Calculate scalability score
        scalability_level = capabilities.get("scalability", "medium")
        scalability_score = {
            "high": 1.0,
            "medium": 0.7,
            "low": 0.4
        }.get(scalability_level, 0.5)
        
        # Weighted final score
        weights = self.SELECTION_WEIGHTS
        final_score = (
            capability_score * weights["capability_match"] +
            performance_score * weights["performance"] +
            scalability_score * weights["reliability"] +
            0.8 * weights["resource_usage"]  # Assume good resource usage
        )
        
        return min(final_score, 1.0)
    
    def _build_agent_config(self, task_request: TaskRequest, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Build agent configuration based on routing decisions."""
        config = {
            "agent_type": strategy["agent_type"],
            "framework_type": strategy["framework_type"].value,
            "capabilities": [tool.name for tool in task_request.available_tools],
            "max_iterations": strategy["max_iterations"],
            "timeout": strategy["timeout"],
            "required_capabilities": strategy["required_capabilities"]
        }
        
        # Merge with execution config from request if present
        if task_request.execution_config:
            config.update({
                "execution_mode": task_request.execution_config.execution_mode.value,
                "max_retries": task_request.execution_config.max_retries,
                "parallel_execution": task_request.execution_config.parallel_execution,
                "enable_logging": task_request.execution_config.enable_logging,
                "enable_monitoring": task_request.execution_config.enable_monitoring
            })
        
        return config
    
    def _build_runtime_options(self, task_request: TaskRequest, complexity: TaskComplexity, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Build runtime options based on task complexity and strategy."""
        return {
            "execution_mode": strategy["execution_mode"].value,
            "enable_logging": True,
            "enable_monitoring": True,
            "max_retries": strategy["retry_count"],
            "framework_score": strategy["framework_score"],
            "fallback_frameworks": [f.value for f in strategy["fallback_frameworks"]]
        }
    
    def _load_routing_rules(self):
        """Load routing rules from configuration."""
        # Can be extended to load additional rules from settings or external config
        pass