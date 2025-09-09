# -*- coding: utf-8 -*-
"""Application Execution Layer components.

This module provides the main execution orchestration:

- ai_assistant.py: System entry point and request processor
- execution_engine.py: Central orchestration and framework routing
- task_router.py: Strategy selection and task analysis
"""

from .ai_assistant import AIAssistant
from .execution_engine import ExecutionEngine  
from .task_router import TaskRouter, ExecutionStrategy

__all__ = [
    "AIAssistant",
    "ExecutionEngine",
    "TaskRouter",
    "ExecutionStrategy",
]