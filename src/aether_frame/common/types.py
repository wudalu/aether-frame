"""Type definitions for Aether Frame."""

from typing import Dict, Any, Optional, List, Union
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class FrameworkType(Enum):
    """Supported framework types."""
    ADK = "adk"
    AUTOGEN = "autogen" 
    LANGGRAPH = "langgraph"


class ExecutionMode(Enum):
    """Task execution modes."""
    WORKFLOW = "workflow"
    COORDINATOR = "coordinator"


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskContext:
    """Context information for task execution."""
    task_id: str
    description: str
    domain: Optional[str] = None
    priority: int = 0
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AgentResponse:
    """Response from agent execution."""
    agent_id: str
    result: Any
    status: TaskStatus
    execution_time: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ToolResult:
    """Result from tool execution."""
    tool_name: str
    result: Any
    success: bool
    execution_time: Optional[float] = None
    error_message: Optional[str] = None


# Type aliases
TaskInput = Dict[str, Any]
TaskOutput = Dict[str, Any]
ConfigDict = Dict[str, Any]
MetricData = Dict[str, Union[str, int, float]]